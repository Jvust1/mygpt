"""Check Android lexical source wiring and exact bundled attribution, no SDK needed."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LICENSE_BLOB = '3d7ee432c15b685eaa654b6abe8f8e3ea8126a8d'


def verify(root=ROOT):
    license = (root / 'third_party/scikit-learn/LICENSE').read_bytes()
    identity = hashlib.sha1(b'blob ' + str(len(license)).encode() + b'\0' + license).hexdigest()
    if identity != LICENSE_BLOB:
        raise ValueError('sklearn license differs from pinned upstream')
    for module in ('android_spike/app', 'android_llm_spike/app', 'android_voice_spike/app'):
        assets = root / module / 'src/main/assets'
        if (assets / 'SCIKIT_LEARN_LICENSE.txt').read_bytes() != license:
            raise ValueError('Android sklearn license asset mismatch')
        notice = (assets / 'SCIKIT_LEARN_NOTICE.txt').read_text()
        if 'bbf8863a869f118a1a42422d8cc67ec6c07f2fe0' not in notice or 'BSD-3-Clause' not in notice:
            raise ValueError('Android sklearn provenance notice mismatch')
    build = (root / 'android_llm_spike/companion/build.gradle.kts').read_text()
    if 'assets.srcDir("../../android_spike/app/src/main/assets")' not in build:
        raise ValueError('Companion V2 must inherit sklearn notices')
    source = (root / 'android_llm_spike/companion/src/main/java/dev/mygpt/companionv2/LocalCompanionMemoryStore.kt').read_text()
    required = ('import dev.mygpt.spike.LexicalMemoryScorer',
                'recent(namespace, LexicalMemoryScorer.MAX_CANDIDATES)',
                'LexicalMemoryScorer.score(query, candidates.map { it.text })',
                '.filter { it.score > 0.0 }', '.thenByDescending { it.memory.updatedAtMs }',
                '.thenBy { it.memory.memoryId }')
    if not all(value in source for value in required) or 'queryTokens(' in source:
        raise ValueError('production memory scorer wiring changed; audit integration')
    print('Android lexical source wiring/license PASS (not an APK/device test)')


if __name__ == '__main__':
    verify()
