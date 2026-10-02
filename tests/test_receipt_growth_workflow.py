"""Keep the synthetic long-run storage gate mandatory and its evidence bounded."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReceiptGrowthWorkflowTests(unittest.TestCase):
    def test_fixed_growth_step_is_not_optional(self):
        text = (ROOT / ".github/workflows/companion-fusion-acceptance.yml").read_text()
        start = text.index("      - name: Require linear new receipt storage")
        end = text.index("      - name: Preserve synthetic receipt storage evidence", start)
        step = text[start:end]
        self.assertIn("--rounds 1000 10000", step)
        self.assertIn("set -euo pipefail", step)
        self.assertNotIn("if:", step)
        self.assertNotIn("continue-on-error", step)
        self.assertIn('git rev-parse HEAD > "$RUNNER_TEMP/receipt-growth/source-commit.txt"', step)
        self.assertIn("fix/lossless-receipt-storage-dot-20261002", text)
        self.assertIn("path: ${{ runner.temp }}/receipt-growth/", text)

    def test_actual_growth_cli_smoke_preserves_replay_and_emits_metrics_only(self):
        with tempfile.TemporaryDirectory(prefix="mygpt-growth-cli-") as temporary:
            output = Path(temporary) / "growth.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "brain/scripts/verify_receipt_growth.py"),
                 "--rounds", "2", "20", "--output", str(output)],
                cwd=ROOT, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertTrue(report["accepted"])
            self.assertFalse(report["retention_policy_complete"])
            self.assertEqual(report["network_model_calls"], 0)
            self.assertEqual(len(report["results"]), 4)
            self.assertEqual(len(report["growth"]), 2)
            for row in report["results"]:
                self.assertEqual(row["sessions_cache_keys"], 0)
                self.assertEqual(row["requests_cache_keys"], 0)
                self.assertTrue(row["warm_replay_first_middle_last"])
                self.assertTrue(row["cold_replay_first_middle_last"])
                self.assertTrue(row["warm_conflict_rejected"])
            self.assertEqual(list(Path(temporary).iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
