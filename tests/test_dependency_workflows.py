"""Protect the new aggregate Python-only reproducibility scope without network."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DependencyWorkflowTests(unittest.TestCase):
    def text(self, name):
        return (ROOT / '.github/workflows' / name).read_text()

    def test_linux_uses_isolated_complete_lock_and_only_named_source_exception(self):
        text = self.text('companion-fusion-acceptance.yml')
        self.assertIn('python -m venv "$RUNNER_TEMP/fusion-venv"', text)
        self.assertIn('LOCK=brain/requirements-linux-py313-full.lock', text)
        self.assertIn('--bootstrap-output "$OUT/bootstrap.lock"', text)
        self.assertNotIn("pip install '.[realtime,lexical-test]'", text)
        self.assertIn('--only-binary=:all: --no-binary=docopt --no-build-isolation --require-hashes', text)
        self.assertNotIn('--no-binary=:all:', text)

    def test_windows_uses_own_lock_and_never_reresolves_editable_source(self):
        text = self.text('desktop-delivery.yml')
        self.assertIn('python -m venv "$env:RUNNER_TEMP/windows-venv"', text)
        self.assertIn('brain/requirements-windows-py313-build.lock', text)
        self.assertNotIn('pip install -e', text)
        self.assertNotIn('pip install pyinstaller', text)
        self.assertNotIn('--no-binary', text)

    def test_both_install_offline_without_hidden_build_dependency_resolution(self):
        for name in ('companion-fusion-acceptance.yml', 'desktop-delivery.yml'):
            with self.subTest(name=name):
                text = self.text(name)
                self.assertIn('--no-cache-dir --no-index --find-links=', text)
                self.assertIn('--require-hashes --force-reinstall', text)
                self.assertIn('--isolated install --no-index --no-build-isolation --no-deps ./brain', text)
                self.assertIn('--installed --install-report', text)
                self.assertIn('native-install-report.json', text)
                self.assertIn('https://pypi.org/simple', text)
                self.assertNotIn('--extra-index-url', text)

    def test_existing_strict_and_native_gates_remain_mandatory(self):
        linux = self.text('companion-fusion-acceptance.yml')
        windows = self.text('desktop-delivery.yml')
        self.assertIn('scripts/verify_integrations.py', linux)
        self.assertIn('scripts/verify_fusion_upstreams.py', linux)
        self.assertIn('scripts/verify_receipt_growth.py --rounds 1000 10000', linux)
        self.assertIn('tools/build_windows_delivery.py --source-commit', windows)
        self.assertIn('brain/tests/test_dependency_lock.py brain/tests/test_acceptance_tools.py', windows)
        self.assertIn('dependency-tests.xml', windows)
        self.assertIn('scripts/assert_required_jobs.py windows-native', windows)
        self.assertIn('needs: [production-components, android-java-boundaries, source-recovery, windows-desktop]', linux)

    def test_only_fixed_sha_actions_and_source_only_recovery_scope(self):
        for name in ('companion-fusion-acceptance.yml', 'desktop-delivery.yml'):
            for action in re.findall(r'uses: (actions/\S+)', self.text(name)):
                self.assertRegex(action, r'^actions/[\w-]+@[a-f0-9]{40}$')
        for path in ('brain/requirements-linux-py313-full.lock', 'brain/requirements-windows-py313-build.lock',
                     'brain/scripts/verify_dependency_lock.py', 'brain/tests/test_dependency_lock.py'):
            from scripts.source_bundle import safe_path
            self.assertTrue(safe_path(path), path)


if __name__ == '__main__':
    unittest.main()
