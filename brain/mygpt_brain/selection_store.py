"""Bounded volatile intake; authorization belongs to the calling service.

No input is called authenticated Book data. Expired entries are purged on access,
not by an always-on timer; revoke/close clears immediately. No disk is used.
"""
from copy import deepcopy
from datetime import timedelta
import math
import secrets
import threading
import time

from .core import ImportedReaderContext, checked_now, utc_now
from .selection_packet import decode_packet, source_bytes

class SelectionStore:
    def __init__(self, *, clock=utc_now, monotonic=time.monotonic):
        self.clock, self.monotonic = clock, monotonic
        self._lock = threading.RLock()
        self._items = {}

    def _purge(self):
        wall, mono = checked_now(self.clock()), self.monotonic()
        if type(mono) not in (int, float) or not math.isfinite(mono):
            self._items.clear()
            raise ValueError('invalid_clock')
        for key, (entry, begin, end) in list(self._items.items()):
            context = ImportedReaderContext.model_validate(entry['context'])
            if not (begin <= mono < end and context.captured_at <= wall < context.expires_at):
                del self._items[key]

    def add(self, raw: bytes) -> dict:
        packet = decode_packet(raw)
        text = source_bytes(packet.source).decode('utf-8')
        with self._lock:
            self._purge()
            if len(self._items) >= 16 or sum(len(e[0]['evidence_text'].encode()) for e in self._items.values()) + len(text.encode()) > 524288:
                raise ValueError('selection_capacity_exceeded')
            now, mono = checked_now(self.clock()), self.monotonic()
            key = 'import-' + secrets.token_hex(12)
            src = packet.source
            context = ImportedReaderContext(session_id=key, course_id=src.course_id,
                book_id=src.book_id, book_version=src.book_version_id, section_id=src.section_id,
                source_id=src.record_id, source_kind=src.source_kind, source_layer=src.layer,
                layer_id=src.layer_id, source_sha256=packet.source_sha256, mode='learn',
                captured_at=now, expires_at=now + timedelta(seconds=120))
            entry = {'id': key, 'label': src.title or src.record_id,
                'context': context.model_dump(mode='json'), 'source_ref': context.reference,
                'evidence_text': text,
                'fixture_reply': '[SIMULATED] 所选内容已通过结构与字节身份校验。来源仍未核验；这里没有进行真实模型推理。'}
            self._items[key] = (deepcopy(entry), mono, mono + 120)
            return entry

    def get(self, key: str) -> dict:
        with self._lock:
            self._purge()
            if key not in self._items:
                raise ValueError('selection_missing_or_expired')
            return deepcopy(self._items[key][0])

    def count(self):
        with self._lock:
            self._purge()
            return len(self._items)

    def clear(self):
        with self._lock:
            self._items.clear()
