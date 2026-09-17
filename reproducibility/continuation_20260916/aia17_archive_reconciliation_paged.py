#!/usr/bin/env python3
"""Resume the existing 17B archive inventory using explicit Cloud Storage pages.

Uses the SAME target validation, archive roots, classification, cache and report
writer as the checksum-verified original aia17_archive_reconciliation.py. Only
its listing transport is replaced, for this process; the original file is not
edited. Authenticates through the existing gcloud login, holding the access token
in process memory only. Sends authenticated HTTPS GET requests ONLY to the
Cloud Storage objects.list endpoint for the 17 agreed yearly prefixes.

No image contents, cloud writes, IAM/billing changes, Git operations, package
installation, label repairs or training. Network errors are not empty listings.
Each verified page is cached; a year completes ONLY when nextPageToken is absent.
Successful original full-year caches remain usable. Inventory observations made
at different times are NOT an atomic snapshot. Normal LIST charges can apply.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

VERSION = 'aia17-archive-paged-transport-v1'
BASE_SHA256 = '3ac43cf67057a6f0cc622c408c7a6dad2d2ca2e161665ff6d29d90d6c12ff274'
PAGE_SIZE = 500
MAX_PAGES = 60  # Includes empty continuation pages; reaching cap never means complete.
MAX_PAGE_BYTES = 2 * 1024**2
SOCKET_TIMEOUT = 60
ATTEMPTS = 3
FIELDS = 'kind,nextPageToken,prefixes,items(name,bucket,size,generation,crc32c,md5Hash,timeCreated,updated)'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_base(path: Path):
    if not path.is_file() or digest(path.read_bytes()) != BASE_SHA256:
        raise ValueError('Original archive script is missing or differs from the verified version: ' + str(path))
    spec = importlib.util.spec_from_file_location('aia17_verified_archive_base', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean(text: str, token: str = '') -> str:
    if token:
        text = text.replace(token, '[REDACTED]')
    text = re.sub(r'(?i)Bearer\s+\S+', 'Bearer [REDACTED]', text)
    text = re.sub(r'ya29\.[A-Za-z0-9._~-]+', '[REDACTED]', text)
    return ''.join(c if c in '\n\t' or c.isprintable() else '?' for c in text)[:1600]


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + '\n').encode()


def safe_write(base, cache: Path, path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise ValueError('Refusing to overwrite a different inventory artifact: ' + str(path))
    used = sum(p.stat().st_size for p in cache.rglob('*') if p.is_file())
    if used + len(data) > base.MAX_CACHE_BYTES:
        raise ValueError('Inventory cache byte cap reached; no completeness claim.')
    if base.shutil.disk_usage(cache).free < base.MIN_FREE_BYTES + len(data):
        raise ValueError('Insufficient inventory disk reserve; no completeness claim.')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.inventory_', delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


class SessionToken:
    def __init__(self, project: str):
        self.project = project
        self.value = ''
        self.created = 0.0

    def get(self) -> str:
        if self.value and time.monotonic() - self.created < 2700:
            return self.value
        print('  Checking existing gcloud authentication (credential output is not displayed).', flush=True)
        env = dict(os.environ, CLOUDSDK_CORE_DISABLE_PROMPTS='1',
                   CLOUDSDK_CORE_LOG_HTTP='false', CLOUDSDK_CORE_VERBOSITY='error')
        try:
            result = subprocess.run(
                ['gcloud', 'auth', 'print-access-token', f'--project={self.project}', '--quiet'],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, timeout=60, check=False)
        except subprocess.TimeoutExpired:
            raise RuntimeError('AUTH_TIMEOUT: existing gcloud session did not supply credentials within 60 seconds. No object LIST attempted.') from None
        if result.returncode:
            raise RuntimeError('AUTH_FAILED: ' + clean(result.stderr.decode('utf-8', errors='replace'))) from None
        token = result.stdout.decode('ascii', errors='strict').strip()
        if not 10 <= len(token) <= 16384 or any(c.isspace() for c in token):
            raise RuntimeError('AUTH_INVALID_OUTPUT: no credential displayed or used.')
        self.value, self.created = token, time.monotonic()
        return token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # Never forward the Authorization header to a redirected destination.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class StoragePages:
    def __init__(self, base, token=None, opener=None, sleep=time.sleep):
        self.base = base
        self.token = token or SessionToken(base.PROJECT)
        self.opener = opener or urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        self.sleep = sleep

    def protocol(self, year: int) -> dict:
        return {'transport': VERSION, 'bucket': self.base.BUCKET, 'project': self.base.PROJECT,
                'year': year, 'prefix': self.base.prefix(year), 'maxResults': PAGE_SIZE,
                'fields': FIELDS, 'projection': 'noAcl', 'versions': False}

    def request_page(self, year: int, page_token: str | None) -> tuple[bytes, list[dict]]:
        proto = self.protocol(year)
        params = {'prefix': proto['prefix'], 'maxResults': PAGE_SIZE,
                  'fields': FIELDS, 'projection': 'noAcl', 'versions': 'false'}
        if page_token is not None:
            params['pageToken'] = page_token
        url = ('https://storage.googleapis.com/storage/v1/b/' +
               urllib.parse.quote(self.base.BUCKET, safe='') + '/o?' + urllib.parse.urlencode(params))
        history = []
        for attempt in range(1, ATTEMPTS + 1):
            token = self.token.get()
            request = urllib.request.Request(url, headers={
                'Authorization': 'Bearer ' + token,
                'X-Goog-User-Project': self.base.PROJECT,
                'Accept': 'application/json', 'Accept-Encoding': 'identity',
                'User-Agent': VERSION}, method='GET')
            started = time.monotonic()
            error, retry = None, False
            try:
                with self.opener.open(request, timeout=SOCKET_TIMEOUT) as response:
                    if response.status != 200:
                        raise RuntimeError('Unexpected successful HTTP status; no completeness claim.')
                    declared = response.headers.get('Content-Length')
                    if declared and int(declared) > MAX_PAGE_BYTES:
                        raise ValueError('Page exceeds metadata response byte cap.')
                    # Socket timeout is not a whole-process deadline. Also bound read size
                    # and check elapsed time between chunks; no whole-year 180 s timeout.
                    chunks, total = [], 0
                    while True:
                        part = response.read(min(65536, MAX_PAGE_BYTES + 1 - total))
                        if not part:
                            break
                        chunks.append(part); total += len(part)
                        if total > MAX_PAGE_BYTES:
                            raise ValueError('Page exceeds metadata response byte cap.')
                        if time.monotonic() - started > 2 * SOCKET_TIMEOUT:
                            raise TimeoutError('Page elapsed-time read guard reached.')
                    raw = b''.join(chunks)
                history.append({'attempt': attempt, 'result': 'HTTP_200',
                                'elapsed_seconds': round(time.monotonic() - started, 3)})
                return raw, history
            except urllib.error.HTTPError as exc:
                # No request headers or token values are logged or persisted.
                try:
                    body = json.loads(exc.read(8192).decode('utf-8', errors='replace'))
                    msg = body.get('error', {}).get('message', '')
                except Exception:
                    msg = 'See the HTTP status; no authenticated request headers logged.'
                finally:
                    exc.close()
                error = f'HTTP_{exc.code}: ' + clean(str(msg), token)
                retry = exc.code in {408, 429, 500, 502, 503, 504}
            except (TimeoutError, socket.timeout) as exc:
                error, retry = 'NETWORK_TIMEOUT: ' + clean(str(exc), token), True
            except urllib.error.URLError as exc:
                error = 'NETWORK_ERROR: ' + clean(str(exc.reason), token)
                retry = not isinstance(exc.reason, ssl.SSLCertVerificationError)
            except (ConnectionError, OSError) as exc:
                error = 'NETWORK_IO_ERROR: ' + clean(str(exc), token)
                retry = not isinstance(exc, ssl.SSLCertVerificationError)
            history.append({'attempt': attempt, 'result': error,
                            'elapsed_seconds': round(time.monotonic() - started, 3)})
            if not retry or attempt == ATTEMPTS:
                raise RuntimeError(f'Year {year} page request stopped after {attempt} attempt(s): {error}. Partial pages are NOT a complete listing.') from None
            delay = 2 ** attempt
            print(f'  {year}: {error}; retry {attempt+1}/{ATTEMPTS} in {delay}s.', flush=True)
            self.sleep(delay)
        raise RuntimeError('Unreachable retry state.')

    def validate_page(self, raw: bytes, year: int) -> tuple[list[dict], str | None]:
        if len(raw) > MAX_PAGE_BYTES:
            raise ValueError('Oversized cached/network page.')
        payload = json.loads(raw.decode('utf-8'))
        if not isinstance(payload, dict) or payload.get('kind') != 'storage#objects' or 'error' in payload:
            raise ValueError('Unexpected objects.list response; not an empty archive.')
        if payload.get('prefixes'):
            raise ValueError('Unexpected delimiter prefixes; full recursive scope not established.')
        items = payload.get('items', [])
        if not isinstance(items, list) or len(items) > PAGE_SIZE:
            raise ValueError('Unexpected item list/page count.')
        items = self.base.validate_listing(items, year)
        # fields must include nextPageToken; absent/empty means end, not page length.
        next_token = payload.get('nextPageToken')
        if next_token is not None and (not isinstance(next_token, str) or len(next_token) > 16384):
            raise ValueError('Invalid continuation token schema.')
        return items, next_token or None

    def fetch_listing(self, year: int, cache: Path) -> tuple[list[dict], dict]:
        base = self.base
        listing = cache / f'objects_{year}.json'
        receipt = cache / f'objects_{year}.receipt.json'
        if receipt.exists():
            record = base.document(receipt)
            if (record.get('year') != year or record.get('prefix') != base.prefix(year) or
                    record.get('bucket') != base.BUCKET or record.get('complete') is not True):
                raise ValueError('Cached yearly receipt differs from the archive protocol.')
            base.verified(listing, record.get('sha256'))
            items = base.validate_listing(json.loads(listing.read_text()), year)
            if record.get('object_count') != len(items):
                raise ValueError('Cached yearly object count differs from receipt.')
            print(f'  {year}: reusing {len(items):,} verified objects from {record["finished_utc"]}.', flush=True)
            return items, {**record, 'reused': True}
        pages_dir = cache / f'pages_{year}'
        pages_dir.mkdir(exist_ok=True)
        if listing.exists() and not list(pages_dir.glob('page_*.json')):
            raise ValueError('Unverified yearly listing without complete page evidence; left unchanged: ' + str(listing))
        proto = self.protocol(year)
        all_items, page_records, seen, token_seen = [], [], set(), set()
        token, last_name, finished, first_started = None, None, False, None
        for number in range(1, MAX_PAGES + 1):
            path = pages_dir / f'page_{number:05d}.json'
            if token in token_seen:
                raise ValueError('Repeated continuation token; no completeness claim.')
            token_seen.add(token)
            if path.exists():
                record = base.document(path)
                if record.get('protocol') != proto or record.get('request_page_token') != token:
                    raise ValueError('Cached page belongs to a different request/pagination chain.')
                raw = record['response_text'].encode('utf-8')
                if digest(raw) != record.get('response_sha256'):
                    raise ValueError('Cached page checksum mismatch: ' + str(path))
                origin = 'cached'
            else:
                print(f'  {year}: requesting page {number} (up to {PAGE_SIZE} object metadata records)...', flush=True)
                started = base.now()
                try:
                    raw, attempts = self.request_page(year, token)
                    # Validate before caching; a failed/invalid response is never reused.
                    self.validate_page(raw, year)
                except Exception as exc:
                    base.save_json(pages_dir / 'last_failure.json', {
                        'status': 'PAGE_FAILED_NO_COMPLETENESS_CLAIM', 'year': year,
                        'page': number, 'recorded_utc': base.now(),
                        'error': clean(str(exc), getattr(self.token, 'value', ''))})
                    raise
                record = {'protocol': proto, 'page_number': number,
                          'request_page_token': token, 'started_utc': started,
                          'finished_utc': base.now(), 'attempts': attempts,
                          'response_sha256': digest(raw), 'response_text': raw.decode('utf-8')}
                origin = 'new'
            items, next_token = self.validate_page(raw, year)
            if record.get('page_number') != number:
                raise ValueError('Cached page number mismatch.')
            for item in items:
                name = item['name']
                if name in seen or (last_name is not None and name <= last_name):
                    raise ValueError('Repeated/out-of-order object across pages; no completeness claim.')
                seen.add(name); last_name = name
            if len(all_items) + len(items) >= base.LIMIT:
                raise ValueError('Yearly listing cap reached; not a complete inventory.')
            if next_token and next_token in token_seen:
                raise ValueError('Repeated continuation token; no completeness claim.')
            if origin == 'new':
                safe_write(base, cache, path, json_bytes(record))
            all_items.extend(items)
            first_started = first_started or record['started_utc']
            page_records.append({'path': str(path), 'sha256': base.sha256(path),
                                 'object_count': len(items), 'finished_utc': record['finished_utc']})
            print(f'  {year}: page {number} {origin}; +{len(items):,}; total {len(all_items):,}; '
                  f'{"more pages" if next_token else "end of listing"}.', flush=True)
            if next_token is None:
                finished = True
                break
            token = next_token
        if not finished:
            raise ValueError('Page-count safety cap reached; partial inventory, not absences.')
        extra_pages = [p for p in pages_dir.glob('page_*.json')
                       if p.name not in {Path(r['path']).name for r in page_records}]
        if extra_pages:
            raise ValueError('Unexpected extra cached pages after terminal page; left unchanged.')
        base.validate_listing(all_items, year)
        payload = json_bytes(all_items)
        if len(payload) > base.MAX_LIST_BYTES:
            raise ValueError('Complete yearly listing exceeds size cap.')
        # If interrupted between these two writes, a subsequent run can reconstruct
        # this same listing from the verified page chain, without another cloud read.
        safe_write(base, cache, listing, payload)
        result = {'year': year, 'bucket': base.BUCKET, 'prefix': base.prefix(year),
                  'started_utc': first_started, 'finished_utc': page_records[-1]['finished_utc'],
                  'complete': True, 'completion_basis': 'TERMINAL_PAGE_WITHOUT_NEXT_PAGE_TOKEN',
                  'object_count': len(all_items), 'sha256': base.sha256(listing),
                  'listing_file': str(listing), 'reused': False, 'transport': VERSION,
                  'original_reconciliation_script_sha256': BASE_SHA256,
                  'transport_script_sha256': digest(Path(__file__).read_bytes()),
                  'protocol': proto, 'pages': page_records,
                  'atomic_archive_snapshot': False}
        safe_write(base, cache, receipt, json_bytes(result))
        print(f'  {year}: COMPLETE metadata listing, {len(all_items):,} objects; saved for reuse.', flush=True)
        return all_items, result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.home()/'solar_flare_aia')
    p.add_argument('--work', type=Path, default=Path.home()/'aia17_metadata_stage1/archive_reconciliation_v1')
    p.add_argument('--base-script', type=Path, default=Path.home()/'aia17_archive_reconciliation.py')
    args = p.parse_args()
    try:
        base = load_base(args.base_script.expanduser().resolve())
    except (OSError, ValueError) as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        return 1
    print('===== PAGED LISTING RESUME =====', flush=True)
    print('Original script unchanged. Same locked inputs, same 17 prefixes, same inventory cache.', flush=True)
    print('Only object metadata requested; 500/page; at most 3 attempts for transient errors.', flush=True)
    backend = StoragePages(base)
    base.fetch_listing = backend.fetch_listing  # In-memory transport adapter, not a source-file patch.
    saved_argv = sys.argv
    try:
        sys.argv = [str(args.base_script), '--repo', str(args.repo), '--work', str(args.work)]
        return base.main()
    finally:
        sys.argv = saved_argv


if __name__ == '__main__':
    raise SystemExit(main())
