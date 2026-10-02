"""Local user-owned notes and focus records. Book content is never auto-persisted."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

MAX_BYTES = 2 * 1024 * 1024
ID = re.compile(r'^[A-Za-z0-9_~.-]{1,120}$')


def empty():
    return {'goal': '', 'notes': {}, 'sessions': {}, 'active': None}


def text(value, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('invalid_text')
    return value


def validate(value):
    if not isinstance(value, dict) or set(value) != {'goal', 'notes', 'sessions', 'active'}:
        raise ValueError('invalid_workspace_schema')
    text(value['goal'], 500)
    for section, cap in (('notes', 1000), ('sessions', 2000)):
        items = value[section]
        if not isinstance(items, dict) or len(items) > cap:
            raise ValueError('too_many_items')
        for key, item in items.items():
            if not isinstance(key, str) or not ID.fullmatch(key) or not isinstance(item, dict):
                raise ValueError('invalid_item')
            if section == 'notes':
                if set(item) != {'title', 'body'}: raise ValueError('invalid_note')
                text(item['title'], 160); text(item['body'], 20000)
            else:
                if set(item) != {'goal', 'seconds', 'ended_at'}: raise ValueError('invalid_session')
                text(item['goal'], 500); text(item['ended_at'], 40)
                if type(item['seconds']) is not int or not 0 <= item['seconds'] <= 86400:
                    raise ValueError('invalid_duration')
    active = value['active']
    if active is not None:
        if not isinstance(active, dict) or set(active) != {'id', 'goal', 'started_ms', 'target_sec'}:
            raise ValueError('invalid_active_session')
        if not isinstance(active['id'], str) or not ID.fullmatch(active['id']): raise ValueError('invalid_session_id')
        text(active['goal'], 500)
        if type(active['started_ms']) is not int or not 0 <= active['started_ms'] <= 2**53-1:
            raise ValueError('invalid_start_time')
        if type(active['target_sec']) is not int or not 60 <= active['target_sec'] <= 14400:
            raise ValueError('invalid_target')
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(raw.encode('utf-8')) > MAX_BYTES: raise ValueError('workspace_too_large')
    return raw


class Store:
    def __init__(self, home):
        home = Path(home); home.mkdir(parents=True, exist_ok=True)
        self.path = home/'workspace.sqlite'
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS snapshots(revision INTEGER PRIMARY KEY, value TEXT NOT NULL, saved_at TEXT NOT NULL)')
            if not db.execute('SELECT 1 FROM snapshots LIMIT 1').fetchone():
                db.execute('INSERT INTO snapshots VALUES(0,?,?)', (validate(empty()), self.now()))

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def read(self):
        with closing(sqlite3.connect(self.path)) as db:
            rev, raw = db.execute('SELECT revision,value FROM snapshots ORDER BY revision DESC LIMIT 1').fetchone()
        value = json.loads(raw); validate(value)
        return {'revision': rev, 'value': value}

    def save(self, revision, value):
        if type(revision) is not int or revision < 0: raise ValueError('invalid_revision')
        raw = validate(value)
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            old, previous = db.execute('SELECT revision,value FROM snapshots ORDER BY revision DESC LIMIT 1').fetchone()
            if old != revision: raise ValueError('revision_conflict')
            if previous == raw: return {'revision': old, 'value': value}
            db.execute('INSERT INTO snapshots VALUES(?,?,?)', (old+1, raw, self.now()))
        return {'revision': old+1, 'value': value}

    def merge(self, backup):
        if not isinstance(backup, dict) or set(backup) != {'schema', 'value'} or backup['schema'] != 'mygpt-workspace-backup-v1':
            raise ValueError('invalid_backup')
        validate(backup['value'])
        current = self.read(); result = current['value']
        for section in ('notes', 'sessions'):
            for key, item in backup['value'][section].items():
                if key in result[section] and result[section][key] != item:
                    digest = hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
                    key = key[:90] + '~' + digest
                    if key in result[section] and result[section][key] != item:
                        raise ValueError('backup_identity_conflict')
                result[section].setdefault(key, item)
        if not result['goal']: result['goal'] = backup['value']['goal']
        # Never resume another device's active timer or overwrite this device's timer.
        return self.save(current['revision'], result)
