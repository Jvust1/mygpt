"""Static call-site/attribution checks complement the real Java/sklearn gates."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('android_lexical_verify', ROOT / 'android_spike/tools/verify_lexical_integration.py')
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


class AndroidLexicalIntegrationTests(unittest.TestCase):
    def test_actual_production_call_and_all_asset_sets(self):
        verify.verify(ROOT)

    def test_pinned_license_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            license = root / 'third_party/scikit-learn/LICENSE'
            license.parent.mkdir(parents=True)
            license.write_text('synthetic wrong license')
            with self.assertRaisesRegex(ValueError, 'license differs'):
                verify.verify(root)
