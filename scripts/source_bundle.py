"""Deterministic source-only recovery bundles from one immutable Git commit.

No working-tree copying, extraction, network, dependency installation or refs
writes. Internal hashes detect damage; trust still requires an external SHA-256.
"""
from __future__ import annotations
import argparse
import configparser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

ROOT_FILES = {'.gitmodules', '.gitignore', '.gitattributes', 'AGENTS.md', 'SECURITY_POLICY.md', 'README.md',
              'package.json', 'package-lock.json', 'run_mygpt.py', 'START_HERE.md',
              'desktop.py', 'desktop_adapter.py', 'desktop_runtime.py', 'desktop_state.py',
              'desktop_workspace.py'}
DIRECTORIES = {'brain', 'host', 'companion', 'demo', 'docs', 'governance', 'scripts', 'tests', '.github',
               'desktop_ui', 'tools', 'android_spike', 'android_llm_spike',
               'android_voice_spike', 'third_party'}
FORBIDDEN_PARTS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
                   '.env', 'credentials', 'secrets', 'models', 'weights', 'cache',
                   'build', '.gradle', 'local.properties'}
FORBIDDEN_EXTENSIONS = {'.ttf', '.otf', '.woff', '.woff2', '.pem', '.key', '.db', '.sqlite',
                        '.pkl', '.pyc', '.zip', '.bin', '.safetensors', '.ckpt', '.sqlite3',
                        '.gguf', '.onnx', '.tflite', '.pt', '.pth', '.apk', '.aar', '.jar',
                        '.class', '.so', '.dll', '.dylib', '.exe', '.o', '.a', '.jks', '.keystore', '.log'}
# The sole already-tracked build bootstrap binary. Never relax the jar denylist.
BUILD_BOOTSTRAPS = {
    'android_llm_spike/gradle/wrapper/gradle-wrapper.jar':
        'e996d452d2645e70c01c11143ca2d3742734a28da2bf61f25c82bdc288c9e637',
}
# Metadata only: no clone, submodule update, checkout, or dependency execution.
EXTERNAL_SUBMODULES = {
    'third_party/llama.cpp/upstream': {
        'url': 'https://github.com/ggml-org/llama.cpp.git',
        'commit': 'ba0ba54d93b25faf1e149f4ccedd3e9d84798563',
    },
    'third_party/sherpa-onnx/upstream': {
        'url': 'https://github.com/k2-fsa/sherpa-onnx.git',
        'commit': '040afe360a38e25daaa325ce8889abf93ea02609',
    },
}
MANIFEST = 'SOURCE_MANIFEST.json'
MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_FILES = 512


def safe_path(name: str) -> bool:
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.@/-]{1,240}', name):
        return False
    parts = name.split('/')
    if any(x in ('', '.', '..') or x.endswith(('.', ' ')) for x in parts):
        return False
    if any(x.lower() in FORBIDDEN_PARTS or x.lower().startswith('.env.') for x in parts):
        return False
    if PurePosixPath(name).suffix.lower() in FORBIDDEN_EXTENSIONS and name not in BUILD_BOOTSTRAPS:
        return False
    if any(re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', x, re.I) for x in parts):
        return False
    return name in ROOT_FILES or (len(parts) > 1 and parts[0] in DIRECTORIES)



def check_portable_names(names) -> None:
    """Reject aliases that would overwrite files during Windows recovery."""
    lowered = [name.casefold() for name in names]
    keys = set(lowered)
    if len(keys) != len(lowered):
        raise ValueError('case_colliding_source_paths')
    for name in lowered:
        parts = name.split('/')
        if any('/'.join(parts[:i]) in keys for i in range(1, len(parts))):
            raise ValueError('file_directory_source_collision')


def check_submodules(files: dict[str, bytes], links: list[dict]) -> None:
    """Validate the two recorded external Gitlinks without consulting the network."""
    seen = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != {'path', 'url', 'commit', 'source_included'}:
            raise ValueError('invalid_submodule_reference')
        path = link['path']
        if not isinstance(path, str) or path in seen or path not in EXTERNAL_SUBMODULES:
            raise ValueError('unregistered_submodule')
        expected = EXTERNAL_SUBMODULES[path]
        if (link['url'] != expected['url'] or link['commit'] != expected['commit']
                or link['source_included'] is not False):
            raise ValueError('submodule_identity_mismatch')
        if any(name == path or name.startswith(path + '/') for name in files):
            raise ValueError('submodule_source_must_remain_external')
        parent = str(PurePosixPath(path).parent)
        if not all(parent + '/' + name in files for name in ('LICENSE', 'NOTICE.md')):
            raise ValueError('missing_submodule_license_or_notice')
        seen.add(path)
    raw = files.get('.gitmodules')
    if raw is None:
        if links:
            raise ValueError('missing_gitmodules')
        return
    config = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        config.read_string(raw.decode('utf-8'))
        if config.defaults() or len(config.sections()) != len(links):
            raise ValueError('unexpected_gitmodules_config')
        configured = set()
        for section in config.sections():
            match = re.fullmatch(r'submodule "([^"\n]+)"', section)
            if not match or set(config[section]) != {'path', 'url'}:
                raise ValueError('unexpected_gitmodules_config')
            path = config[section]['path']
            if (path != match[1] or path not in seen or path in configured
                    or config[section]['url'] != EXTERNAL_SUBMODULES[path]['url']):
                raise ValueError('gitmodules_reference_mismatch')
            configured.add(path)
        if configured != seen:
            raise ValueError('gitmodules_reference_mismatch')
    except (configparser.Error, UnicodeDecodeError) as error:
        raise ValueError('invalid_gitmodules') from error


def check_notices(files: dict[str, bytes]) -> None:
    groups = {name.split('/')[1] for name in files if name.startswith('third_party/')}
    for group in groups:
        if not all(f'third_party/{group}/{name}' in files for name in ('LICENSE', 'NOTICE.md')):
            raise ValueError('missing_upstream_license_or_notice')


def check_bootstraps(files: dict[str, bytes]) -> list[dict]:
    entries = []
    for path, expected in BUILD_BOOTSTRAPS.items():
        if path in files:
            if hashlib.sha256(files[path]).hexdigest() != expected:
                raise ValueError('build_bootstrap_identity_mismatch')
            entries.append({'path': path, 'sha256': expected})
    return entries


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True,
                          timeout=30).stdout


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_entry(archive: zipfile.ZipFile, name: str, data: bytes, mode: str = '100644') -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = int(mode, 8) << 16
    info.compress_type = zipfile.ZIP_STORED
    archive.writestr(info, data)


def build(root: Path, commit: str, output: Path) -> dict:
    root, output = root.resolve(), output.absolute()
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('immutable_commit_sha_required')
    if output.resolve().is_relative_to(root):
        raise ValueError('output_must_be_outside_repository')
    actual = git(root, 'rev-parse', '--verify', commit + '^{commit}').decode().strip()
    if actual != commit:
        raise ValueError('commit_identity_mismatch')
    rows = git(root, 'ls-tree', '-r', '-z', commit).split(b'\0')
    rows = [r for r in rows if r]
    if not 1 <= len(rows) <= MAX_FILES:
        raise ValueError('source_file_count_limit')
    entries, files, links, total = [], {}, [], 0
    for row in rows:
        header, path = row.split(b'\t', 1)
        mode, kind, oid = header.decode('ascii').split()
        name = path.decode('utf-8')
        if kind == 'commit' and mode == '160000':
            expected = EXTERNAL_SUBMODULES.get(name)
            if expected is None or oid != expected['commit']:
                raise ValueError('unregistered_submodule_identity')
            links.append({'path': name, **expected, 'source_included': False})
            continue
        if not safe_path(name) or kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('unsafe_or_unsupported_tracked_path')
        size = int(git(root, 'cat-file', '-s', oid))
        total += size
        if size > MAX_FILE or total > MAX_TOTAL:
            raise ValueError('source_size_limit')
        data = git(root, 'cat-file', 'blob', oid)
        if len(data) != size or git_blob(data) != oid:
            raise ValueError('git_blob_mismatch')
        files[name] = data
        entries.append({'path': name, 'mode': mode, 'bytes': size, 'git_blob': oid,
                        'sha256': hashlib.sha256(data).hexdigest()})
    check_portable_names([*files, *(link['path'] for link in links)])
    check_submodules(files, links)
    check_notices(files)
    bootstraps = check_bootstraps(files)
    manifest = {'schema': 'mygpt.source-bundle.v2', 'repository': 'Jvust1/mygpt',
                'source_commit': commit,
                'scope': 'TRACKED_PROJECT_SOURCE_WITH_EXTERNAL_SUBMODULE_REFERENCES',
                'includes_dependencies': False,
                'external_submodules': sorted(links, key=lambda x: x['path']),
                'build_bootstraps': bootstraps,
                'files': sorted(entries, key=lambda x: x['path'])}
    raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    with output.open('xb') as stream, zipfile.ZipFile(stream, 'w') as archive:
        for entry in manifest['files']:
            write_entry(archive, entry['path'], files[entry['path']], entry['mode'])
        write_entry(archive, MANIFEST, raw)
    result = verify(output, sha256_file(output))
    result['sha256'] = sha256_file(output)
    result['archive_bytes'] = output.stat().st_size
    return result


def verify(path: Path, expected_sha256: str) -> dict:
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('external_sha256_required')
    if path.stat().st_size > MAX_TOTAL + 2 * 1024 * 1024:
        raise ValueError('archive_size_limit')
    if sha256_file(path) != expected_sha256:
        raise ValueError('archive_hash_mismatch')
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        check_portable_names(names)
        if len(names) != len(set(names)) or not 2 <= len(names) <= MAX_FILES + 1:
            raise ValueError('invalid_member_set')
        total = 0
        for info in infos:
            total += info.file_size
            mode = info.external_attr >> 16
            if (info.filename != MANIFEST and not safe_path(info.filename)) or stat.S_ISLNK(mode):
                raise ValueError('unsafe_archive_member')
            if info.file_size > MAX_FILE or total > MAX_TOTAL or info.flag_bits & 1:
                raise ValueError('archive_member_limit')
        raw = archive.read(MANIFEST)
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or manifest.get('schema') not in ('mygpt.source-bundle.v1', 'mygpt.source-bundle.v2') or not re.fullmatch('[0-9a-f]{40}', manifest.get('source_commit', '')):
            raise ValueError('invalid_manifest')
        entries = manifest.get('files', [])
        if not isinstance(entries, list) or len(entries) != len(names) - 1:
            raise ValueError('manifest_member_mismatch')
        if any(not isinstance(e, dict) or not isinstance(e.get('path'), str)
               or type(e.get('bytes')) is not int for e in entries):
            raise ValueError('invalid_manifest_entry')
        indexed = [e['path'] for e in entries]
        if len(indexed) != len(set(indexed)) or set(names) != set(indexed) | {MANIFEST}:
            raise ValueError('manifest_member_mismatch')
        files = {}
        for entry in entries:
            data = archive.read(entry['path'])
            files[entry['path']] = data
            if (len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']
                    or git_blob(data) != entry['git_blob']
                    or entry['mode'] not in ('100644', '100755')
                    or archive.getinfo(entry['path']).external_attr >> 16 != int(entry['mode'], 8)):
                raise ValueError('member_identity_mismatch')
        links = manifest.get('external_submodules', [])
        if not isinstance(links, list):
            raise ValueError('invalid_submodule_references')
        check_submodules(files, links)
        check_portable_names([*files, *(link['path'] for link in links)])
        check_notices(files)
        bootstraps = check_bootstraps(files)
        if manifest['schema'] == 'mygpt.source-bundle.v2':
            if (manifest.get('repository') != 'Jvust1/mygpt'
                    or manifest.get('scope') != 'TRACKED_PROJECT_SOURCE_WITH_EXTERNAL_SUBMODULE_REFERENCES'
                    or manifest.get('includes_dependencies') is not False
                    or manifest.get('build_bootstraps') != bootstraps):
                raise ValueError('invalid_source_scope')
        elif links or bootstraps:
            raise ValueError('unsupported_legacy_dependency_metadata')
    return {'status': 'PASS', 'source_commit': manifest['source_commit'], 'files_verified': len(entries),
            'external_submodules': links, 'build_bootstraps': bootstraps,
            'submodule_sources_included': False,
            'extracted_files': 0, 'authenticity': 'requires_trusted_external_hash'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build_args = sub.add_parser('build')
    build_args.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    build_args.add_argument('--commit', required=True)
    build_args.add_argument('--output', type=Path, required=True)
    verify_args = sub.add_parser('verify')
    verify_args.add_argument('archive', type=Path)
    verify_args.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        result = build(args.root, args.commit, args.output) if args.command == 'build' else verify(args.archive, args.sha256)
        print(json.dumps(result, sort_keys=True)); return 0
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__})); return 1


if __name__ == '__main__':
    raise SystemExit(main())
