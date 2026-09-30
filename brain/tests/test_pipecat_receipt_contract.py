import asyncio

import pytest

from fixtures_pipecat import Frames, create_processor
from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.memory_store import MemoryStore
from mygpt_brain.pipecat_bridge import PipecatCompanionBridge
from mygpt_brain.session_store import ChatSessionStore


def runtime(responder, memory, sessions, persona='p1'):
    return CompanionChatRuntime(persona=CompanionPersona(persona_id=persona, display_name='Test',
        visual_skin_id='test', instructions='Trusted ' + persona), responder=responder,
        memory_store=memory, session_store=sessions)


@pytest.mark.asyncio
async def test_automatic_same_utterance_after_restart_is_new_with_prior_context(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    calls, replies = [], []
    for incarnation in range(2):
        async def responder(prompt, incarnation=incarnation):
            calls.append(prompt)
            if incarnation:
                assert [m.content for m in prompt.window.history] == ['Continue.', 'answer-0', 'Continue.']
            return f'answer-{incarnation}'
        with MemoryStore() as memory, ChatSessionStore(path) as sessions:
            bridge = PipecatCompanionBridge(runtime(responder, memory, sessions), session_id='conversation')
            replies.append(await bridge.respond('Continue.'))
            assert len(sessions.load_messages('conversation')) == 3 + 2 * incarnation
            bridge.close()
    assert len(calls) == 2
    assert [r.text for r in replies] == ['answer-0', 'answer-1']
    assert replies[0].request_id != replies[1].request_id
    assert not any(r.replayed for r in replies)


@pytest.mark.asyncio
async def test_explicit_receipt_retrieval_after_restart_keeps_data_and_one_commit(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    calls = []
    async def responder(_): calls.append(1); return 'Stored answer.'
    for incarnation in range(2):
        with MemoryStore() as memory, ChatSessionStore(path) as sessions:
            bridge = PipecatCompanionBridge(runtime(responder, memory, sessions), session_id='conversation')
            answer = await bridge.respond('Question.', request_id='explicit-retry')
            assert answer.text == 'Stored answer.' and answer.replayed is bool(incarnation)
            assert len(sessions.load_messages('conversation')) == 3
            bridge.close()
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', ['text', 'session', 'persona'])
async def test_explicit_receipt_conflicts_cannot_cross_text_session_or_persona(tmp_path, changed):
    path = tmp_path / 'chat.sqlite3'
    async def first(_): return 'PRIVATE P1 ANSWER'
    with MemoryStore() as memory, ChatSessionStore(path) as sessions:
        bridge = PipecatCompanionBridge(runtime(first, memory, sessions), session_id='s1')
        await bridge.respond('Question.', request_id='receipt')
        bridge.close()
    async def must_not_run(_): raise AssertionError('conflicting retry must not infer')
    with MemoryStore() as memory, ChatSessionStore(path) as sessions:
        bridge = PipecatCompanionBridge(runtime(must_not_run, memory, sessions, 'p2' if changed == 'persona' else 'p1'),
                                        session_id='s2' if changed == 'session' else 's1')
        with pytest.raises(ValueError, match='request_id conflict'):
            await bridge.respond('Different.' if changed == 'text' else 'Question.', request_id='receipt')
        assert len(sessions.load_messages('s1')) == 3
        assert sessions.load_messages('s2') == []


@pytest.mark.asyncio
@pytest.mark.parametrize('value', ['', ' ', 0, False, '../wrong', 'x' * 97])
async def test_invalid_explicit_id_never_falls_back_to_fresh_event(value):
    async def must_not_run(_): raise AssertionError('invalid input must not infer')
    with MemoryStore() as memory, ChatSessionStore() as sessions:
        bridge = PipecatCompanionBridge(runtime(must_not_run, memory, sessions), session_id='s1')
        with pytest.raises(ValueError): await bridge.respond('Question.', request_id=value)
        assert bridge._turn == 0
        assert sessions.load_messages('s1') == []


def test_long_lived_counter_and_separate_bridge_incarnations_are_distinct():
    async def unused(_): return 'unused'
    with MemoryStore() as memory, ChatSessionStore() as sessions:
        first = PipecatCompanionBridge(runtime(unused, memory, sessions), session_id='s1')
        second = PipecatCompanionBridge(runtime(unused, memory, sessions), session_id='s1')
        assert first._incarnation != second._incarnation
        ids = {first._request_id('same') for _ in range(5000)}
        assert len(ids) == 5000
        first._turn = (1 << 63) - 2
        assert len({first._request_id('same') for _ in range(4)}) == 4
        assert second._request_id('same') not in ids
        assert len(first._incarnation) == 32
        assert sessions.load_messages('s1') == []


@pytest.mark.asyncio
async def test_processor_receipt_replay_has_completion_but_no_repeated_speech_or_formatter(tmp_path):
    calls, formatted = [], []
    async def responder(_): calls.append(1); return 'Stored speech.'
    async def formatter(text): formatted.append(text); return text
    with MemoryStore() as memory, ChatSessionStore(tmp_path / 'chat.sqlite3') as sessions:
        bridge = PipecatCompanionBridge(runtime(responder, memory, sessions), session_id='s1')
        processor = create_processor(bridge, speech_formatter=formatter)
        for _ in range(2):
            frame = Frames.TranscriptionFrame('Question.', metadata={'mygpt': {'request_id': 'stable', 'session_id': 'ignored'}})
            await processor.process_frame(frame, 'down')
        spoken = [f for f, _ in processor.pushed if isinstance(f, Frames.LLMTextFrame)]
        ends = [f for f, _ in processor.pushed if isinstance(f, Frames.LLMFullResponseEndFrame)]
        assert len(spoken) == len(calls) == len(formatted) == 1
        assert [f.metadata['mygpt']['replayed'] for f in ends] == [False, True]
        assert all(f.metadata['mygpt']['request_id'] == 'stable' for f in ends)
        assert len(sessions.load_messages('s1')) == 3
        assert sessions.load_messages('ignored') == []


@pytest.mark.asyncio
@pytest.mark.parametrize('metadata', [None, [], {'mygpt': None}, {'mygpt': {'request_id': None}}, {'mygpt': {'request_id': ''}}, {'mygpt': {'request_id': '../bad'}}])
async def test_malformed_retry_metadata_fails_closed_without_output(metadata):
    async def must_not_run(_): raise AssertionError('invalid retry must not infer')
    with MemoryStore() as memory, ChatSessionStore() as sessions:
        bridge = PipecatCompanionBridge(runtime(must_not_run, memory, sessions), session_id='s1')
        processor = create_processor(bridge)
        frame = Frames.TranscriptionFrame('Question.')
        frame.metadata = metadata
        await processor.process_frame(frame, 'down')
        assert processor.errors == ['MyGPT companion reply unavailable']
        assert not any(isinstance(f, Frames.LLMTextFrame) for f, _ in processor.pushed)
        assert sessions.load_messages('s1') == []
