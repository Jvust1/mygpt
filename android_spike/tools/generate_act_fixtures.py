"""Regenerate bounded Java/Python ACT parity cases from the reviewed Python port.

Run using the pinned Brain environment, from repository root. Synthetic only.
"""
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "brain"))
from mygpt_brain.airi_act import parse_act_reply


def generate():
    cases = []
    def add(label, text):
        case = {"id": label, "input": text}
        try:
            r = parse_act_reply(text)
            case.update(text=r.text, emotion=r.emotion, intensity=r.intensity, marker_found=r.marker_found)
        except ValueError:
            case["error"] = True
        cases.append(case)
    def marker(payload):
        return "before<|ACT:" + payload + "|>after"
    add("plain", "学习 with literal punctuation * | {} []")
    add("non-act-control", "before<|ACTION:literal|>after")
    add("null-input", None)
    add("reply-over-limit", "x" * 16001)
    add("reply-at-limit", "x" * 16000)
    for name in ["happy", "sad", "angry", "think", "surprised", "awkward", "question", "curious", "neutral"]:
        add("name-" + name, marker(json.dumps({"emotion": name})))
        add("unicode-space-" + name, marker(json.dumps({"emotion": "\u00a0" + name.upper() + "\u0085"})))
    for index, value in enumerate([-100, -0.0, 0, 0.1, 0.75, 1, 100, True, False, None, "0.4", [], {}]):
        add("intensity-" + str(index), marker(json.dumps({"emotion": {"name": "happy", "intensity": value}})))
    for index, payload in enumerate([
        '{"emotion":"happy","note":"a|>b"}',
        '{"emotion":"happy","note":"a\\\"|>b"}',
        '{"emotion":"sad","emotion":"happy"}',
        '{"emotion":null,"emotion":"happy"}',
        '{"emotion":{"name":"sad","name":"happy"}}',
        '{"emotion":"happy","data":{"a":null,"a":2}}',
        '{"emotion":"happy","emot\\u0069on":"sad"}',
        '{"emotion":"happy","note":NaN}',
        '{"emotion":"happy","note":Infinity}',
        '{"emotion":"happy","note":-Infinity}',
        '{"emotion":"happy","note":1e999}',
        '{"emotion":"happy","note":1e-999}',
        '{"emotion":{"name":"happy","intensity":' + '9' * 400 + '}}',
        '{"emotion":"happy","note":"\\ud800"}',
        '{"emotion":"happy","\\udfff":0}',
        '{"emotion":"happy","note":"\\ud83d\\ude00"}',
        '{"emotion":"happy",}',
        '{emotion:"happy"}',
        '{"emotion":"happy"} {}',
        '{"emotion":"happy"/*comment*/}',
        '\ufeff{"emotion":"happy"}',
        '{"emotion":"THİNK"}',
        'null', '[]', '42', '"happy"', '{}',
    ]):
        add("strict-" + str(index), marker(payload))
    complete = '<|ACT:{"emotion":{"name":"happy","intensity":0.75}}|>'
    for end in range(1, len(complete)):
        add("truncated-" + str(end), "before" + complete[:end])
    add("multiple-last-valid", 'a<|ACT:{"emotion":"happy"}|>b<|ACT:{"emotion":"sad"}|>c')
    add("invalid-after-valid", 'a<|ACT:{"emotion":"happy"}|>b<|ACT:{"emotion":"unknown"}|>c')
    add("case-spacing", 'a<|act \n : {"emotion":"HAPPY"} |>b')
    add("unclosed-quote", 'before<|ACT:{"emotion":"happy","note":"unterminated|>after')
    for target in [767, 768, 769]:
        base = '{"emotion":"happy","note":"' + "中" * 200
        base += "x" * (target - len((base + '"}').encode())) + '"}'
        assert len(base.encode()) == target
        add("utf8-limit-" + str(target), marker(base))
    for depth in [22, 23, 24, 25, 26]:
        add("depth-" + str(depth), marker('{"emotion":"happy","data":' + '[' * depth + '0' + ']' * depth + '}'))
    rng = random.Random(20260930)
    for index in range(200):
        name = rng.choice(["happy", "sad", "neutral", "invalid"])
        payload = {"emotion": {"name": name, "intensity": rng.uniform(-1, 2)},
                   "note": rng.choice(["quoted |> text", "中文", "\\escape", "a\"b", "plain"])}
        value = marker(json.dumps(payload, ensure_ascii=False))
        if index % 5 == 0:
            value = value[:rng.randint(8, len(value) - 1)]
        add("random-" + str(index), value)
    source = (ROOT / "brain/mygpt_brain/airi_act.py").read_bytes()
    result = {"schema_version": "mygpt.airi-act-golden.v1",
              "python_parser_git_blob": hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest(),
              "cases": cases}
    target = ROOT / "android_spike/src/test/resources/airi-act-golden.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Generated {len(cases)} synthetic ACT parity cases")


if __name__ == "__main__":
    generate()
