"""Actual Pipecat queue/TTS + SQLite restart, with only model/audio synthesis doubled."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.memory_store import MemoryStore
from mygpt_brain.pipecat_bridge import PipecatCompanionBridge, create_pipecat_companion_processor
from mygpt_brain.session_store import ChatSessionStore
from test_pipecat_runtime import SynthesisTextProbe, frames, setup_for, transcript

PERSONA = CompanionPersona(persona_id='p1', display_name='Test', visual_skin_id='test', instructions='Trusted persona')


def bridge_for(responder, memory, sessions):
    runtime = CompanionChatRuntime(persona=PERSONA, responder=responder, memory_store=memory, session_store=sessions)
    return PipecatCompanionBridge(runtime, session_id='resumed-conversation')


@asynccontextmanager
async def pipeline(bridge):
    processor = create_pipecat_companion_processor(bridge)
    tts = SynthesisTextProbe()
    processor.link(tts)
    setup = setup_for()
    await processor.setup(setup)
    await tts.setup(setup)
    endings, interrupted, emitted = asyncio.Queue(), asyncio.Event(), []
    @tts.event_handler('on_after_process_frame')
    async def complete(_processor, frame):
        if isinstance(frame, frames.LLMFullResponseEndFrame): endings.put_nowait(frame)
        if isinstance(frame, frames.InterruptionFrame): interrupted.set()
    @processor.event_handler('on_before_push_frame')
    async def record(_processor, frame): emitted.append(frame)
    async def send(text, request_id=None):
        frame = transcript(text)
        if request_id is not None: frame.metadata['mygpt'] = {'request_id': request_id}
        await processor.queue_frame(frame)
        return await asyncio.wait_for(endings.get(), 3)
    try:
        await processor.queue_frame(frames.StartFrame())
        yield SimpleNamespace(processor=processor, tts=tts, send=send, interrupted=interrupted, emitted=emitted)
    finally:
        await processor.cleanup()
        await tts.cleanup()
    assert setup.task_manager.current_tasks() == []


@pytest.mark.asyncio
async def test_real_voice_restart_same_utterance_produces_new_reply_once(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    calls, ids, spoken = [], [], []
    for incarnation in range(2):
        async def responder(prompt, incarnation=incarnation):
            calls.append(prompt)
            if incarnation:
                assert [m.content for m in prompt.window.history] == ['Continue please.', 'Answer 0.', 'Continue please.']
            return f'Answer {incarnation}.'
        with MemoryStore() as memory, ChatSessionStore(path) as sessions:
            bridge = bridge_for(responder, memory, sessions)
            async with pipeline(bridge) as run:
                end = await run.send('Continue please.')
                ids.append(end.metadata['mygpt']['request_id'])
                assert end.metadata['mygpt']['replayed'] is False
                assert run.tts.spoken == [f'Answer {incarnation}.']
                spoken += run.tts.spoken
                assert len(sessions.load_messages('resumed-conversation')) == 3 + 2 * incarnation
    assert ids[0] != ids[1]
    assert len(calls) == 2 and spoken == ['Answer 0.', 'Answer 1.']


@pytest.mark.asyncio
async def test_real_voice_cold_receipt_replay_retrieves_data_without_duplicate_speech(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    calls = []
    async def responder(prompt):
        calls.append(1)
        if len(calls) == 1: return 'Stored answer.'
        assert [m.content for m in prompt.window.history] == ['Question.', 'Stored answer.', 'New continuation.']
        return 'Fresh continuation.'
    for incarnation in range(2):
        with MemoryStore() as memory, ChatSessionStore(path) as sessions:
            bridge = bridge_for(responder, memory, sessions)
            async with pipeline(bridge) as run:
                end = await run.send('Question.', request_id='explicit-receipt')
                assert end.metadata['mygpt'] == {'request_id': 'explicit-receipt', 'replayed': bool(incarnation)}
                assert run.tts.spoken == ([] if incarnation else ['Stored answer.'])
                text_frames = [f for f in run.emitted if isinstance(f, frames.LLMTextFrame)]
                assert len(text_frames) == (0 if incarnation else 1)
                assert len(sessions.load_messages('resumed-conversation')) == 3
                # The existing bridge retrieval API still exposes stored data.
                retrieved = await bridge.respond('Question.', request_id='explicit-receipt')
                assert retrieved.replayed and retrieved.text == 'Stored answer.'
                assert calls == [1]
                if incarnation:
                    continued = await run.send('New continuation.')
                    assert continued.metadata['mygpt']['replayed'] is False
                    assert run.tts.spoken == ['Fresh continuation.']
                    assert len(sessions.load_messages('resumed-conversation')) == 5
    assert calls == [1, 1]


@pytest.mark.asyncio
async def test_real_cancel_restart_retry_commits_and_speaks_only_recovered_turn(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    entered, cancelled = asyncio.Event(), asyncio.Event()
    async def interrupted_responder(_):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            return 'Obsolete response after cancellation.'
    with MemoryStore() as memory, ChatSessionStore(path) as sessions:
        async with pipeline(bridge_for(interrupted_responder, memory, sessions)) as run:
            frame = transcript('Resume this question.')
            frame.metadata['mygpt'] = {'request_id': 'unfinished-request'}
            await run.processor.queue_frame(frame)
            await asyncio.wait_for(entered.wait(), 2)
            await run.processor.queue_frame(frames.InterruptionFrame())
            await asyncio.wait_for(run.interrupted.wait(), 2)
            assert cancelled.is_set()
            assert run.tts.spoken == []
            assert sessions.load_messages('resumed-conversation') == []
            assert sessions.get_receipt('unfinished-request') is None
    calls = []
    async def recovered(_): calls.append(1); return 'Recovered answer.'
    with MemoryStore() as memory, ChatSessionStore(path) as sessions:
        async with pipeline(bridge_for(recovered, memory, sessions)) as run:
            first = await run.send('Resume this question.', request_id='unfinished-request')
            replay = await run.send('Resume this question.', request_id='unfinished-request')
            assert first.metadata['mygpt']['replayed'] is False and replay.metadata['mygpt']['replayed'] is True
            assert run.tts.spoken == ['Recovered answer.']
            assert calls == [1]
            assert [m.content for m in sessions.load_messages('resumed-conversation')] == [
                PERSONA.instructions, 'Resume this question.', 'Recovered answer.',
            ]
