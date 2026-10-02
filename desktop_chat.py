"""Desktop text adapter over the existing companion runtime and SQLite store.

One event loop owns the async runtime for the whole desktop service lifetime.
History is read-only; no refresh, restart, or ambiguous retry dispatches a model.
"""
import asyncio
from concurrent.futures import TimeoutError as FutureTimeout
import hashlib
import json
from pathlib import Path
import threading
from uuid import UUID

from mygpt_brain.companion_chat import CompanionChatRequest, CompanionChatRuntime, CompanionPersona
from mygpt_brain.providers import OllamaResponder
from mygpt_brain.session_store import ChatSessionStore

SESSION_ID = 'desktop-local-chat-v1'
PERSONA_ID = 'mygpt-desktop-v1'
MAX_PROMPT_CHARS = 4000


def validate_request(value):
    if not isinstance(value, dict) or set(value) != {'consent', 'port', 'model', 'prompt', 'request_id'}:
        raise ValueError('invalid_chat_request')
    if value['consent'] is not True:
        raise ValueError('explicit_consent_required')
    port, model, prompt, request_id = (value[k] for k in ('port', 'model', 'prompt', 'request_id'))
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('invalid_local_port')
    if not isinstance(model, str) or not model.strip() or len(model) > 160 or 'cloud' in model.lower():
        raise ValueError('local_model_name_required')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError('prompt_must_contain_1_to_4000_characters')
    try:
        if not isinstance(request_id, str) or str(UUID(request_id)) != request_id:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError('invalid_request_id') from None
    request = CompanionChatRequest(request_id=request_id, session_id=SESSION_ID,
                                   persona_id=PERSONA_ID, text=prompt)
    fingerprint = hashlib.sha256(json.dumps({
        'request': request.model_dump(mode='json'), 'port': port, 'model': model.strip(),
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return request, fingerprint, port, model.strip()


class DesktopChat:
    def __init__(self, home):
        self._guard = threading.RLock()
        self._closed = False
        self._slot = threading.BoundedSemaphore(1)
        self.store = ChatSessionStore(Path(home)/'chat.sqlite3')
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name='mygpt-desktop-chat', daemon=True)
        self.thread.start()
        try:
            asyncio.run_coroutine_threadsafe(self._initialize(), self.loop).result(timeout=5)
        except BaseException:
            self.close()
            raise

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        self.loop.close()

    async def _initialize(self):
        persona = CompanionPersona(persona_id=PERSONA_ID, display_name='mygpt', visual_skin_id='3714430278',
            instructions='你是mygpt学习助手。诚实区分来源与推断；不声称看到了屏幕或Book实时状态。不把学习时长当作掌握证明。')
        async def unconfigured(_prompt):
            raise RuntimeError("desktop provider requires explicit configuration")
        self.runtime = CompanionChatRuntime(persona=persona, responder=unconfigured,
            session_store=self.store, recent_turn_limit=20, request_timeout_seconds=60)

    def history(self, before=None):
        with self._guard:
            if self._closed:
                raise ValueError('chat_service_closed')
            return self.store.history_page(SESSION_ID, persona_id=PERSONA_ID, before=before)

    def send(self, value):
        request, fingerprint, port, model = validate_request(value)
        if not self._slot.acquire(blocking=False):
            raise ValueError('model_busy')
        try:
            with self._guard:
                if self._closed:
                    raise ValueError('chat_service_closed')
                future = asyncio.run_coroutine_threadsafe(self._send(request, fingerprint, port, model), self.loop)
            try:
                return future.result(timeout=65)
            except FutureTimeout:
                future.cancel()
                raise ValueError('chat_outcome_unknown_check_history_no_automatic_retry') from None
        finally:
            self._slot.release()

    async def _send(self, request, fingerprint, port, model):
        # SQLite claim failure is before provider contact. An existing claim is
        # not a receipt: it may represent crash/timeout/failure after dispatch.
        with self._guard:
            if self._closed:
                raise ValueError('chat_service_closed')
            fresh, generation = self.store.claim_dispatch(request.request_id, SESSION_ID, fingerprint)
            if not fresh and self.store.get_receipt(request.request_id) is None:
                raise ValueError('chat_outcome_unknown_check_history_no_automatic_retry')
        def is_current():
            return not self._closed and self.store.dispatch_is_current(request.request_id, generation)
        provider = OllamaResponder(model, port=port, timeout_seconds=60,
                                   keep_alive="0", num_predict=2048)
        async def guarded_provider(prompt):
            if not is_current():
                raise ValueError('chat_admission_revoked')
            return await provider(prompt)
        self.runtime.responder = guarded_provider
        try:
            result = await self.runtime.send(request, is_current=is_current,
                                             completion_guard=lambda: self._guard)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Do not expose provider response, prompt, SQL paths or exception
            # internals. Saved state can only be established by receipt/history.
            raise ValueError('chat_result_unconfirmed_check_history_no_automatic_retry') from None
        return {'reply': result.assistant_message.content, 'request_id': result.request_id,
                'session_id': result.session_id, 'saved': True, 'replayed': result.replayed,
                'origin': 'USER_CONFIGURED_LOCAL_OLLAMA', 'quality_verified': False}

    async def _shutdown(self):
        current = asyncio.current_task()
        pending = [task for task in asyncio.all_tasks() if task is not current]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def close(self):
        with self._guard:
            if self._closed:
                return
            self._closed = True
        try:
            asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop).result(timeout=10)
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=5)
            if not self.thread.is_alive():
                self.store.close()
                if hasattr(self, 'runtime'):
                    self.runtime.memory_store.close()
