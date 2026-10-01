"""Actual POSIX launcher -> loopback status -> Ctrl+C shutdown acceptance.

Requires the locked SDK environment. Uses no supplied documents or model calls.
Only test-owned process groups are signalled. Never persists cookies or stdout.
"""
from __future__ import annotations
import argparse
import http.client
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time


def check_mode(root: Path, intake: bool) -> list[str]:
    if os.name != 'posix':
        raise ValueError('posix_acceptance_only')
    command = [sys.executable, str(root / 'run_mygpt.py'), 'start', '--authorization-seconds', '60']
    if intake:
        command.append('--enable-selection-intake')
    process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, start_new_session=True)
    lines = queue.Queue()
    reader = threading.Thread(target=lambda: [lines.put(s) for s in process.stdout], daemon=True)
    reader.start()
    port = None
    checks = []
    prefix = 'intake_on' if intake else 'intake_off'
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('launcher_exited_before_ready')
            try:
                line = lines.get(timeout=.1)
            except queue.Empty:
                continue
            match = re.fullmatch(r'mygpt local brain: http://127\.0\.0\.1:(\d+)\s*', line)
            if match:
                port = int(match[1]); break
        if port is None:
            raise RuntimeError('launcher_startup_timeout')
        checks.append(prefix + ':printed_loopback_ready')
        origin = f'http://127.0.0.1:{port}'
        def call(path, headers=None):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
            try:
                conn.request('GET', path, headers=headers or {})
                response = conn.getresponse()
                return response.status, dict(response.getheaders()), response.read()
            finally:
                conn.close()
        status, headers, _ = call('/host/selection.html')
        assert status == 200
        cookie = headers['Set-Cookie'].split(';')[0]
        checks.append(prefix + ':selection_page_loads')
        status, _, body = call('/api/v1/status', {'Cookie': cookie, 'Origin': origin,
                              'X-MyGPT-Client': 'mygpt-reader-brain-v1'})
        data = json.loads(body)
        assert status == 200 and data['selection_intake_enabled'] is intake
        checks.append(prefix + ':explicit_intake_flag_preserved')
        assert data['test_model'] is True and data['paid_model_calls'] == 0
        assert data['requests_started'] == 0 and not data['live_book_connected']
        checks.append(prefix + ':no_implicit_inference_or_book')
        os.killpg(process.pid, signal.SIGINT)
        assert process.wait(timeout=5) in (0, 130)
        checks.append(prefix + ':ctrl_c_exits')
        try:
            call('/api/v1/status')
        except OSError:
            checks.append(prefix + ':listener_closed')
        else:
            raise AssertionError('test_listener_survived_shutdown')
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=3)
        reader.join(timeout=1)
        process.stdout.close()
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    checks = check_mode(args.root.resolve(), False) + check_mode(args.root.resolve(), True)
    report = {'status': 'PASS', 'scope': 'ACTUAL_POSIX_LAUNCHER_AND_LOOPBACK', 'checks': checks,
              'checks_passed': len(checks), 'paid_model_calls': 0, 'source_text_received': False,
              'windows_device_acceptance': False}
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
