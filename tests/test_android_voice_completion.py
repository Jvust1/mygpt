"""Source wiring is checked separately from the production JVM ownership tests."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('verify_voice_completion', ROOT / 'android_spike/tools/verify_voice_completion.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class VoiceCompletionWiringTests(unittest.TestCase):
    def test_actual_callbacks_and_all_current_asset_sets(self):
        module.verify(ROOT)

    def test_unguarded_failure_regression_is_detected(self):
        read = Path.read_text
        def changed(path, *args, **kwargs):
            text = read(path, *args, **kwargs)
            if path == ROOT / module.ACTIVITY:
                return text.replace('ttsCompletion.onFailure(lease) {', 'run {')
            return text
        with patch.object(Path, 'read_text', changed):
            with self.assertRaisesRegex(ValueError, 'ownership wiring changed'):
                module.verify(ROOT)
