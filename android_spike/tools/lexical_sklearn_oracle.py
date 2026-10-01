"""Generate/check synthetic Android scores using actual pinned sklearn, not the port."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import random
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'android_spike/src/test/resources/lexical-memory-golden.json'
PIN = 'bbf8863a869f118a1a42422d8cc67ec6c07f2fe0'


def normalize(text):
    return ' '.join(re.findall(r'[^\W_]+', text.lower()))


def cases():
    values = [
        ('chinese', '数学 拓扑', ['数学 拓扑', '数学 代数 几何', '语音 设置']),
        ('english', 'topology study', ['topology study', 'study exam review', 'voice local']),
        ('repetition', 'a a a b', ['a b', 'a a a a b', 'b b b', 'c']),
        ('mixed', 'Mixed! 中文_123', ['MIXED 中文', '123 456', 'other']),
        ('none', '???', ['数学', '语音']),
        ('empty', '', []),
        ('empty-vocabulary', 'math', ['', '?!', '_']),
        ('zero-overlap', 'xyzzy', ['数学', '语音']),
        ('late-query-evidence', '无' * 3996 + '拓扑学习', ['拓扑学习', '语音 设置']),
        ('after-old-token-cap', ' '.join('zzz' + str(i) for i in range(30)) + ' 拓扑',
         ['拓扑', '语音 设置']),
        ('unicode', 'CAFÉ ΙΣ Ⅳ ² 𠀀 𐐀', ['café ις ⅳ ² 𠀀 𐐨', 'other']),
        ('combining-separators', 're\u0301sume _ 中文—拓扑', ['re sume 中文 拓扑', 'resume', 'other']),
        ('max-candidates', '数学 语音', [('数学' if i % 3 else '语音') * 5 for i in range(100)]),
    ]
    rng = random.Random(20260930)
    words = ['数学', '拓扑', '代数', 'a', 'longword', '学习', 'voice', '42', 'café', 'Ⅳ', '²', '𠀀']
    for i in range(96):
        documents = [' '.join(rng.choices(words, k=rng.randint(0, 30))) for _ in range(rng.randint(1, 12))]
        query = ' / '.join(rng.choices(words, k=rng.randint(0, 25)))
        values.append((f'random-{i:03}', query, documents))
    result = []
    for name, query, documents in values:
        normalized_documents = [normalize(text) for text in documents]
        normalized_query = normalize(query)
        scores = [0.0] * len(documents)
        if any(normalized_documents):
            vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3),
                                        sublinear_tf=True, smooth_idf=True, norm='l2', lowercase=False)
            fitted = vectorizer.fit_transform(normalized_documents)
            scores = cosine_similarity(vectorizer.transform([normalized_query]), fitted)[0].tolist()
        result.append({'id': name, 'query': query, 'documents': documents,
                       'normalized_query': normalized_query, 'normalized_documents': normalized_documents,
                       'scores': [round(value, 14) for value in scores]})
    return {'upstream': 'scikit-learn/scikit-learn', 'version': '1.9.1', 'source_commit': PIN, 'cases': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Explicitly regenerate the synthetic fixture')
    args = parser.parse_args()
    if importlib.metadata.version('scikit-learn') != '1.9.1':
        raise SystemExit('actual scikit-learn 1.9.1 is required')
    expected = cases()
    if args.write:
        FIXTURE.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n')
    actual = json.loads(FIXTURE.read_text())
    if actual.keys() != expected.keys() or len(actual['cases']) != len(expected['cases']):
        raise SystemExit('oracle fixture inventory mismatch')
    for key in ('upstream', 'version', 'source_commit'):
        if actual[key] != expected[key]: raise SystemExit('oracle identity mismatch')
    for got, want in zip(actual['cases'], expected['cases']):
        if got.keys() != want.keys(): raise SystemExit('oracle case structure mismatch')
        for key in ('id', 'query', 'documents', 'normalized_query', 'normalized_documents'):
            if got[key] != want[key]: raise SystemExit('oracle case/input mismatch: ' + key)
        if len(got['scores']) != len(want['scores']): raise SystemExit('oracle score count mismatch')
        if any(not isinstance(a, (int, float)) or not abs(a - b) <= 1e-12
               for a, b in zip(got['scores'], want['scores'])):
            raise SystemExit('oracle score mismatch')
    print('Actual sklearn oracle PASS:', len(expected['cases']), 'Android fixture cases')


if __name__ == '__main__':
    main()
