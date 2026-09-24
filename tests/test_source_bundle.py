"""Actual temporary Git repositories, no remote, no user files or credentials."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location('source_bundle', Path(__file__).resolve().parents[1] / 'scripts/source_bundle.py')
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class SourceBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'repo'; self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'local-test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.root / 'README.md').write_text('example\n')
        self.git('add', 'README.md'); self.git('commit', '-qm', 'fixture')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        self.out = self.base / 'source.zip'

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True, timeout=10).stdout

    def build(self):
        return bundle.build(self.root, self.commit, self.out)

    def test_actual_git_and_hashes(self):
        result = self.build()
        self.assertEqual(result['files_verified'], 1)
        self.assertEqual(result['extracted_files'], 0)
        self.assertEqual(bundle.verify(self.out, result['sha256'])['status'], 'PASS')

    def test_repeated_builds_byte_identical(self):
        self.build(); other = self.base / 'second.zip'
        bundle.build(self.root, self.commit, other)
        self.assertEqual(self.out.read_bytes(), other.read_bytes())

    def test_dirty_and_untracked_files_not_copied(self):
        (self.root / 'README.md').write_text('dirty changes')
        (self.root / '.env').write_text('fake-not-a-secret')
        self.build()
        with zipfile.ZipFile(self.out) as z:
            self.assertEqual(z.read('README.md'), b'example\n')
            self.assertNotIn('.env', z.namelist())

    def test_no_overwrite(self):
        self.out.write_bytes(b'keep')
        with self.assertRaises(FileExistsError): self.build()
        self.assertEqual(self.out.read_bytes(), b'keep')

    def test_mutable_ref_rejected(self):
        with self.assertRaises(ValueError): bundle.build(self.root, 'HEAD', self.out)
        self.assertFalse(self.out.exists())

    def test_output_in_repo_rejected(self):
        with self.assertRaises(ValueError): bundle.build(self.root, self.commit, self.root / 'bundle.zip')

    def test_forbidden_paths(self):
        for name in ['../x', '/root', 'host/../x', 'host//a', 'host/a\\b', 'brain/.env', 'brain/.env.local',
                     'host/font.ttf', 'companion/x.woff2', 'host/x.pem', 'brain/x.db', 'docs/NUL.txt',
                     'tests/CON', 'data/messages.json', 'host/node_modules/x.js', 'host/file.', 'host/x.zip']:
            with self.subTest(name=name): self.assertFalse(bundle.safe_path(name))

    def test_symlink_rejected(self):
        (self.root / 'docs').mkdir()
        (self.root / 'docs/link.md').symlink_to('../README.md')
        self.git('add', '.'); self.git('commit', '-qm', 'symlink fixture')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        with self.assertRaises(ValueError): self.build()

    def test_tracked_font_rejected_not_distributed(self):
        (self.root / 'host').mkdir(); (self.root / 'host/font.ttf').write_bytes(b'fake')
        self.git('add', '.'); self.git('commit', '-qm', 'font fixture')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        with self.assertRaises(ValueError): self.build()

    def test_external_hash_required(self):
        result = self.build()
        with self.assertRaises(ValueError): bundle.verify(self.out, '0' * 64)
        with self.assertRaises(ValueError): bundle.verify(self.out, '')

    def test_member_tamper_detected_even_with_new_outer_hash(self):
        self.build(); altered = self.base / 'tampered.zip'
        with zipfile.ZipFile(self.out) as src, zipfile.ZipFile(altered, 'w') as dst:
            for i in src.infolist(): dst.writestr(i, b'changed' if i.filename == 'README.md' else src.read(i))
        with self.assertRaises(ValueError): bundle.verify(altered, bundle.sha256_file(altered))

    def test_extra_member_detected(self):
        self.build()
        with zipfile.ZipFile(self.out, 'a') as z: bundle.write_entry(z, 'docs/extra.md', b'bad')
        with self.assertRaises(ValueError): bundle.verify(self.out, bundle.sha256_file(self.out))

    def test_no_extraction_side_effects(self):
        self.build(); before = set(self.base.rglob('*'))
        bundle.verify(self.out, bundle.sha256_file(self.out))
        self.assertEqual(set(self.base.rglob('*')), before)

    def test_executable_mode_preserved(self):
        path = self.root / 'run_mygpt.py'; path.write_text('pass\n'); path.chmod(0o755)
        self.git('add', '.'); self.git('commit', '-qm', 'executable fixture')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        self.build()
        with zipfile.ZipFile(self.out) as z: self.assertEqual(z.getinfo('run_mygpt.py').external_attr >> 16, 0o100755)


if __name__ == '__main__': unittest.main()
