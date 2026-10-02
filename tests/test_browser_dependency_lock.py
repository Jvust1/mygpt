"""Offline regression checks for the bounded Linux browser-tools npm lock.

Real npm ci, independent caches, and negative installs are separate acceptance
experiments. These tests do not claim to execute npm's integrity verification.
"""
import base64
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / 'tools/browser'
WORKFLOW = ROOT / '.github/workflows/companion-fusion-acceptance.yml'


class BrowserDependencyLockTests(unittest.TestCase):
    def setUp(self):
        self.package = json.loads((BROWSER / 'package.json').read_text())
        self.lock = json.loads((BROWSER / 'package-lock.json').read_text())
        self.packages = self.lock['packages']
        self.workflow = WORKFLOW.read_text()

    def test_only_the_existing_exact_direct_dependency_is_requested(self):
        self.assertEqual(self.package, {
            'name': 'mygpt-browser-tools', 'version': '0.1.0', 'private': True,
            'dependencies': {'playwright': '1.62.1'},
        })
        self.assertEqual(self.lock['lockfileVersion'], 3)
        self.assertEqual(self.lock['name'], self.package['name'])
        self.assertEqual(self.lock['version'], self.package['version'])
        self.assertEqual(self.packages['']['dependencies'], self.package['dependencies'])

    def test_the_complete_recorded_closure_remains_small_and_exact(self):
        expected = {'node_modules/playwright': '1.62.1',
                    'node_modules/playwright-core': '1.62.1',
                    'node_modules/fsevents': '2.3.2'}
        self.assertEqual(set(self.packages), {'', *expected})
        for path, version in expected.items():
            with self.subTest(package=path):
                self.assertEqual(self.packages[path]['version'], version)
                self.assertNotIn('link', self.packages[path])
        self.assertEqual(self.packages['node_modules/playwright']['dependencies'],
                         {'playwright-core': '1.62.1'})
        for path in ('node_modules/playwright-core', 'node_modules/fsevents'):
            self.assertFalse(self.packages[path].get('dependencies'))
            self.assertFalse(self.packages[path].get('optionalDependencies'))

    def test_each_registry_package_has_canonical_url_and_sha512_sri(self):
        for path, package in self.packages.items():
            if not path:
                continue
            with self.subTest(package=path):
                name = path.removeprefix('node_modules/')
                self.assertEqual(package['resolved'],
                                 f"https://registry.npmjs.org/{name}/-/{name}-{package['version']}.tgz")
                self.assertRegex(package['integrity'], r'^sha512-[A-Za-z0-9+/]{86}==$')
                self.assertEqual(len(base64.b64decode(package['integrity'][7:], validate=True)), 64)

    def test_darwin_only_optional_metadata_is_preserved_not_installed_on_linux(self):
        self.assertEqual(self.packages['node_modules/playwright']['optionalDependencies'],
                         {'fsevents': '2.3.2'})
        optional = self.packages['node_modules/fsevents']
        self.assertIs(optional['optional'], True)
        self.assertEqual(optional['os'], ['darwin'])
        for name in ('playwright', 'playwright-core'):
            self.assertFalse(self.packages['node_modules/' + name].get('optional'))
            self.assertFalse(self.packages['node_modules/' + name].get('os'))

    def test_workflow_copies_both_files_and_uses_npm_ci(self):
        step = self.workflow.split('      - name: Verify actual local Book math preview in Chromium\n', 1)[1]
        step = step.split('\n      - name:', 1)[0]
        self.assertIn('set -euo pipefail', step)
        copy = 'cp tools/browser/package.json tools/browser/package-lock.json "$RUNNER_TEMP/mygpt-browser/"'
        install = 'npm ci --prefix "$RUNNER_TEMP/mygpt-browser" --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org'
        self.assertIn('mkdir -p "$RUNNER_TEMP/mygpt-browser"', step)
        self.assertIn(copy, step)
        self.assertIn(install, step)
        self.assertLess(step.index(copy), step.index(install))
        self.assertNotIn('npm install', step)
        self.assertNotIn('continue-on-error', step)
        self.assertNotIn('|| true', step)
        self.assertIn('export NODE_PATH="$RUNNER_TEMP/mygpt-browser/node_modules"', step)
        self.assertIn('export MYGPT_CHROMIUM_PATH="$(command -v google-chrome)"', step)
        self.assertIn('test -x "$MYGPT_CHROMIUM_PATH"', step)
        self.assertIn('MYGPT_TEST_OUTPUT="$RUNNER_TEMP/math-preview" node tests/math-preview-browser.cjs', step)

    def test_browser_lock_changes_trigger_the_bounded_branch(self):
        push = self.workflow.split('  push:\n', 1)[1].split('  workflow_dispatch:', 1)[0]
        branches, paths = push.split('    paths:\n', 1)
        self.assertIn('      - fix/browser-tool-lock-dot-20261002\n', branches)
        self.assertRegex(paths, re.compile(r"^      - 'tools/browser/\*\*'$", re.MULTILINE))
        self.assertIn("      - 'tests/**'", paths)

    def test_source_recovery_includes_the_two_lock_inputs(self):
        from scripts.source_bundle import safe_path
        self.assertTrue(safe_path('tools/browser/package.json'))
        self.assertTrue(safe_path('tools/browser/package-lock.json'))
        root_package = json.loads((ROOT / 'package.json').read_text())
        self.assertNotIn('dependencies', root_package)
        self.assertNotIn('devDependencies', root_package)
        self.assertFalse((ROOT / 'package-lock.json').exists())


if __name__ == '__main__':
    unittest.main()
