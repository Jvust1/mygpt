"""Source-tree launcher. Doctor is read-only; start opens only the local test service.

Never installs dependencies, opens a browser, reads credentials or chooses a live
provider. Python 3.11+ is required. Each explicit start owns one child process.
"""
from __future__ import annotations
import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REQUIRED_FILES = (
    'brain/pyproject.toml', 'brain/mygpt_brain/local_service.py',
    'brain/mygpt_brain/local_engine.py', 'host/brain.html', 'host/brain.js',
    'host/selection.html', 'host/selection.js', 'host/controller.js',
    'host/fixtures.js', 'companion/mygpt-pet.js', 'companion/assets/jonah.png',
)


def doctor(root: Path = ROOT, lookup=metadata.version, python_version=None) -> dict:
    version = sys.version_info[:3] if python_version is None else python_version
    missing_files = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    checks = []
    issue = None
    if version < (3, 11):
        issue = 'python_3_11_or_newer_required'
    else:
        try:
            import tomllib
            project = tomllib.loads((root / 'brain/pyproject.toml').read_text('utf-8'))['project']
            requirements = project['dependencies'] + project['optional-dependencies']['integrations']
            pins = {}
            for requirement in requirements:
                match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)', requirement)
                if not match:
                    raise ValueError('expected_exact_pin')
                name, expected = match.groups()
                if name in pins and pins[name] != expected:
                    raise ValueError('conflicting_pin')
                pins[name] = expected
            for name, expected in sorted(pins.items()):
                try:
                    actual = lookup(name)
                except metadata.PackageNotFoundError:
                    actual = None
                checks.append({'package': name, 'expected': expected, 'installed': actual,
                               'matches': actual == expected})
        except (OSError, ValueError, KeyError, TypeError):
            issue = 'dependency_manifest_unreadable_or_invalid'
    ready = not missing_files and not issue and bool(checks) and all(x['matches'] for x in checks)
    return {'schema': 'mygpt.launcher-doctor.v1', 'status': 'READY' if ready else 'BLOCKED',
            'python': '.'.join(map(str, version)), 'missing_files': missing_files,
            'dependencies': checks, 'issue': issue, 'opens_listener': False,
            'installs_packages': False, 'live_model_enabled': False,
            'note': 'READY checks files and package metadata, not a service/browser/device acceptance.',
            'instructions': 'START_HERE.md'}


def service_environment(source=None) -> dict:
    source = os.environ if source is None else source
    allowed = ('SYSTEMROOT', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR')
    result = {k: source[k] for k in allowed if k in source}
    result.update(PYTHONUTF8='1', PYTHONNOUSERSITE='1', OTEL_SDK_DISABLED='true',
                  DO_NOT_TRACK='1', LANG='C.UTF-8')
    return result


def launch_command(root: Path, port: int, seconds: int, intake: bool) -> list[str]:
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('invalid_port')
    if type(seconds) is not int or not 60 <= seconds <= 3600:
        raise ValueError('invalid_authorization_duration')
    if type(intake) is not bool:
        raise ValueError('invalid_intake_choice')
    # Only this known module is runnable; source path is an argv value, not code.
    code = ("import runpy,sys; from pathlib import Path; "
            "root=Path(sys.argv.pop(1)); sys.path.insert(0,str(root/'brain')); "
            "runpy.run_module('mygpt_brain.local_service',run_name='__main__')")
    args = [sys.executable, '-I', '-c', code, str(root.resolve()),
            '--port', str(port), '--authorization-seconds', str(seconds)]
    if intake:
        args.append('--enable-selection-intake')
    return args


def main(argv=None, *, root=ROOT, run=subprocess.run) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'start'], nargs='?', default='doctor')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--authorization-seconds', type=int, default=1800)
    parser.add_argument('--enable-selection-intake', action='store_true')
    args = parser.parse_args(argv)
    try:
        command = launch_command(root, args.port, args.authorization_seconds, args.enable_selection_intake)
    except ValueError as error:
        parser.error(str(error))
    report = doctor(root)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if report['status'] != 'READY':
        return 2
    if args.command == 'doctor':
        return 0
    print('Local TestModel only. Open /host/selection.html for opted-in input, '
          'or /host/brain.html for fixed samples. Ctrl+C stops this service.', flush=True)
    try:
        result = run(command, cwd=root, env=service_environment(), check=False)
        return result.returncode
    except KeyboardInterrupt:
        return 130
    except OSError:
        print('Service process could not start; see START_HERE.md.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
