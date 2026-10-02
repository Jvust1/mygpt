"""Keep the public npm entrypoint complete without changing production tests."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github/workflows'


class NpmEntrypointTests(unittest.TestCase):
    def test_package_uses_node_default_discovery_without_a_file_allowlist(self):
        package = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(package['scripts']['test'], 'node --test')

    def run_discovery_probe(self, succeeds):
        npm = shutil.which('npm')
        self.assertIsNotNone(npm, 'Node and npm are required for repository acceptance')
        with tempfile.TemporaryDirectory(prefix='mygpt-npm-discovery-') as temporary:
            root = Path(temporary)
            # Exercise the actual package entrypoint in an isolated, synthetic tree.
            (root / 'package.json').write_bytes((ROOT / 'package.json').read_bytes())
            nested = root / 'tests/unlisted/nested'
            nested.mkdir(parents=True)
            (root / 'tests/atlas.test.mjs').write_text(
                "import test from 'node:test';\n"
                "test('synthetic atlas baseline', () => {});\n", encoding='utf-8')
            (nested / 'future-feature.test.mjs').write_text(
                "import test from 'node:test';\n"
                "import assert from 'node:assert/strict';\n"
                "import { writeFileSync } from 'node:fs';\n"
                "test('unlisted nested discovery probe', () => {\n"
                "  writeFileSync('discovery-ran.txt', 'SYNTHETIC_TEST_ONLY');\n"
                f"  assert.equal({str(succeeds).lower()}, true);\n"
                "});\n", encoding='utf-8')
            result = subprocess.run([npm, 'test'], cwd=root, capture_output=True,
                                    text=True, encoding='utf-8', timeout=30,
                                    env=dict(os.environ, NO_COLOR='1'))
            output = result.stdout + result.stderr
            self.assertTrue((root / 'discovery-ran.txt').is_file(), output)
            self.assertEqual((root / 'discovery-ran.txt').read_text(), 'SYNTHETIC_TEST_ONLY')
            self.assertRegex(output, r'(?m)^[#ℹ] tests 2\s*$')
            for key in ('skipped', 'todo', 'cancelled'):
                self.assertRegex(output, rf'(?m)^[#ℹ] {key} 0\s*$')
            return result, output

    def test_npm_discovers_a_new_nested_passing_test(self):
        result, output = self.run_discovery_probe(True)
        self.assertEqual(result.returncode, 0, output)
        self.assertRegex(output, r'(?m)^[#ℹ] pass 2\s*$')
        self.assertRegex(output, r'(?m)^[#ℹ] fail 0\s*$')

    def test_npm_propagates_failure_from_a_new_nested_test(self):
        result, output = self.run_discovery_probe(False)
        self.assertNotEqual(result.returncode, 0, output)
        self.assertRegex(output, r'(?m)^[#ℹ] pass 1\s*$')
        self.assertRegex(output, r'(?m)^[#ℹ] fail 1\s*$')

    def test_all_three_acceptance_surfaces_use_the_same_npm_entrypoint(self):
        commands = {
            'companion-fusion-acceptance.yml': '          npm test\n',
            'desktop-delivery.yml': '          npm test 2>&1 | Tee-Object "$env:RUNNER_TEMP/windows-evidence/node-tests.txt"\n',
            'source-delivery.yml': '          npm test 2>&1 | tee "$OUT/recovered-node.txt"\n',
        }
        for name, command in commands.items():
            with self.subTest(workflow=name):
                text = (WORKFLOWS / name).read_text()
                self.assertEqual(text.count(command), 1)
                self.assertNotIn('node --test', text)
                if name == 'desktop-delivery.yml':
                    self.assertIn(command + '          if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }', text)
                elif name == 'source-delivery.yml':
                    self.assertIn('set -euo pipefail', text)
                    self.assertLess(text.index('cd "$SRC"'), text.index(command))

    def test_package_changes_trigger_the_new_aggregate_branch(self):
        text = (WORKFLOWS / 'companion-fusion-acceptance.yml').read_text()
        push = text.split('  push:\n', 1)[1].split('  workflow_dispatch:', 1)[0]
        branches, paths = push.split('    paths:\n', 1)
        self.assertIn('      - fix/npm-discovery-dot-20261002\n', branches)
        self.assertRegex(paths, re.compile(r"^      - 'package\.json'$", re.MULTILINE))
        self.assertIn("      - 'tests/**'", paths)


if __name__ == '__main__':
    unittest.main()
