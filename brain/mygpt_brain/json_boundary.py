"""Bounded UTF-8 JSON input; no duplicate keys, nonfinite values or surrogates."""
import json
import math

class BoundaryError(ValueError):
    pass

def load_object(raw: bytes, *, max_bytes: int = 65536) -> dict:
    if type(raw) is not bytes or len(raw) > max_bytes:
        raise BoundaryError('invalid_json_size')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BoundaryError('duplicate_json_key')
            result[key] = value
        return result
    def constant(_):
        raise BoundaryError('nonfinite_json_number')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        stack, count = [(value, 0)], 0
        while stack:
            node, depth = stack.pop(); count += 1
            if depth > 24 or count > 8192:
                raise BoundaryError('json_complexity_limit')
            if isinstance(node, str) and any(0xD800 <= ord(c) <= 0xDFFF for c in node):
                raise BoundaryError('invalid_unicode_scalar')
            if isinstance(node, float) and not math.isfinite(node):
                raise BoundaryError('nonfinite_json_number')
            if isinstance(node, dict):
                stack.extend((x, depth + 1) for pair in node.items() for x in pair)
            elif isinstance(node, list):
                stack.extend((x, depth + 1) for x in node)
        if type(value) is not dict:
            raise BoundaryError('json_object_required')
        return value
    except BoundaryError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise BoundaryError('invalid_json') from None
