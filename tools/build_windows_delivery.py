"""Build a runner-local Windows executable; emit synthetic verification evidence.

The frozen package is not a licensed distribution or user-device acceptance.
Linux's full offline suite remains in the calling aggregate workflow.
Explicit --local-package-dir retains local ZIP packaging; CI never publishes it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'mygpt'
FONT_SUFFIXES = {'.ttf', '.otf', '.woff', '.woff2', '.eot', '.ttc'}
# Explicit renderer files only: never copy the whole third_party tree or fonts.
DATA_FILES = (
    ('desktop_ui', 'desktop_ui'), ('host', 'host'), ('companion', 'companion'),
    ('brain/pyproject.toml', 'brain'),
    ('third_party/katex/katex.mjs', 'third_party/katex'),
    ('third_party/katex/LICENSE', 'third_party/katex'),
    ('third_party/katex/NOTICE.md', 'third_party/katex'),
)
KATEX_SHA256 = {
    'katex.mjs': '694a531495903e374957e9a9c904a402e2f413762635df486c4cf6163320d1aa',
    'LICENSE': '766ccc1f306c885aa45542a9846bbd0a505b27a0374f146778171c2254ce18e3',
    'NOTICE.md': '3cd738da115b4dcf06e3a7347c76c8f476d14f2e314e8c1da434f3ab4883e906',
}


def pyinstaller_command():
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
            '--windowed', '--contents-directory', '_internal', '--name', NAME,
            '--exclude-module', 'playwright', '--exclude-module', 'pytest',
            '--exclude-module', 'mcp.cli', '--paths', 'brain',
            '--collect-submodules', 'mygpt_brain', '--collect-all', 'pydantic_ai',
            '--collect-submodules', 'mcp.client', '--collect-submodules', 'mcp.server',
            '--collect-data', 'mcp', '--recursive-copy-metadata', 'pydantic-ai-slim',
            '--recursive-copy-metadata', 'mcp']
    for source, destination in DATA_FILES:
        args.extend(['--add-data', f'{source}:{destination}'])
    return [*args, 'desktop.py']


def verify_bundled_assets(resource_root, source_root=ROOT):
    """Check actual frozen bytes, including unserved legal notices, before boot."""
    sys.path.insert(0, str(source_root / 'brain'))
    from mygpt_brain.local_service import STATIC_FILES

    names = set(STATIC_FILES.values()) | {
        'desktop_ui/index.html', 'desktop_ui/app.js', 'brain/pyproject.toml',
        'third_party/katex/LICENSE', 'third_party/katex/NOTICE.md',
    }
    renderer = resource_root / 'third_party/katex'
    if not renderer.is_dir() or {p.name for p in renderer.iterdir()} != {
        'katex.mjs', 'LICENSE', 'NOTICE.md'
    }:
        raise ValueError('bundled renderer must contain exactly runtime, LICENSE and NOTICE')
    result = []
    for name in sorted(names):
        source, bundled = source_root / name, resource_root / name
        if not bundled.is_file() or bundled.is_symlink():
            raise ValueError(f'missing or unsafe bundled resource: {name}')
        raw = bundled.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if not raw or raw != source.read_bytes():
            raise ValueError(f'bundled resource differs from source: {name}')
        if name.startswith('third_party/katex/') and bundled.name in KATEX_SHA256:
            if digest != KATEX_SHA256[bundled.name]:
                raise ValueError(f'pinned upstream resource changed: {name}')
        result.append({'path': name, 'bytes': len(raw), 'sha256': digest})
    return result


def native_process_options(home):
    """Keep EXE verification independent of the source CWD and Python settings."""
    home = Path(home).resolve()
    env = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME'):
        env.pop(name, None)
    env['LOCALAPPDATA'] = str(home / 'synthetic-profile')
    return {'cwd': home, 'env': env}


def run(args, *, cwd=ROOT, **kwargs):
    subprocess.run(args, check=True, cwd=cwd, **kwargs)


def write_local_archives(package, evidence, destination, report, source_root=ROOT):
    """Optional local-only legacy delivery files, after all native checks pass."""
    destination = destination.resolve()
    if any(destination == root or root in destination.parents
           for root in (package.resolve(), evidence.resolve())):
        raise ValueError('local archive output must be outside package and evidence trees')
    destination.mkdir(parents=True, exist_ok=False)
    commit = report['source_commit']
    shutil.copy2(source_root / 'docs/DESKTOP_DELIVERY.md', package / '使用说明.md')
    (package / 'SOURCE_COMMIT.txt').write_text(commit + '\n', encoding='utf-8')
    manifest = {**report, 'files': []}
    for path in sorted(package.rglob('*')):
        if path.is_file() and path.name != 'PACKAGE_MANIFEST.json':
            manifest['files'].append({'path': path.relative_to(package).as_posix(),
                'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (package / 'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    with zipfile.ZipFile(destination / (NAME + '-Windows-Portable.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                archive.write(path, NAME + '/' + path.relative_to(package).as_posix())
    subprocess.run(['git', 'archive', '--format=zip', commit, '-o',
                    str(destination / (NAME + '-Source-and-Tests.zip'))], check=True, cwd=source_root)
    with zipfile.ZipFile(destination / (NAME + '-Verification.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(evidence.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(evidence).as_posix())
    (destination / 'release.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (destination / 'SHA256SUMS.txt').write_text(''.join(
        hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n'
        for path in sorted(destination.glob('*.zip'))), encoding='utf-8')



def verify_browser_report(browser, exe_sha256):
    """Reject incomplete/fallback reports before calling the native build a pass."""
    if any(browser.get(name) is not True for name in
           ('ok', 'native_math_preview', 'native_text_chat', 'native_text_restart_restore')):
        raise ValueError('native browser math/text/restart checks did not pass')
    if (browser.get('os') != 'win32' or browser.get('browser') != 'Microsoft Edge'
            or not browser.get('browser_version') or browser.get('exe_sha256') != exe_sha256):
        raise ValueError('exact frozen EXE and Microsoft Edge evidence required')
    for key, expected in (('synthetic_provider_calls', 2), ('synthetic_model_calls', 2), ('stopped_provider_connection_attempts', 0),
                          ('live_model_calls', 0), ('javascript_error_count', 0),
                          ('external_request_count', 0)):
        if type(browser.get(key)) is not int or browser[key] != expected:
            raise ValueError('unexpected native verification counter: ' + key)
    text = browser.get('text_chat', {})
    ports = (text.get('first_port'), text.get('second_port'))
    if (text.get('turns') != 2 or text.get('session_id') != 'desktop-local-chat-v1'
            or any(type(port) is not int or not 1 <= port <= 65535 for port in ports)
            or text.get('previous_port_reserved') is not True
            or ports[0] == ports[1] or len(text.get('sqlite_rows', [])) != 4
            or len(set(text.get('request_ids', []))) != 2):
        raise ValueError('two-turn SQLite and new-origin restoration evidence required')
    requests = text.get('read_only_restart_requests', [])
    if (not requests or not any(row.get('path') == '/desktop-api/chat-history' for row in requests)
            or any(row.get('method') != 'GET' or row.get('path') == '/desktop-api/local-chat'
                   for row in requests)):
        raise ValueError('restart must restore history without a chat POST')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    parser.add_argument('--local-package-dir', type=Path,
                        help='Optional NEW local directory for ZIPs; not permission to publish/distribute')
    options = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('native Windows runner required; no cross-platform acceptance')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', options.source_commit) or commit != options.source_commit:
        parser.error('checkout must match the exact expected source commit')
    run(['git', 'diff', '--exit-code', 'HEAD', '--'])
    evidence = options.evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    run(pyinstaller_command())
    package = ROOT / 'dist' / NAME
    removed = []
    for path in sorted(package.rglob('*')):
        if path.is_file() and path.suffix.lower() in FONT_SUFFIXES:
            removed.append(path.relative_to(package).as_posix())
            path.unlink()
    for path in package.rglob('*.css'):
        text = path.read_text(encoding='utf-8', errors='strict')
        cleaned = re.sub(r'@font-face\s*\{[^}]*\}', '', text)
        if cleaned != text:
            path.write_text(cleaned, encoding='utf-8', newline='\n')
    assets = verify_bundled_assets(package / '_internal')
    exe = package / (NAME + '.exe')
    with tempfile.TemporaryDirectory(prefix=NAME + '-native-') as temp:
        smoke = evidence / 'native-smoke.json'
        profile = Path(temp) / 'synthetic-profile'
        try:
            run([str(exe), '--self-test', str(smoke), '--data-dir', str(Path(temp) / 'controller')],
                **native_process_options(Path(temp)), timeout=150)
        finally:
            # Only this runner-created EXE profile, never the user's default boot log.
            log = profile / 'mygptDesktop/boot.log'
            (evidence / 'native-self-test-diagnostics.txt').write_bytes(
                log.read_bytes() if log.is_file() else b'No synthetic native boot output.\n')
        if json.loads(smoke.read_text(encoding='utf-8')).get('ok') is not True:
            raise RuntimeError('native executable smoke failed')
    run([sys.executable, 'tools/desktop_browser_test.py', str(exe), str(evidence)], timeout=360)
    browser = json.loads((evidence / 'browser.json').read_text(encoding='utf-8'))
    exe_sha256 = hashlib.sha256(exe.read_bytes()).hexdigest()
    verify_browser_report(browser, exe_sha256)
    run(['git', 'diff', '--exit-code', 'HEAD', '--'])
    report = {
        'status': 'WINDOWS_NATIVE_MATH_AND_TEXT_CHAT_PASS', 'source_commit': commit,
        'built_on': sys.platform, 'python': sys.version,
        'exe_bytes': exe.stat().st_size, 'exe_sha256': exe_sha256,
        'native_executable_smoke': True, 'native_math_preview': True,
        'native_text_chat': True, 'native_text_restart_restore': True,
        'synthetic_provider_calls': 2, 'synthetic_model_calls': 2, 'live_model_calls': 0,
        'stopped_provider_connection_attempts': 0,
        'font_binaries_distributed': 0, 'excluded_font_count': len(removed),
        'required_resources': assets, 'exe_published': False,
        'actual_user_device_tested': False, 'live_model_quality_accepted': False,
        'distribution_license_verified': False, 'cross_platform_hash_lock_complete': False,
    }
    (evidence / 'build-evidence.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if options.local_package_dir is not None:
        write_local_archives(package, evidence, options.local_package_dir, report)
    print(json.dumps({key: report[key] for key in ('status', 'source_commit', 'exe_sha256')}))


if __name__ == '__main__':
    main()
