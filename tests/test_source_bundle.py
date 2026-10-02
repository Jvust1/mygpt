"""Actual temporary Git repositories, no remote, no user files or credentials."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch

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


    def commit_files(self, files):
        for name, data in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data if isinstance(data, bytes) else data.encode())
        self.git('add', '.')
        self.git('commit', '-qm', 'source fixture')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()

    def add_submodules(self):
        config = []
        for path, expected in bundle.EXTERNAL_SUBMODULES.items():
            parent = Path(path).parent
            for name in ('LICENSE', 'NOTICE.md'):
                target = self.root / parent / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('synthetic notice fixture\n')
            config.append(f'[submodule "{path}"]\npath = {path}\nurl = {expected["url"]}\n')
        (self.root / '.gitmodules').write_text('\n'.join(config))
        self.git('add', '.')
        for path, expected in bundle.EXTERNAL_SUBMODULES.items():
            self.git('update-index', '--add', '--cacheinfo', f'160000,{expected["commit"]},{path}')
        self.git('commit', '-qm', 'external pins fixture')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()

    def rewrite_manifest(self, change):
        altered = self.base / 'rewritten.zip'
        with zipfile.ZipFile(self.out) as src, zipfile.ZipFile(altered, 'w') as dst:
            for info in src.infolist():
                data = src.read(info)
                if info.filename == bundle.MANIFEST:
                    manifest = json.loads(data)
                    change(manifest)
                    data = json.dumps(manifest).encode()
                dst.writestr(info, data)
        return altered

    def test_android_sources_and_exact_upstream_notices_are_retained(self):
        files = {'android_spike/src/main/java/Example.java': 'class Example {}',
                 'third_party/airi/LICENSE': 'synthetic license',
                 'third_party/airi/NOTICE.md': 'synthetic notice',
                 'third_party/airi/reference/example.ts': 'export const value = 1'}
        self.commit_files(files)
        self.build()
        with zipfile.ZipFile(self.out) as z:
            for path, data in files.items():
                self.assertEqual(z.read(path).decode(), data)
            manifest = json.loads(z.read(bundle.MANIFEST))
            self.assertEqual(manifest['repository'], 'Jvust1/mygpt')
            self.assertEqual(manifest['schema'], 'mygpt.source-bundle.v2')

    def test_missing_upstream_notice_fails_instead_of_silently_packaging(self):
        self.commit_files({'third_party/airi/reference/a.ts': 'x', 'third_party/airi/LICENSE': 'x'})
        with self.assertRaisesRegex(ValueError, 'missing_upstream_license_or_notice'):
            self.build()
        self.assertFalse(self.out.exists())

    def test_external_gitlinks_record_exact_pins_without_fetching_source(self):
        self.add_submodules()
        original = bundle.git
        calls = []
        def capture(root, *args):
            calls.append(args)
            return original(root, *args)
        with patch.object(bundle, 'git', capture):
            result = self.build()
        self.assertEqual(len(result['external_submodules']), 2)
        self.assertFalse(result['submodule_sources_included'])
        self.assertTrue(all(args[0] in {'rev-parse', 'ls-tree', 'cat-file'} for args in calls))
        with zipfile.ZipFile(self.out) as z:
            for path, expected in bundle.EXTERNAL_SUBMODULES.items():
                self.assertFalse(any(name == path or name.startswith(path + '/') for name in z.namelist()))
                self.assertIn({'path': path, **expected, 'source_included': False}, result['external_submodules'])
                self.assertIn(str(Path(path).parent / 'LICENSE'), z.namelist())
        second = self.base / 'second.zip'
        bundle.build(self.root, self.commit, second)
        self.assertEqual(self.out.read_bytes(), second.read_bytes())

    def test_changed_gitlink_pin_is_rejected(self):
        self.add_submodules()
        path = next(iter(bundle.EXTERNAL_SUBMODULES))
        self.git('update-index', '--cacheinfo', f'160000,{"f" * 40},{path}')
        self.git('commit', '-qm', 'wrong pin')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        with self.assertRaisesRegex(ValueError, 'unregistered_submodule_identity'):
            self.build()

    def test_gitmodules_cannot_add_commands_or_change_urls(self):
        self.add_submodules()
        files = {'.gitmodules': (self.root / '.gitmodules').read_bytes()}
        for path in bundle.EXTERNAL_SUBMODULES:
            for name in ('LICENSE', 'NOTICE.md'):
                files[str(Path(path).parent / name)] = b'fixture'
        links = [{'path': path, **item, 'source_included': False}
                 for path, item in bundle.EXTERNAL_SUBMODULES.items()]
        original = files['.gitmodules']
        for bad in (original + b'update = !not-executed\n',
                    original.replace(b'https://github.com/', b'https://example.invalid/'),
                    original + b'[include]\npath = local.cfg\n', b''):
            with self.subTest(config=bad):
                files['.gitmodules'] = bad
                with self.assertRaises(ValueError): bundle.check_submodules(files, links)

    def test_gitlinks_require_matching_config_and_license_notice(self):
        self.add_submodules()
        self.git('rm', '.gitmodules')
        self.git('commit', '-qm', 'missing config')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        with self.assertRaisesRegex(ValueError, 'missing_gitmodules'): self.build()

    def test_submodule_inclusion_claim_cannot_be_forged(self):
        self.add_submodules(); self.build()
        def mutate(m): m['external_submodules'][0]['source_included'] = True
        altered = self.rewrite_manifest(mutate)
        with self.assertRaisesRegex(ValueError, 'submodule_identity_mismatch'):
            bundle.verify(altered, bundle.sha256_file(altered))

    def test_submodule_inventory_cannot_be_dropped(self):
        self.add_submodules(); self.build()
        altered = self.rewrite_manifest(lambda m: m.pop('external_submodules'))
        with self.assertRaises(ValueError): bundle.verify(altered, bundle.sha256_file(altered))

    def test_external_submodule_worktree_files_are_not_bundled(self):
        self.add_submodules()
        path = next(iter(bundle.EXTERNAL_SUBMODULES))
        local = self.root / path / 'private-untracked.txt'
        local.parent.mkdir(parents=True); local.write_text('synthetic untracked fixture')
        self.build()
        with zipfile.ZipFile(self.out) as z:
            self.assertNotIn(str(local.relative_to(self.root)), z.namelist())

    def test_model_and_distribution_binaries_remain_forbidden(self):
        for suffix in ('gguf', 'onnx', 'tflite', 'pt', 'pth', 'apk', 'aar', 'jar', 'sqlite3', 'class', 'so', 'jks', 'keystore', 'log'):
            with self.subTest(suffix=suffix):
                self.assertFalse(bundle.safe_path('android_spike/assets/file.' + suffix))
        self.assertTrue(bundle.safe_path(next(iter(bundle.BUILD_BOOTSTRAPS))))
        for name in ('android_spike/build/a.txt', 'android_llm_spike/.gradle/a.txt',
                     'android_voice_spike/local.properties'):
            self.assertFalse(bundle.safe_path(name))

    def test_existing_wrapper_exception_requires_exact_content(self):
        self.commit_files({next(iter(bundle.BUILD_BOOTSTRAPS)): b'not-the-wrapper'})
        with self.assertRaisesRegex(ValueError, 'build_bootstrap_identity_mismatch'):
            self.build()
        self.assertFalse(self.out.exists())

    def test_legacy_v1_archive_verification_still_supported(self):
        self.build()
        def legacy(m):
            m.update(schema='mygpt.source-bundle.v1', repository='Jvust/mygpt', scope='TRACKED_PROJECT_SOURCE_ONLY')
            m.pop('external_submodules'); m.pop('build_bootstraps')
        altered = self.rewrite_manifest(legacy)
        self.assertEqual(bundle.verify(altered, bundle.sha256_file(altered))['status'], 'PASS')

    def test_v2_repository_and_dependency_claims_are_checked(self):
        self.build()
        altered = self.rewrite_manifest(lambda m: m.update(includes_dependencies=True))
        with self.assertRaisesRegex(ValueError, 'invalid_source_scope'):
            bundle.verify(altered, bundle.sha256_file(altered))


    def test_case_colliding_tracked_paths_fail_before_output(self):
        self.commit_files({'docs/Case.md': 'a', 'docs/case.md': 'b'})
        with self.assertRaisesRegex(ValueError, 'case_colliding_source_paths'): self.build()
        self.assertFalse(self.out.exists())

    def test_archive_alias_and_file_directory_collisions_are_rejected(self):
        self.build()
        for index, names in enumerate([['docs/Case.md', 'docs/case.md'], ['docs/a', 'docs/a/b']]):
            altered = self.base / f'collision-{index}.zip'
            altered.write_bytes(self.out.read_bytes())
            with zipfile.ZipFile(altered, 'a') as z:
                for name in names: bundle.write_entry(z, name, b'fixture')
            with self.assertRaisesRegex(ValueError, 'source_paths|source_collision'):
                bundle.verify(altered, bundle.sha256_file(altered))

    def test_notice_removal_is_rejected_even_with_consistent_outer_hash_and_manifest(self):
        self.commit_files({'third_party/airi/LICENSE': 'fixture', 'third_party/airi/NOTICE.md': 'fixture'})
        self.build()
        removed = 'third_party/airi/NOTICE.md'
        altered = self.base / 'missing-notice.zip'
        with zipfile.ZipFile(self.out) as src, zipfile.ZipFile(altered, 'w') as dst:
            for info in src.infolist():
                if info.filename == removed: continue
                data = src.read(info)
                if info.filename == bundle.MANIFEST:
                    manifest = json.loads(data)
                    manifest['files'] = [e for e in manifest['files'] if e['path'] != removed]
                    data = json.dumps(manifest).encode()
                dst.writestr(info, data)
        with self.assertRaisesRegex(ValueError, 'missing_upstream_license_or_notice'):
            bundle.verify(altered, bundle.sha256_file(altered))


    def test_external_tree_case_alias_is_rejected_with_self_consistent_manifest(self):
        self.add_submodules(); self.build()
        for index, added in enumerate(['third_party/llama.cpp/UPSTREAM/fixture.txt',
                                       'third_party/llama.cpp/UPSTREAM']):
            data = b'synthetic forbidden external source'
            altered = self.base / f'external-case-{index}.zip'
            with zipfile.ZipFile(self.out) as src, zipfile.ZipFile(altered, 'w') as dst:
                for info in src.infolist():
                    original = src.read(info)
                    if info.filename == bundle.MANIFEST:
                        manifest = json.loads(original)
                        manifest['files'].append({'path': added, 'mode': '100644', 'bytes': len(data),
                            'git_blob': bundle.git_blob(data), 'sha256': hashlib.sha256(data).hexdigest()})
                        original = json.dumps(manifest).encode()
                    dst.writestr(info, original)
                bundle.write_entry(dst, added, data)
            with self.assertRaisesRegex(ValueError, 'source_paths|source_collision'):
                bundle.verify(altered, bundle.sha256_file(altered))


if __name__ == '__main__': unittest.main()
