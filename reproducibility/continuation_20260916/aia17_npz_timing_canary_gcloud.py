#!/usr/bin/env python3
"""Resume the existing 17B NPZ canary with Google's native download transport.

No source-script edits, listings, new sample selection, package installation,
Git operations, cloud writes, or training. The original canary verifies all
inputs, object checksums, and NPZ content. Only the download transport changes.
Use: ~/aia17_time_venv/bin/python ~/aia17_npz_timing_canary_gcloud.py

Uses generation-qualified gcloud storage cp downloads, one object at a time.
Child-process-only settings request resumable downloads with 1-MiB chunks,
three retry attempts after an initial failed request, and integrity checking.
Each copy invocation is bounded by a 600-second process wall-time watchdog.
CLI resume trackers / temporary bytes are retained for subsequent runs.
Logical payload caps are NOT cumulative network-traffic or monetary caps.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

VERSION = 'aia17-npz-gcloud-transport-v1'
BASE_SHA256 = '878424c0a74f453396bdba616cd1f1bebcc4667e6cff9c92e0f9419f676d3755'
COPY_TIMEOUT_SECONDS = 600
HEARTBEAT_SECONDS = 15
MAX_LOG_BYTES = 1024**2


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def load_base(path: Path):
    if not path.is_file() or sha(path) != BASE_SHA256:
        raise ValueError('Original aia17_npz_timing_canary.py is missing or changed. '
                         'Keep the original; do not overwrite it or bypass this check.')
    spec = importlib.util.spec_from_file_location('aia17_npz_canary_original', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_json(path: Path, data: dict) -> None:
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write('\n')


def private_env(trackers: Path) -> dict:
    """No gcloud config set: all overrides apply to the child command only."""
    env = os.environ.copy()
    env.update({
        'CLOUDSDK_CORE_DISABLE_PROMPTS': '1',
        'CLOUDSDK_CORE_LOG_HTTP': 'false',
        'CLOUDSDK_CORE_DISABLE_FILE_LOGGING': 'true',
        'CLOUDSDK_CORE_DISABLE_USAGE_REPORTING': 'true',
        'CLOUDSDK_COMPONENT_MANAGER_DISABLE_UPDATE_CHECK': 'true',
        'CLOUDSDK_STORAGE_CHECK_HASHES': 'always',
        'CLOUDSDK_STORAGE_MAX_RETRIES': '3',
        'CLOUDSDK_STORAGE_BASE_RETRY_DELAY': '1',
        'CLOUDSDK_STORAGE_MAX_RETRY_DELAY': '8',
        'CLOUDSDK_STORAGE_EXPONENTIAL_SLEEP_MULTIPLIER': '2',
        'CLOUDSDK_STORAGE_PROCESS_COUNT': '1',
        'CLOUDSDK_STORAGE_THREAD_COUNT': '1',
        'CLOUDSDK_STORAGE_SLICED_OBJECT_DOWNLOAD_THRESHOLD': '0',
        'CLOUDSDK_STORAGE_RESUMABLE_THRESHOLD': '1',
        'CLOUDSDK_STORAGE_DOWNLOAD_CHUNK_SIZE': str(1024**2),
        'CLOUDSDK_STORAGE_TRACKER_FILES_DIRECTORY': str(trackers),
    })
    return env


def stop_own_process_group(proc) -> None:
    """Stop only the subprocess group created for this exact copy command."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


class GcloudDownloadClient:
    def __init__(self, base, transport_root: Path, timeout=COPY_TIMEOUT_SECONDS):
        self.base = base
        self.root = transport_root
        self.timeout = timeout
        self.executable = shutil.which('gcloud')
        if not self.executable:
            raise RuntimeError('gcloud is not on PATH. Use the existing Cloud Shell; '
                               'no packages or new credentials were installed.')
        self.root.mkdir(parents=True, exist_ok=True)
        self.trackers = self.root / 'trackers'
        self.trackers.mkdir(exist_ok=True)
        self.events = []

    def _candidate_check(self, c: dict) -> None:
        b = self.base
        # The original canary validates the complete 18-object payload first.
        b.validate_candidates([c], 1)
        expected_name = c['expected_uri'].removeprefix(f'gs://{b.BUCKET}/')
        if c.get('name') != expected_name:
            raise ValueError('Object-name disagreement; no copy attempted.')
        if not (c.get('crc32c') or c.get('md5Hash')):
            raise ValueError('No locked content checksum; no copy attempted.')

    def _copy(self, c: dict, staged: Path, log: Path) -> float:
        cmd = [self.executable, 'storage', 'cp',
               c['expected_uri'] + '#' + c['generation'], str(staged),
               '--do-not-decompress', f'--project={self.base.PROJECT}',
               '--quiet', '--verbosity=info']
        print(f'    Native resumable download; exact generation {c["generation"]}.', flush=True)
        print('    CLI transport log:', log, flush=True)
        start = time.monotonic()
        with log.open('xb') as f:
            os.chmod(log, 0o600)
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=f,
                                    stderr=subprocess.STDOUT, env=private_env(self.trackers),
                                    start_new_session=True)
            try:
                while True:
                    elapsed = time.monotonic() - start
                    if elapsed >= self.timeout:
                        raise TimeoutError(f'gcloud copy exceeded {self.timeout:g} seconds; '
                                           f'resume files retained. Log: {log}')
                    try:
                        rc = proc.wait(timeout=min(HEARTBEAT_SECONDS, self.timeout-elapsed))
                        break
                    except subprocess.TimeoutExpired:
                        elapsed = time.monotonic() - start
                        # File sizes are progress clues, NOT verified byte counts.
                        sizes = sum(p.stat().st_size for p in staged.parent.iterdir()
                                    if p.is_file() and p.name != 'object_contract.json')
                        print(f'    Download still running: {elapsed:.0f}s; '
                              f'local staging files {sizes/1024**2:.2f} MiB '
                              '(unverified).', flush=True)
                        if log.stat().st_size > MAX_LOG_BYTES:
                            raise RuntimeError(f'Copy log exceeded 1 MiB safety limit. Log: {log}')
                        if sizes > int(c['object_bytes']) + 8*1024**2:
                            raise RuntimeError('Staging size exceeds the small-canary allowance; '
                                               'no content will be loaded.')
            except BaseException:
                stop_own_process_group(proc)
                raise
        if rc != 0:
            print('    ===== GCLOUD ERROR TAIL =====', flush=True)
            tail = log.read_bytes()[-6000:].decode('utf-8', errors='replace')
            print(tail, flush=True)
            raise RuntimeError(f'gcloud download failed with exit code {rc}. '
                               'No broader permission, billing, or absence conclusion is made. '
                               f'Keep the error for review. Log: {log}')
        return time.monotonic()-start

    def download(self, c: dict, partial: Path) -> None:
        self._candidate_check(c)
        partial = Path(partial)
        if partial.exists() or partial.is_symlink():
            raise ValueError('Unexpected existing destination; refusing overwrite.')
        key = hashlib.sha256((c['expected_uri']+'#'+c['generation']).encode()).hexdigest()
        stage_dir = self.root/'staging'/key
        stage_dir.mkdir(parents=True, exist_ok=True)
        staged = stage_dir/'payload.npz'
        contract = {k: c[k] for k in ('expected_uri', 'generation', 'object_bytes')}
        contract.update({k: c.get(k, '') for k in ('crc32c', 'md5Hash')})
        contract_path = stage_dir/'object_contract.json'
        if contract_path.exists():
            if self.base.read_json(contract_path) != contract:
                raise ValueError('Native-download cache contract differs; no mixing versions.')
        else:
            if any(stage_dir.iterdir()):
                raise ValueError('Unidentified staging files; refusing reuse.')
            write_json(contract_path, contract)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        logs = self.root/'logs'; logs.mkdir(exist_ok=True)
        log = logs/f'{c["sample_id"]}_{stamp}.log'
        event = {'sample_id': c['sample_id'], 'uri': c['expected_uri'],
                 'generation': c['generation'], 'transport': VERSION,
                 'status': 'STARTED', 'log': None}
        self.events.append(event)
        try:
            if staged.is_symlink():
                raise ValueError('Unexpected staging symlink; refusing reuse.')
            if staged.exists():
                self.base.check_object(staged, c)
                print('    Verified a completed native-transfer file; reusing it.', flush=True)
                event['completed_native_file_reused'] = True
            else:
                event['log'] = str(log)
                event['elapsed_seconds'] = self._copy(c, staged, log)
                # The original canary checks again before its ordinary receipt is written.
                self.base.check_object(staged, c)
            os.replace(staged, partial)
            event['status'] = 'TRANSFER_COMPLETE_LOCKED_CHECKSUMS_PASSED'
            print('    Transfer complete; size and locked checksums passed.', flush=True)
        except BaseException as exc:
            event['status'] = 'TRANSFER_STOPPED'
            event['error_type'] = type(exc).__name__
            event['error'] = str(exc)[:2000]
            raise
        finally:
            write_json(logs/f'{c["sample_id"]}_{stamp}.json', event)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original', type=Path, default=Path.home()/'aia17_npz_timing_canary.py')
    p.add_argument('--repo', type=Path, default=Path.home()/'solar_flare_aia')
    p.add_argument('--inventory', type=Path,
                   default=Path.home()/'aia17_metadata_stage1/archive_reconciliation_v1')
    p.add_argument('--report-dir', type=Path)
    p.add_argument('--work', type=Path,
                   default=Path.home()/'aia17_metadata_stage1/npz_timing_canary_v1')
    args = p.parse_args()
    try:
        base = load_base(args.original.expanduser().resolve())
        work = args.work.expanduser().resolve()
        repo = args.repo.expanduser().resolve()
        if repo == work or repo in work.parents:
            raise ValueError('The canary cache must remain outside the Git checkout.')
        print('===== NATIVE GCLOUD DOWNLOAD RESUME =====', flush=True)
        print('Original script unchanged; existing inventory/candidates/checksums reused.', flush=True)
        print('Same 18-object maximum and 128-MiB logical payload cap. '
              'Retries can transfer additional bytes; not a monetary cap.', flush=True)
        print('Only the transport changes: native resumable cp, sequential, '
              '1-MiB chunks, up to 3 retries/request, 600s/copy watchdog.', flush=True)
        client = GcloudDownloadClient(base, work/'transport_gcloud_v1')
        # All original selection checks, clock checks and analysis remain in use.
        return base.run(args, client=client)
    except KeyboardInterrupt:
        print('\nSTOP: interrupted; existing verified files and CLI resume files retained.', file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'\nSTOP: {exc}', file=sys.stderr)
        print('No archive relisting, source changes, cloud writes, or training.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
