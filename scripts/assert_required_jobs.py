"""Fail closed on missing, skipped, cancelled or unsuccessful required CI jobs."""
import json
import os
import sys


def assert_required_jobs(raw, required):
    if not required or len(set(required)) != len(required):
        raise ValueError("required job list must be nonempty and unique")
    try:
        needs = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("required job results are not valid JSON") from exc
    if not isinstance(needs, dict) or set(needs) != set(required):
        raise ValueError("required job results do not match the declared gate")
    for name in required:
        result = needs[name]
        if not isinstance(result, dict) or result.get("result") != "success":
            raise ValueError(f"required job did not succeed: {name}")


def main():
    try:
        assert_required_jobs(os.environ.get("REQUIRED_JOB_RESULTS", ""), sys.argv[1:])
    except ValueError as exc:
        print(f"Required job gate FAIL: {exc}", file=sys.stderr)
        return 1
    print("Required job gate PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
