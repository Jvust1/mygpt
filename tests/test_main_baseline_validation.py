"""Exercise the actual retained main workflow, with synthetic filenames only."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


def scan_script():
    lines = (ROOT / ".github/workflows/validate.yml").read_text().splitlines()
    step = next(i for i, line in enumerate(lines) if "name: Check for accidentally committed secret files" in line)
    start = next(i for i in range(step + 1, len(lines)) if lines[i].strip() == "run: |") + 1
    body = []
    for line in lines[start:]:
        if line.strip() and len(line) - len(line.lstrip()) < 10:
            break
        body.append(line)
    return textwrap.dedent("\n".join(body)) + "\n"


@unittest.skipUnless(shutil.which("bash"), "retained baseline workflow runs on Bash/Ubuntu")
class MainBaselineValidationTests(unittest.TestCase):
    def run_scan(self, paths=(), prefix=""):
        with tempfile.TemporaryDirectory(prefix="mygpt-baseline-scan-") as temporary:
            for name in paths:
                path = Path(temporary, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("SYNTHETIC_TEST_SENTINEL_NOT_A_SECRET\n")
            return subprocess.run([shutil.which("bash"), "-e", "-o", "pipefail", "-c", prefix + scan_script()],
                                  cwd=temporary, text=True, capture_output=True, timeout=5)

    def test_clean_tree_and_existing_exemptions_pass(self):
        result = self.run_scan(["README.md", ".env.example", "nested/.env.example", ".git/ignored.key"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout + result.stderr, "")

    def test_intended_prohibited_paths_fail_without_logging_contents(self):
        for path in [".env", "nested/.env", ".env.local", "nested/.env.example.local", "id.pem", "nested/id.key"]:
            with self.subTest(path=path):
                result = self.run_scan([path])
                self.assertEqual(result.returncode, 1)
                self.assertIn("Secret-like files detected", result.stdout)
                self.assertEqual(result.stderr, "")
                self.assertNotIn("SYNTHETIC_TEST_SENTINEL", result.stdout + result.stderr)
                self.assertNotIn(path, result.stdout + result.stderr)

    def test_find_execution_failure_is_not_a_false_green(self):
        result = self.run_scan(prefix="find() { return 42; }\n")
        self.assertEqual(result.returncode, 42)
        self.assertNotIn("Secret-like files detected", result.stdout)


class SourceBaselineScopeTests(unittest.TestCase):
    def test_default_private_companion_state_is_git_ignored(self):
        with tempfile.TemporaryDirectory(prefix="mygpt-ignore-fixture-") as temporary:
            subprocess.run(["git", "init", "-q", temporary], check=True, capture_output=True)
            Path(temporary, ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
            for path in [".mygpt-local/companion.token", "brain/.mygpt-local/memory.sqlite3",
                         "brain/.mygpt-local/chat.sqlite3"]:
                result = subprocess.run(["git", "-c", f"core.excludesfile={os.devnull}",
                                         "check-ignore", "--no-index", "-q", path],
                                        cwd=temporary, capture_output=True)
                self.assertEqual(result.returncode, 0, path)

    def test_exact_main_documents_are_allowed_without_broadening_root_scope(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("main_source_bundle_test", ROOT / "scripts/source_bundle.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for path in ["CONTRIBUTING.md", "SECURITY.md"]:
            self.assertTrue(module.safe_path(path))
            self.assertTrue((ROOT / path).is_file())
        for path in ["private.md", "security.md", "SECURITY.md.env", ".env", "private.key"]:
            self.assertFalse(module.safe_path(path))


if __name__ == "__main__":
    unittest.main()
