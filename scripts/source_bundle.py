"""Deterministic source-only recovery bundles from one immutable Git commit.

No working-tree copying, extraction, network, dependency installation or refs
writes. Internal hashes detect damage; trust still requires an external SHA-256.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

ROOT_FILES = {'.gitignore', 'AGENTS.md', 'SECURITY_POLICY.md', 'README.md',
              'package.json', 'package-lock.json', 'run_mygpt.py', 'START_HERE.md'}
DIRECTORIES = {'brain', 'host', 'companion', 'demo', 'docs', 'governance', 'scripts', 'tests', '.github'}
FORBIDDEN_PARTS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
                   '.env', 'credentials', 'secrets', 'models', 'weights', 'cache'}
FORBIDDEN_EXTENSIONS = {'.ttf', '.otf', '.woff', '.woff2', '.pem', '.key', '.db', '.sqlite',
                        '.pkl', '.pyc', '.zip', '.bin', '.safetensors', '.ckpt'}
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
    if PurePosixPath(name).suffix.lower() in FORBIDDEN_EXTENSIONS:
        return False
    if any(re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', x, re.I) for x in parts):
        return False
    return name in ROOT_FILES or (len(parts) > 1 and parts[0] in DIRECTORIES)


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
    entries, files, total = [], {}, 0
    for row in rows:
        header, path = row.split(b'\t', 1)
        mode, kind, oid = header.decode('ascii').split()
        name = path.decode('utf-8')
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
    manifest = {'schema': 'mygpt.source-bundle.v1', 'repository': 'Jvust2/mygpt',
                'source_commit': commit, 'scope': 'TRACKED_PROJECT_SOURCE_ONLY',
                'includes_dependencies': False, 'files': sorted(entries, key=lambda x: x['path'])}
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
        if not isinstance(manifest, dict) or manifest.get('schema') != 'mygpt.source-bundle.v1' or not re.fullmatch('[0-9a-f]{40}', manifest.get('source_commit', '')):
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
        for entry in entries:
            data = archive.read(entry['path'])
            if (len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']
                    or git_blob(data) != entry['git_blob']
                    or entry['mode'] not in ('100644', '100755')
                    or archive.getinfo(entry['path']).external_attr >> 16 != int(entry['mode'], 8)):
                raise ValueError('member_identity_mismatch')
    return {'status': 'PASS', 'source_commit': manifest['source_commit'], 'files_verified': len(entries),
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
