"""Regression against actual engine behavior, not a replacement mock engine."""
import asyncio
from datetime import timedelta
from types import SimpleNamespace
import pytest
from mygpt_brain.local_service import LocalBrainEngine, LocalServiceError
from test_local_service import NOW, request

class Clock:
    wall = NOW
    mono = 10.0
    def advance(self, seconds):
        self.wall += timedelta(seconds=seconds)
        self.mono += seconds

async def fixed(_brain, _evidence, _question, text, _now):
    return SimpleNamespace(text=text)

def make(clock, **kwargs):
    return LocalBrainEngine(clock=lambda: clock.wall, monotonic=lambda: clock.mono,
                            responder=kwargs.pop('responder', fixed), **kwargs)

@pytest.mark.asyncio
async def test_cached_reply_cannot_outlive_selection():
    clock = Clock(); engine = make(clock)
    await engine.explain(request(offset_ms=1000))
    clock.advance(2)
    with pytest.raises(LocalServiceError, match='selection_expired'):
        await engine.explain(request(offset_ms=1000))

@pytest.mark.asyncio
async def test_reply_rechecks_expiry_after_await():
    clock = Clock()
    async def slow(*args):
        clock.advance(2)
        return await fixed(*args)
    engine = make(clock, responder=slow)
    with pytest.raises(LocalServiceError, match='selection_expired'):
        await engine.explain(request(offset_ms=1000))
    assert engine.status()['requests_completed'] == 0

@pytest.mark.asyncio
async def test_failed_request_is_terminal_not_permanently_running():
    engine = make(Clock()); body = request(); body['source_ref'] = 'forged'
    for _ in range(2):
        with pytest.raises(LocalServiceError, match='source_identity_mismatch'):
            await engine.explain(body)
    assert engine._requests['req-1'].status == 'failed'

@pytest.mark.asyncio
async def test_task_cancellation_is_recorded_and_propagated():
    started = asyncio.Event()
    async def pending(*_):
        started.set()
        await asyncio.Event().wait()
    engine = make(Clock(), responder=pending)
    task = asyncio.create_task(engine.explain(request()))
    await started.wait(); task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    with pytest.raises(LocalServiceError, match='request_cancelled'):
        await engine.explain(request())

@pytest.mark.asyncio
async def test_authorization_expiring_during_reply_prevents_delivery():
    clock = Clock()
    async def slow(*args):
        clock.advance(61)
        return await fixed(*args)
    engine = make(clock, responder=slow, authorization_seconds=60)
    with pytest.raises(LocalServiceError, match='authorization_revoked_or_expired'):
        await engine.explain(request())
    assert engine.status()['requests_completed'] == 0

@pytest.mark.asyncio
async def test_mono_deadline_prevents_cache_resurrection_after_wall_rollback():
    clock = Clock(); engine = make(clock)
    body = request(offset_ms=1000); await engine.explain(body)
    clock.mono += 2
    with pytest.raises(LocalServiceError, match='selection_expired'):
        await engine.explain(body)

@pytest.mark.asyncio
async def test_unknown_cancel_tombstone_prevents_later_dispatch():
    engine=make(Clock());engine.cancel('req-1')
    with pytest.raises(LocalServiceError,match='request_cancelled'):await engine.explain(request())
    assert engine.status()['requests_started']==0

@pytest.mark.asyncio
async def test_responder_timeout_is_terminal_and_drains_cooperative_task():
    stopped=asyncio.Event()
    async def pending(*_):
        try:await asyncio.Event().wait()
        finally:stopped.set()
    engine=make(Clock(),responder=pending,request_timeout_seconds=.025)
    with pytest.raises(LocalServiceError,match='request_timeout') as caught:await engine.explain(request())
    assert caught.value.status==504 and stopped.is_set()
    with pytest.raises(LocalServiceError,match='request_timeout'):await engine.explain(request())

@pytest.mark.asyncio
async def test_cancel_during_pending_responder_does_not_wait_for_its_natural_completion():
    entered=asyncio.Event();stopped=asyncio.Event()
    async def pending(*_):
        try:entered.set();await asyncio.Event().wait()
        finally:stopped.set()
    engine=make(Clock(),responder=pending)
    task=asyncio.create_task(engine.explain(request()));await entered.wait();engine.cancel('req-1')
    with pytest.raises(LocalServiceError,match='request_cancelled'):await asyncio.wait_for(task,.5)
    assert stopped.is_set()

@pytest.mark.asyncio
async def test_exception_does_not_echo_private_message_and_is_terminal():
    async def fails(*_):raise RuntimeError('do-not-echo-this-fixture')
    engine=make(Clock(),responder=fails)
    for _ in range(2):
        with pytest.raises(LocalServiceError,match='^local_brain_failure$'):await engine.explain(request())

@pytest.mark.parametrize('text',['',' '*2,'x'*4001,123,None])
@pytest.mark.asyncio
async def test_invalid_responder_output_is_rejected(text):
    async def invalid(*_):return SimpleNamespace(text=text)
    engine=make(Clock(),responder=invalid)
    with pytest.raises(LocalServiceError,match='invalid_responder_reply'):await engine.explain(request())

@pytest.mark.parametrize('kwargs',[{'authorization_seconds':True},{'context_seconds':1.5},
    {'demo_delay_ms':False},{'request_timeout_seconds':float('inf')},
    {'request_timeout_seconds':float('nan')},{'request_timeout_seconds':0}])
def test_configuration_limits_are_strict(kwargs):
    with pytest.raises(ValueError):make(Clock(),**kwargs)

@pytest.mark.asyncio
async def test_repeated_expired_cache_reads_remain_expired_not_in_progress():
    clock=Clock();e=make(clock);body=request(offset_ms=1000)
    await e.explain(body);clock.advance(2)
    for _ in range(3):
        with pytest.raises(LocalServiceError,match='selection_expired'):await e.explain(body)

@pytest.mark.asyncio
async def test_self_cancelled_responder_produces_bounded_terminal_error():
    async def cancelled(*_):raise asyncio.CancelledError()
    e=make(Clock(),responder=cancelled)
    for _ in range(2):
        with pytest.raises(LocalServiceError,match='responder_cancelled'):await e.explain(request())
