from datetime import datetime, timedelta, timezone

import pytest

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.lexical_memory import lowercase_lexical_text
from mygpt_brain.memory_store import MemoryRecord, MemoryStore
from mygpt_brain.session_store import ChatSessionStore

NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def record(mid, text, *, namespace='p1', tags=()):
    return MemoryRecord(memory_id=mid, namespace=namespace, kind='fact', text=text,
                        tags=list(tags), source='user_explicit', created_at=NOW, updated_at=NOW)


@pytest.mark.parametrize('stored,query', [
    ('CAFÉ préféré', 'café'), ('ΜΆΘΗΜΑ άλγεβρας', 'μάθημα'),
    ('АЛГЕБРА сегодня', 'алгебра'), ('ÉTUDE du jour', 'étude'),
])
def test_unicode_candidate_text_is_lowered_before_sql_lookup(stored, query):
    with MemoryStore() as memory:
        memory.put(record('matched', stored))
        memory.put(record('foreign', stored, namespace='other'))
        memory.put(record('unrelated', '语音设置'))
        assert [item.memory_id for item in memory.search(query, namespace='p1')] == ['matched']
        assert memory.get('matched').text == stored
        assert [event.action for event in memory.history('matched')] == ['ADD']


@pytest.mark.parametrize('tag,query', [('CAFÉ', 'café'), ('АЛГЕБРА', 'алгебра'), ('ΜΆΘΗΜΑ', 'μάθημα')])
def test_unicode_tags_use_same_preprocessor(tag, query):
    with MemoryStore() as memory:
        memory.put(record('tagged', 'explicit preference', tags=[tag]))
        assert [item.memory_id for item in memory.search(query, namespace='p1')] == ['tagged']
        assert memory.get('tagged').tags == [tag]


def test_lowercase_is_not_casefold_or_unicode_normalization():
    assert lowercase_lexical_text('İI') == 'i\u0307i'
    assert lowercase_lexical_text('CAFÉ') == 'café'
    assert lowercase_lexical_text('CAFE\u0301') == 'cafe\u0301'
    assert lowercase_lexical_text('Straße') == 'straße'
    assert lowercase_lexical_text('ΟΣ') == 'ος'
    for bad in (None, 42, b'ABC'):
        with pytest.raises(ValueError): lowercase_lexical_text(bad)


@pytest.mark.parametrize('stored,query', [
    ('Straße', 'STRASSE'), ('CAFÉ', 'cafe'), ('CAFE\u0301', 'café'),
    ('İSTANBUL', 'istanbul'), ('ΟΣ', 'οσ'), ('РАУ', 'PAY'),
])
def test_distinct_casefold_accents_and_lookalikes_do_not_broaden_candidates(stored, query):
    with MemoryStore() as memory:
        memory.put(record('literal', stored))
        assert memory.search(query, namespace='p1') == []


def test_dotted_i_and_combining_query_keep_existing_lexical_word_rules():
    with MemoryStore() as memory:
        memory.put(record('dotted', 'İSTANBUL'))
        memory.put(record('combining', 'CAFE\u0301'))
        assert [r.memory_id for r in memory.search('İSTANBUL', namespace='p1')] == ['dotted']
        assert [r.memory_id for r in memory.search('CAFE\u0301', namespace='p1')] == ['combining']


def test_sql_wildcards_never_become_user_supplied_patterns():
    with MemoryStore() as memory:
        memory.put(record('accented', 'CAFÉ préféré'))
        memory.put(record('other', 'unrelated secret'))
        assert memory.search('%_[]', namespace='p1') == []
        assert memory.search("%' OR 1=1 --", namespace='p1') == []
        assert [r.memory_id for r in memory.search('café_%', namespace='p1')] == ['accented']
        # Public preprocessing treats punctuation as word separators, not SQL patterns.
        assert memory.search('c_fé', namespace='p1') == memory.search('c fé', namespace='p1')
        assert memory.search('c_%é', namespace='p1') == []
        assert memory._keyword_candidates('c_fé', namespace='p1') == []


def test_reopened_connection_update_delete_and_schema_are_unchanged(tmp_path):
    path = tmp_path / 'memory.sqlite3'
    with MemoryStore(path) as memory:
        memory.put(record('m1', 'CAFÉ'))
        assert memory._db.execute("SELECT lower('CAFÉ'), mygpt_lexical_lower('CAFÉ')").fetchone()[:] == ('cafÉ', 'café')
    with MemoryStore(path) as memory:
        assert [r.memory_id for r in memory.search('café', namespace='p1')] == ['m1']
        memory.update('m1', text='АЛГЕБРА', tags=['ÉTUDE'], updated_at=NOW + timedelta(seconds=1))
        assert memory.search('café', namespace='p1') == []
        assert [r.memory_id for r in memory.search('алгебра étude', namespace='p1')] == ['m1']
        assert memory._db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == '1'
        memory.delete('m1', deleted_at=NOW + timedelta(seconds=2))
        assert memory.search('алгебра', namespace='p1') == []
        assert [e.action for e in memory.history('m1')] == ['DELETE', 'UPDATE', 'ADD']


def test_full_query_preserves_window_and_candidate_ceilings(monkeypatch):
    import mygpt_brain.memory_store as module
    with MemoryStore() as memory:
        for i in range(80): memory.put(record(f'm{i:02}', 'ΜΆΘΗΜΑ CAFÉ'))
        calls = []
        original = memory._keyword_candidates
        def select(query, **kwargs):
            calls.append((query, kwargs))
            return original(query, **kwargs)
        memory._keyword_candidates = select
        counts = []
        scorer = module.tfidf_memory_scores
        def score(query, documents):
            counts.append((len(query), len(documents)))
            return scorer(query, documents)
        monkeypatch.setattr(module, 'tfidf_memory_scores', score)
        query = ('μάθημα café ' * 400)[:4000]
        assert memory.search(query, namespace='p1', limit=6)
        assert len(calls) == 8
        assert all(len(q) <= 500 and options == {'namespace': 'p1', 'limit': 8} for q, options in calls)
        assert counts[0][0] == 4000 and counts[0][1] <= 64


@pytest.mark.asyncio
async def test_actual_prompt_recall_keeps_unicode_data_lower_authority_and_durable_text(tmp_path):
    query = '?' * 600 + 'café'
    persona = CompanionPersona(persona_id='p1', display_name='Test', visual_skin_id='test', instructions='Trusted persona')
    seen = []
    async def responder(prompt):
        seen.append(prompt)
        messages = prompt.provider_messages()
        recalled = [m for m in messages if 'CAFÉ préféré' in m.content]
        assert len(recalled) == 1 and recalled[0].role == 'user'
        assert all('foreign secret' not in m.content for m in messages)
        assert prompt.window.history[-1].content == query
        return 'Synthetic reply.'
    with MemoryStore(tmp_path / 'memory.sqlite3') as memory, ChatSessionStore(tmp_path / 'chat.sqlite3') as history:
        memory.put(record('pref', 'CAFÉ préféré'))
        memory.put(record('other', 'CAFÉ foreign secret', namespace='other'))
        runtime = CompanionChatRuntime(persona=persona, responder=responder, memory_store=memory, session_store=history)
        result = await runtime.send({'request_id': 'unicode', 'session_id': 's1', 'persona_id': 'p1', 'text': query}, now=NOW)
        assert result.recalled_memory_ids == ['pref']
        assert history.load_messages('s1')[-2].content == query
        assert len(memory.recent(namespace='p1')) == 1
        assert len(memory.history('pref')) == 1
    assert len(seen) == 1
