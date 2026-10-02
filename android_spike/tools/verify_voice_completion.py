"""Check production callback ownership wiring and exact Android Pipecat notices."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTIVITY = 'android_llm_spike/companion/src/main/java/dev/mygpt/companionv2/CompanionV2Activity.kt'


def verify(root=ROOT):
    source = (root / ACTIVITY).read_text()
    required = (
        'private val ttsCompletion = VoiceOutputCompletion()',
        'val lease = ttsCompletion.beginUtterance()',
        '!ttsCompletion.isCurrent(lease)',
        'ttsCompletion.onSuccess(lease) {',
        'ttsCompletion.onFailure(lease) {\n                    stopTtsPlayback(null)',
        'private fun stopTtsPlayback(message: String? = null) {\n        ttsCompletion.invalidate()',
        'ttsEnabled = !ttsEnabled\n        ttsCompletion.invalidate()',
        'override fun onDestroy() {\n        ttsCompletion.close()',
    )
    if 'ttsEpoch' in source or not all(item in source for item in required):
        raise ValueError('production voice completion ownership wiring changed; audit callbacks')
    license = (root / 'third_party/pipecat/LICENSE').read_bytes()
    digest = hashlib.sha1(b'blob ' + str(len(license)).encode() + b'\0' + license).hexdigest()
    if digest != '88cf66570d9c1e77bcb44f9eeacfa051d840267c':
        raise ValueError('Pipecat license differs from pinned source')
    for module in ('android_spike/app', 'android_llm_spike/app', 'android_voice_spike/app'):
        assets = root / module / 'src/main/assets'
        if (assets / 'PIPECAT_LICENSE.txt').read_bytes() != license:
            raise ValueError('Android Pipecat license asset mismatch')
        if '49dea682fb84bfc515d881d00dfeaaa9e9f1075f' not in (assets / 'PIPECAT_NOTICE.txt').read_text():
            raise ValueError('Android Pipecat notice pin mismatch')
    build = (root / 'android_llm_spike/companion/build.gradle.kts').read_text()
    if 'assets.srcDir("../../android_spike/app/src/main/assets")' not in build:
        raise ValueError('Companion V2 must inherit Pipecat notices')
    print('Android voice completion wiring/license PASS (not AudioTrack/device acceptance)')


if __name__ == '__main__':
    verify()
