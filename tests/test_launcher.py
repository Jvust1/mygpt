"""Launcher unit tests use explicit metadata/process fixtures, not SDK success."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('launcher', Path(__file__).resolve().parents[1] / 'run_mygpt.py')
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'source with spaces'
        for name in launcher.REQUIRED_FILES:
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('fixture')
        (self.root / 'brain/pyproject.toml').write_text(
            '[project]\ndependencies=["alpha==1.0"]\n'
            '[project.optional-dependencies]\nintegrations=["beta==2.0"]\n')

    def metadata(self, name):
        return {'alpha': '1.0', 'beta': '2.0'}[name]

    def test_ready_is_metadata_only(self):
        result = launcher.doctor(self.root, self.metadata)
        self.assertEqual(result['status'], 'READY')
        self.assertFalse(result['opens_listener'])
        self.assertFalse(result['installs_packages'])

    def test_missing_or_wrong_package_blocks(self):
        def missing(name):
            raise launcher.metadata.PackageNotFoundError(name)
        for lookup in (missing, lambda name: 'wrong'):
            self.assertEqual(launcher.doctor(self.root, lookup)['status'], 'BLOCKED')

    def test_missing_sprite_blocks(self):
        (self.root / 'companion/assets/jonah.png').unlink()
        result = launcher.doctor(self.root, self.metadata)
        self.assertIn('companion/assets/jonah.png', result['missing_files'])

    def test_old_python_gives_help_without_toml_import(self):
        result = launcher.doctor(self.root, self.metadata, (3, 10, 9))
        self.assertEqual(result['issue'], 'python_3_11_or_newer_required')

    def test_invalid_manifest_blocks(self):
        for text in ('[broken', '[project]\ndependencies=["alpha>=1"]\n[project.optional-dependencies]\nintegrations=[]'):
            (self.root / 'brain/pyproject.toml').write_text(text)
            self.assertEqual(launcher.doctor(self.root, self.metadata)['status'], 'BLOCKED')

    def test_intake_off_unless_explicit(self):
        no = launcher.launch_command(self.root, 0, 1800, False)
        yes = launcher.launch_command(self.root, 0, 1800, True)
        self.assertNotIn('--enable-selection-intake', no)
        self.assertIn('--enable-selection-intake', yes)
        self.assertIn(str(self.root), no)
        self.assertIn('-I', no)

    def test_bad_config_rejected(self):
        for port, seconds, intake in [(True, 1800, False), (-1, 1800, False), (65536, 1800, False),
                                     (0, 59, False), (0, 3601, False), (0, 1800, 'yes')]:
            with self.assertRaises(ValueError):
                launcher.launch_command(self.root, port, seconds, intake)

    def test_credentials_and_pythonpath_not_inherited(self):
        env = launcher.service_environment({'OPENAI_API_KEY': 'fixture', 'HTTP_PROXY': 'fixture',
            'HOME': 'private', 'PATH': 'bad', 'PYTHONPATH': 'bad', 'SystemRoot': 'C:/Windows'})
        self.assertEqual(env['SystemRoot'], 'C:/Windows')
        self.assertFalse(set(env) & {'OPENAI_API_KEY', 'HTTP_PROXY', 'HOME', 'PATH', 'PYTHONPATH'})

    def test_doctor_does_not_start_child(self):
        with patch.object(launcher, 'doctor', return_value={'status': 'READY'}):
            self.assertEqual(launcher.main(['doctor'], root=self.root, run=lambda *a, **kw: self.fail()), 0)

    def test_blocked_start_never_runs(self):
        with patch.object(launcher, 'doctor', return_value={'status': 'BLOCKED'}):
            self.assertEqual(launcher.main(['start'], root=self.root, run=lambda *a, **kw: self.fail()), 2)

    def test_start_propagates_failure_and_intake_flag(self):
        calls = []
        def run(command, **kwargs):
            calls.append((command, kwargs)); return subprocess.CompletedProcess(command, 7)
        with patch.object(launcher, 'doctor', return_value={'status': 'READY'}):
            self.assertEqual(launcher.main(['start', '--enable-selection-intake'], root=self.root, run=run), 7)
        self.assertEqual(len(calls), 1)
        self.assertIn('--enable-selection-intake', calls[0][0])
        self.assertFalse(calls[0][1]['check'])

    def test_start_os_failure_is_bounded(self):
        def run(*a, **kw):
            raise OSError('private fixture')
        with patch.object(launcher, 'doctor', return_value={'status': 'READY'}):
            self.assertEqual(launcher.main(['start'], root=self.root, run=run), 1)
