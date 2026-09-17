#!/usr/bin/env python3
"""17B small NPZ content / timestamp-evidence canary (NOT training clearance).

Uses the 18 already-selected archive candidates: no cloud listings or new sample
selection. Downloads pinned generations through read-only Cloud Storage GETs.
Logical NPZ payload cap 128 MiB; 16 MiB/object; one GET attempt/object/invocation.
Successful downloads are checksum-cached. Does not grant IAM, change billing,
edit metadata, relabel, repair, train, or invoke Git. No automatic package install.

Timing results distinguish explicit scale tags, naive UTC/TAI hypotheses, and
filename stamps. None of these replaces verification of original per-channel
observation headers and instrument availability. The older format has a shared
used_timestamp, not necessarily six independent exposure timestamps.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
from importlib import metadata as package_metadata
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

VERSION = 'aia17-npz-content-timing-canary-v1'
BUCKET = 'suryabench-sharp-pipeline-bamidele'
PROJECT = 'sonorous-shore-450510-i4'
REPORT_ID = '20260916T073559880010Z'
EXPECTED_STATUS = 'OBJECT_RECONCILIATION_COMPLETE_CONTENT_AND_TIMING_NOT_VERIFIED'
MAX_CANDIDATES = 18
MAX_TOTAL_BYTES = 128 * 1024**2
MAX_OBJECT_BYTES = 16 * 1024**2
MAX_INFLATED_BYTES = 64 * 1024**2
MAX_METADATA_BYTES = 1024**2
RESERVE = 1024**3
CHANNELS = [94, 131, 171, 193, 211, 335]
SID = re.compile(r'(\d{8})_(\d{4})_HARP(\d+)_NOAA(\d+)')
CLOCK_SHA = '8ff5f9de5f119c004cccb96e1faaa17cdb4d9ccd9701880c2ab63c0fe309264e'
BOUNDARY = '20240714_0724_HARP11520_NOAA13753'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def read_json(path, limit=32*1024**2):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError(f'Missing/oversized JSON: {path}')
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return obj


def write_json(path, obj):
    path = Path(path)
    if path.exists():
        raise ValueError(f'Output already exists; no overwrite: {path}')
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, allow_nan=False, ensure_ascii=True)
        f.write('\n')


def verified(path, expected):
    if not re.fullmatch('[0-9a-f]{64}', str(expected)) or sha(path) != expected:
        raise ValueError(f'Input checksum differs: {path}')
    return expected


def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f'Missing/duplicate CSV headers: {path}')
        for r in reader:
            if None in r or any(v is None for v in r.values()):
                raise ValueError(f'Malformed CSV row: {path}:{reader.line_num}')
            yield r


def prefix(year):
    root = 'samples_npz' if year <= 2024 else 'jsoc_2025_2026_production_v1/samples_npz'
    return f'{root}/{year}/'


def validate_candidates(candidates, expected_count):
    if len(candidates) != expected_count or not 1 <= len(candidates) <= MAX_CANDIDATES:
        raise ValueError('Candidate count differs from completed inventory or exceeds 18.')
    ids = set()
    for c in candidates:
        sid = c['sample_id']; m = SID.fullmatch(sid)
        if not m or sid in ids:
            raise ValueError('Invalid/duplicate candidate ID.')
        ids.add(sid)
        year = int(c['stored_year'])
        if not 2010 <= year <= 2026 or year != int(sid[:4]):
            raise ValueError('Candidate year disagrees with its sample ID.')
        if c['expected_uri'] != f'gs://{BUCKET}/{prefix(year)}{sid}.npz':
            raise ValueError('Candidate outside exact documented object path.')
        if c['object_status'] != 'EXACT_NONEMPTY_OBJECT':
            raise ValueError('Canary contains a non-exact or empty candidate.')
        if not re.fullmatch(r'\d+', c['generation']):
            raise ValueError('Missing pinned generation.')
        if not 0 < int(c['object_bytes']) <= MAX_OBJECT_BYTES:
            raise ValueError('Object exceeds 16 MiB canary limit.')
        if int(c['original_label']) not in (0, 1):
            raise ValueError('Invalid preserved original label.')
    total = sum(int(c['object_bytes']) for c in candidates)
    if total > MAX_TOTAL_BYTES:
        raise ValueError('Planned canary downloads exceed 128 MiB; nothing downloaded.')
    return total


def load_inventory(report_dir, inventory_root, repo):
    complete = read_json(report_dir/'COMPLETE.json')
    if complete['status'] != EXPECTED_STATUS:
        raise ValueError('Archive inventory was not completed.')
    hashes = {}
    for name in ['archive_reconciliation_report.json', 'timing_canary_candidates.csv',
                 'target_object_register.csv', 'yearly_object_coverage.csv']:
        hashes[str(report_dir/name)] = verified(report_dir/name, complete['output_sha256'][name])
    report = read_json(report_dir/'archive_reconciliation_report.json')
    if report['status'] != EXPECTED_STATUS or report['input_contract']['bucket'] != BUCKET:
        raise ValueError('Unexpected archive report contract.')
    candidates = list(csv_rows(report_dir/'timing_canary_candidates.csv'))
    total = validate_candidates(candidates, report['canary_candidate_count'])
    by_sid = {c['sample_id']: c for c in candidates}
    matched = set(); profile = Counter(); baseline = Counter()
    all_counts = Counter(); row_count = 0
    for r in csv_rows(report_dir/'target_object_register.csv'):
        row_count += 1
        label = int(r['original_label'])
        if label not in (0, 1):
            raise ValueError('Nonbinary original label in object register.')
        status = r['object_status']
        all_counts[status] += 1
        profile[(int(r['stored_year']), status, label)] += 1
        if r['in_baseline'] == '1':
            baseline[status] += 1
        if r['sample_id'] in by_sid:
            c = by_sid[r['sample_id']]
            for k in ('stored_year', 'expected_uri', 'generation', 'object_bytes', 'object_status',
                      'HARPNUM', 'NOAA_AR_clean', 'stored_issue_time', 'original_label'):
                if c[k] != r[k]:
                    raise ValueError(f'Candidate disagrees with object register: {k}')
            if r['sample_id'] in matched:
                raise ValueError('Duplicate candidate record in object register.')
            matched.add(r['sample_id'])
    if row_count != report['master_targets'] or dict(all_counts) != report['status_counts'] or matched != set(by_sid):
        raise ValueError('Object-register totals differ from completed report.')
    receipts = {int(r['year']): r for r in report['listing_receipts']}
    for year in sorted({int(c['stored_year']) for c in candidates}):
        lp = inventory_root/'listings'/f'objects_{year}.json'
        hashes[str(lp)] = verified(lp, receipts[year]['sha256'])
        items = json.loads(lp.read_text(encoding='utf-8'))
        by_name = {o['name']: o for o in items}
        if len(by_name) != len(items):
            raise ValueError('Duplicate names in locked listing.')
        for c in candidates:
            if int(c['stored_year']) != year:
                continue
            name = c['expected_uri'].split(f'gs://{BUCKET}/', 1)[1]
            obj = by_name[name]
            if str(obj['generation']) != c['generation'] or int(obj['size']) != int(c['object_bytes']):
                raise ValueError('Candidate object metadata differs from locked listing.')
            c['name'] = name
            c['crc32c'] = obj.get('crc32c', '')
            c['md5Hash'] = obj.get('md5Hash', '')
            if not c['crc32c'] and not c['md5Hash']:
                raise ValueError('No listed checksum; canary download will not proceed.')
    # Read exact raw TAI lineage; do not infer observation scale from sample names.
    lock_path = repo/'docs/research_audit/2026-09-15/stage1/source_lock_snapshot.json'
    recorded = report['input_contract']['source_sha256']
    key = str(lock_path.relative_to(repo))
    hashes[str(lock_path)] = verified(lock_path, recorded[key])
    lock = read_json(lock_path)
    specs = [s for s in lock['sources'] if s['id'] == 'curated_master']
    if len(specs) != 1:
        raise ValueError('Missing/ambiguous master-source lock.')
    sp = specs[0]; master = Path(sp['local_path']).expanduser()
    if master.stat().st_size != sp['size_bytes']:
        raise ValueError('Master source size differs from recorded source.')
    print('Verifying existing cached master for raw TAI lineage (not downloading it).', flush=True)
    hashes[str(master)] = verified(master, sp['sha256'])
    found = set()
    for r in csv_rows(master):
        sid = r.get('sample_id', '').strip()
        if sid not in by_sid:
            continue
        c = by_sid[sid]
        if sid in found or r['T_REC_dt'] != c['stored_issue_time']:
            raise ValueError('Raw master/candidate timestamp or identity conflict.')
        if int(float(r['HARPNUM'])) != int(c['HARPNUM']) or int(float(r['NOAA_AR_clean'])) != int(c['NOAA_AR_clean']):
            raise ValueError('Raw master/candidate region conflict.')
        if float(r['label_48h_final']) != int(c['original_label']):
            raise ValueError('Raw master/candidate original label conflict.')
        c['raw_T_REC'] = r['T_REC']
        found.add(sid)
    if found != set(by_sid):
        raise ValueError('Not all selected candidates have raw TAI lineage.')
    support = [{'stored_year': y, 'object_status': s, 'original_label': l, 'rows': n}
               for (y, s, l), n in sorted(profile.items())]
    return report, candidates, support, dict(baseline), hashes, total


# CRC32C Castagnoli, independent of optional installed acceleration packages.
def _crc_table():
    out = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ (0x82F63B78 if c & 1 else 0)
        out.append(c)
    return out
CRC_TABLE = _crc_table()


def file_hashes(path):
    h = hashlib.sha256(); m = hashlib.md5(); crc = 0xffffffff; n = 0
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b); m.update(b); n += len(b)
            for x in b:
                crc = CRC_TABLE[(crc ^ x) & 255] ^ (crc >> 8)
    return {'bytes': n, 'sha256': h.hexdigest(),
            'md5Hash': base64.b64encode(m.digest()).decode(),
            'crc32c': base64.b64encode((crc ^ 0xffffffff).to_bytes(4, 'big')).decode()}


def check_object(path, c):
    if not Path(path).is_file() or Path(path).stat().st_size != int(c['object_bytes']):
        raise ValueError('Downloaded/cached object size differs from locked inventory.')
    hashes = file_hashes(path)
    for key in ('crc32c', 'md5Hash'):
        if c.get(key) and hashes[key] != c[key]:
            raise ValueError(f'Object {key} mismatch; no loading permitted.')
    return hashes


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Unexpected redirect rejected; credentials not forwarded.')


class DownloadClient:
    def __init__(self):
        self.opener = urllib.request.build_opener(NoRedirect())
        self.token = ''; self.acquired = 0.0

    def get_token(self):
        if self.token and time.monotonic()-self.acquired < 2400:
            return self.token
        p = subprocess.run(['gcloud', 'auth', 'print-access-token', f'--project={PROJECT}', '--quiet'],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
                           env=dict(os.environ, CLOUDSDK_CORE_DISABLE_PROMPTS='1'))
        if p.returncode:
            raise RuntimeError('Existing gcloud authentication failed; no credential output saved.')
        token = p.stdout.decode().strip()
        if not token or any(c.isspace() for c in token):
            raise RuntimeError('Invalid authentication response; no credential output saved.')
        self.token = token; self.acquired = time.monotonic()
        return token

    def download(self, c, partial):
        query = urllib.parse.urlencode({'alt': 'media', 'generation': c['generation']})
        url = f'https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{urllib.parse.quote(c["name"], safe="")}?{query}'
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer '+self.get_token(),
                   'Accept-Encoding': 'identity', 'User-Agent': VERSION}, method='GET')
        start = time.monotonic(); count = 0
        try:
            with self.opener.open(req, timeout=60) as response:
                if response.status != 200:
                    raise RuntimeError('Non-complete object response rejected.')
                gen = response.headers.get('x-goog-generation')
                if gen and gen != c['generation']:
                    raise RuntimeError('Response generation differs; no fallback to current object.')
                encoding = response.headers.get('Content-Encoding', 'identity').lower()
                if encoding != 'identity':
                    raise RuntimeError('Unexpected transport encoding; no automatic conversion.')
                length = response.headers.get('Content-Length')
                if length is not None and int(length) != int(c['object_bytes']):
                    raise RuntimeError('Response length differs from locked inventory.')
                with Path(partial).open('xb') as f:
                    while True:
                        if time.monotonic()-start > 180:
                            raise TimeoutError('Object download exceeded the 180-second deadline.')
                        chunk = response.read(min(1024**2, int(c['object_bytes'])-count+1))
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > int(c['object_bytes']):
                            raise RuntimeError('Object exceeded locked byte size.')
                        f.write(chunk)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'Cloud Storage GET returned HTTP {exc.code}; no empty-object inference. '
                               'No automatic retry or switch to a different generation.') from None
        if count != int(c['object_bytes']):
            raise RuntimeError('Incomplete object response; no loading permitted.')


def obtain(c, cache, client):
    key = hashlib.sha256((c['expected_uri']+'#'+c['generation']).encode()).hexdigest()
    path = cache/(key+'.npz'); receipt = cache/(key+'.receipt.json')
    if receipt.exists():
        r = read_json(receipt)
        if r['uri'] != c['expected_uri'] or r['generation'] != c['generation']:
            raise ValueError('Cached receipt refers to another object version.')
        h = check_object(path, c)
        if h != r['hashes']:
            raise ValueError('Cached bytes differ from their receipt.')
        return path, {**r, 'reused': True}
    if path.exists():
        raise ValueError('Unreceipted cache file; no silent reuse or overwrite.')
    partial = cache/(key+'.partial')
    if partial.exists():
        # This is exclusively the downloader's own incomplete cache object.
        partial.unlink()
    try:
        client.download(c, partial)
        h = check_object(partial, c)
        r = {'uri': c['expected_uri'], 'generation': c['generation'], 'fetched_utc': utc_now(),
             'hashes': h, 'reused': False}
        os.replace(partial, path)
        write_json(receipt, r)
        return path, r
    finally:
        partial.unlink(missing_ok=True)


def safe_npz(path, np):
    arrays = {}; descriptors = {}
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        if not 1 <= len(infos) <= 64 or len({x.filename for x in infos}) != len(infos):
            raise ValueError('Unsupported NPZ member count/duplicate names.')
        if sum(i.file_size for i in infos) > MAX_INFLATED_BYTES:
            raise ValueError('NPZ uncompressed-size cap exceeded.')
        for info in infos:
            if not re.fullmatch(r'[A-Za-z0-9_]+\.npy', info.filename) or info.flag_bits & 1:
                raise ValueError('Unexpected/encrypted NPZ member; no extraction or pickle used.')
            key = info.filename[:-4]
            cap = MAX_INFLATED_BYTES if key == 'x' else MAX_METADATA_BYTES
            if info.file_size > cap:
                raise ValueError(f'NPZ member exceeds size allowance: {key}')
            with z.open(info) as f:
                version = np.lib.format.read_magic(f)
                if version == (1, 0):
                    shape, order, dtype = np.lib.format.read_array_header_1_0(f, max_header_size=10000)
                elif version == (2, 0):
                    shape, order, dtype = np.lib.format.read_array_header_2_0(f, max_header_size=10000)
                else:
                    raise ValueError('Unsupported NPY header version; no implicit conversion.')
                if dtype.hasobject:
                    raise ValueError(f'Object/pickle array rejected: {key}')
                if any(not isinstance(d, int) or d < 0 for d in shape):
                    raise ValueError('Malformed array shape.')
                declared_bytes = math.prod(shape)*dtype.itemsize
                if declared_bytes != info.file_size-f.tell():
                    raise ValueError('NPY header allocation differs from member byte length.')
            with z.open(info) as f:
                # Loading via NumPy after bounded header inspection; never allow pickle.
                arrays[key] = np.load(f, allow_pickle=False, max_header_size=10000)
            descriptors[key] = {'shape': list(shape), 'dtype': str(dtype)}
    return arrays, descriptors


def scalar(a):
    if a.shape != ():
        raise ValueError('Expected a scalar metadata field.')
    v = a.item()
    if isinstance(v, bytes):
        return v.decode('utf-8')
    if not isinstance(v, (str, int, float, bool)) or isinstance(v, float) and not math.isfinite(v):
        raise ValueError('Unsupported scalar metadata type.')
    return v


def parse_channels(a):
    if a.ndim != 1:
        raise ValueError('Channels must be a one-dimensional array.')
    values = a.tolist(); out = []
    for v in values:
        s = v.decode() if isinstance(v, bytes) else str(v)
        m = re.fullmatch(r'(?:aia)?(\d+)', s)
        if not m:
            raise ValueError('Unrecognised channel token.')
        out.append(int(m[1]))
    return out


def normal_time(s):
    # Preserve unknown/non-supported forms rather than guessing.
    s = str(s).strip()
    m = re.fullmatch(r'(\d{4})\.(\d{2})\.(\d{2})_(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)_TAI', s)
    if m:
        return f'{m[1]}-{m[2]}-{m[3]}T{m[4]}', 'tai', 'explicit_TAI_suffix'
    m = re.fullmatch(r'(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)(Z|\+00:00|_UTC)?', s)
    if not m:
        raise ValueError('Unrecognised timestamp representation.')
    return m[1]+'T'+m[2], ('utc' if m[3] else None), ('explicit_UTC_suffix' if m[3] else 'naive_scale_unresolved')


def timing_entry(field, value, issue, clock, channel=None):
    r = {'field': field, 'channel': channel, 'raw_value': str(value),
         'observation_header_verified': False, 'report_availability_verified': False}
    try:
        iso, scale, kind = normal_time(value)
        r['representation'] = kind
        if not '2010-01-01T00:00:00' <= iso < '2026-07-01T00:00:00':
            raise ValueError('Timestamp outside this verified historical clock scope.')
        for candidate_scale in ([scale] if scale else ['utc', 'tai']):
            tick = clock.ticks([iso], candidate_scale)[0]
            delta_us = tick-issue
            label = 'declared' if scale else 'hypothesis'
            r[f'{candidate_scale}_{label}'] = {
                'delta_seconds_frame_minus_issue': delta_us/1000000,
                'within_180_seconds': abs(delta_us) <= 180000000,
                'at_or_before_issue': delta_us <= 0,
                'passes_both_timing_rules': -180000000 <= delta_us <= 0}
        r['status'] = 'DECLARED_SCALE_METADATA_ONLY' if scale else 'UNRESOLVED_SCALE_CONDITIONAL_COMPARISONS'
    except (ValueError, TypeError) as exc:
        r['status'] = 'TIMESTAMP_UNPARSED'; r['error'] = str(exc)
    return r


def inspect_file(path, c, np, clock, raw_tai_iso):
    arrays, desc = safe_npz(path, np)
    r = {'sample_id': c['sample_id'], 'stored_year': int(c['stored_year']),
         'original_label': int(c['original_label']), 'generation': c['generation'],
         'npz_members': desc, 'issues': [], 'timing_evidence': [],
         'metadata': {}, 'observation_headers_verified': False, 'training_authorised': False}
    for key in ('sample_id', 'T_REC_dt', 'HARPNUM', 'NOAA_AR_clean', 'used_timestamp',
                'used_s3_path', 'source', 'block_id', 'crop_meta', 'channel_metadata', 'y', 'label_48h_final'):
        if key in arrays:
            r['metadata'][key] = scalar(arrays[key])
    for key, expected in [('sample_id', c['sample_id']), ('HARPNUM', int(c['HARPNUM'])),
                          ('NOAA_AR_clean', int(c['NOAA_AR_clean'])), ('T_REC_dt', c['stored_issue_time'])]:
        if key not in r['metadata']:
            r['issues'].append('MISSING_IDENTITY_'+key)
        elif str(r['metadata'][key]) != str(expected):
            r['issues'].append('IDENTITY_MISMATCH_'+key)
    channel_sources = {}
    for key in ('channels', 'wavelengths'):
        if key in arrays:
            channel_sources[key] = parse_channels(arrays[key])
    r['channel_declarations'] = channel_sources
    if not channel_sources or any(v != CHANNELS for v in channel_sources.values()):
        r['issues'].append('CHANNEL_ORDER_OR_DECLARATION_REVIEW')
    if 'x' not in arrays:
        r['issues'].append('MISSING_X')
    else:
        x = arrays['x']
        r['tensor_shape'] = list(x.shape); r['tensor_dtype'] = str(x.dtype)
        if x.shape != (512, 512, 6) or x.dtype.kind != 'f':
            r['issues'].append('TENSOR_SHAPE_OR_DTYPE_REVIEW')
        else:
            stats = []
            for i, wl in enumerate(CHANNELS):
                plane = x[..., i]; finite = np.isfinite(plane)
                n_bad = int(plane.size-np.count_nonzero(finite))
                s = {'wavelength': wl, 'nonfinite_pixels': n_bad}
                if finite.any():
                    good = plane[finite]
                    s.update(min=float(good.min()), max=float(good.max()), mean=float(good.mean()),
                             std=float(good.std()), zero_fraction=float(np.mean(good == 0)))
                    if s['min'] == s['max']:
                        r['issues'].append(f'CONSTANT_CHANNEL_{wl}')
                if n_bad:
                    r['issues'].append(f'NONFINITE_CHANNEL_{wl}')
                stats.append(s)
            r['channel_statistics'] = stats
    # This is a lineage comparison only: NPZ labels never replace official labels.
    r['embedded_label_comparisons'] = {key: {'value': r['metadata'][key],
         'matches_original_manifest_label': str(r['metadata'][key]) in
            (str(c['original_label']), str(float(c['original_label'])))}
         for key in ('y', 'label_48h_final') if key in r['metadata']}
    issue = clock.ticks([raw_tai_iso(c['raw_T_REC'])], 'tai')[0]
    r['raw_T_REC'] = c['raw_T_REC']; r['derived_issue_utc'] = clock.utc_text([issue])[0]
    if 'channel_metadata' in r['metadata']:
        r['format'] = 'PER_CHANNEL_METADATA'
        cm = json.loads(r['metadata']['channel_metadata'])
        if not isinstance(cm, dict):
            raise ValueError('channel_metadata JSON is not an object.')
        for wl in CHANNELS:
            record = cm.get(str(wl))
            if not isinstance(record, dict):
                r['issues'].append(f'MISSING_CHANNEL_METADATA_{wl}'); continue
            if 'used_time' in record:
                entry = timing_entry('channel_metadata.used_time', record['used_time'], issue, clock, wl)
                # The stored delta is absolute and does not certify a no-future rule.
                entry['stored_absolute_delta_seconds'] = record.get('delta_seconds')
                r['timing_evidence'].append(entry)
            else:
                r['issues'].append(f'MISSING_USED_TIME_{wl}')
            filename = str(record.get('source_file', ''))
            # An explicit Z stamp in a source filename is separate evidence, NOT a FITS header.
            m = re.search(r'(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})(\d{2})Z', filename)
            if m:
                stamp = f'{m[1]}T{m[2]}:{m[3]}:{m[4]}Z'
                entry = timing_entry('source_file.Z_timestamp_not_header', stamp, issue, clock, wl)
                entry['source_file'] = filename
                r['timing_evidence'].append(entry)
    elif 'used_timestamp' in r['metadata']:
        r['format'] = 'SHARED_USED_TIMESTAMP'
        r['timing_evidence'].append(timing_entry('used_timestamp_shared_not_per_channel',
                                       r['metadata']['used_timestamp'], issue, clock))
    else:
        r['format'] = 'NO_RECOGNISED_IMAGE_TIME_FIELD'
        r['issues'].append('NO_RECOGNISED_IMAGE_TIME_FIELD')
    r['content_status'] = 'CONTENT_CHECKS_PASSED_ON_THIS_FILE' if not r['issues'] else 'CONTENT_REVIEW_REQUIRED'
    r['timing_status'] = 'TIMING_PROVENANCE_REVIEW_REQUIRED'
    return r


def load_clock(repo):
    path = repo/'scripts/aia17_time_label_impact.py'
    verified(path, CLOCK_SHA)
    spec = importlib.util.spec_from_file_location('aia17_verified_clock_helper', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    clock = mod.AstroClock(); tests = clock.check()
    if tests.get('passed') is not True:
        raise ValueError('Existing clock self-tests did not pass.')
    return clock, mod.raw_tai_iso, tests


def write_csv(path, rows, fields):
    with path.open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)


def brief_timing(r):
    rows = [t for t in r.get('timing_evidence', []) if t['field'].startswith(('used_timestamp', 'channel_metadata'))]
    answers = []
    for scale in ('utc', 'tai'):
        vals = [t[f'{scale}_hypothesis']['delta_seconds_frame_minus_issue']
                for t in rows if f'{scale}_hypothesis' in t]
        if vals:
            answers.append(f'{scale.upper()} hypothesis signed delta {min(vals):.6f}..{max(vals):.6f} s')
    return '; '.join(answers) or 'See explicit-scale/raw timestamp evidence; no exposure-header certification'


def installed_versions():
    out = {}
    for name in ('numpy', 'astropy', 'pyerfa', 'astropy-iers-data'):
        try:
            out[name] = package_metadata.version(name)
        except package_metadata.PackageNotFoundError:
            out[name] = 'not_installed_in_this_test_environment'
    return out


def run(args, client=None, clock_bundle=None):
    repo = args.repo.expanduser().resolve(); root = args.inventory.expanduser().resolve()
    rd = (args.report_dir or root/'reports'/REPORT_ID).expanduser().resolve()
    work = args.work.expanduser().resolve()
    if repo == work or repo in work.parents:
        raise ValueError('Canary cache/reports must remain outside the Git repository.')
    print('===== 17B SMALL NPZ CONTENT / TIMING-EVIDENCE CANARY =====', flush=True)
    print('Up to 18 pinned NPZ downloads; no relisting, extraction, label repairs or training.', flush=True)
    if clock_bundle is None:
        import numpy as np
        clock, raw_tai_iso, selftests = load_clock(repo)
    else:
        np, clock, raw_tai_iso, selftests = clock_bundle
    report, candidates, support, baseline, hashes, total = load_inventory(rd, root, repo)
    work.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(work).free < total+RESERVE:
        raise ValueError('Need planned canary bytes plus 1 GiB free disk reserve.')
    contract = {'version': VERSION, 'inventory_report_sha256': hashes[str(rd/'archive_reconciliation_report.json')],
                'candidates_sha256': hashes[str(rd/'timing_canary_candidates.csv')], 'logical_bytes': total,
                'max_total_bytes': MAX_TOTAL_BYTES, 'max_candidates': MAX_CANDIDATES}
    cp = work/'input_contract.json'
    if cp.exists() and read_json(cp) != contract:
        raise ValueError('Canary work directory has a different input contract; no mixing snapshots.')
    if not cp.exists():
        write_json(cp, contract)
    print(f'Canary files: {len(candidates)} | locked payload: {total/1024**2:.2f} MiB (cap 128 MiB).', flush=True)
    print('Baseline object statuses:', json.dumps(baseline, sort_keys=True), flush=True)
    cache = work/'objects'; cache.mkdir(exist_ok=True)
    lock = work/'.running.lock'
    fd = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    os.write(fd, str(os.getpid()).encode()); os.close(fd)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = work/'reports'/stamp; out.mkdir(parents=True, exist_ok=False)
    results = []
    try:
        client = client or DownloadClient()
        for n, c in enumerate(candidates, 1):
            print(f'  [{n}/{len(candidates)}] {c["sample_id"]}: pinned generation download/cache check', flush=True)
            path, receipt = obtain(c, cache, client)
            try:
                result = inspect_file(path, c, np, clock, raw_tai_iso)
            except Exception as exc:
                result = {'sample_id': c['sample_id'], 'stored_year': int(c['stored_year']),
                          'content_status': 'CONTENT_READ_OR_SCHEMA_ERROR', 'error_type': type(exc).__name__,
                          'error': str(exc)[:2000], 'timing_evidence': [], 'format': 'UNRESOLVED',
                          'timing_status': 'NOT_EVALUATED_CONTENT_ERROR', 'training_authorised': False}
            result['download_receipt'] = receipt
            result['selection_reason'] = c['selection_reason']
            write_json(out/(c['sample_id']+'.json'), result)
            results.append(result)
            print(f'    {result["content_status"]} | {result["format"]}', flush=True)
        summary = {'version': VERSION, 'status': 'NPZ_CANARY_COMPLETE_REVIEW_REQUIRED_NO_TRAINING',
          'created_utc': utc_now(), 'source_inventory_report': str(rd/'archive_reconciliation_report.json'),
          'input_sha256': hashes, 'clock_self_tests': selftests,
          'versions': installed_versions(),
          'candidate_count': len(candidates), 'planned_object_bytes': total,
          'content_status_counts': dict(Counter(r['content_status'] for r in results)),
          'format_counts': dict(Counter(r['format'] for r in results)), 'baseline_object_statuses': baseline,
          'source_labels_replaced': False, 'training_authorised': False,
          'all_selected_object_bytes_checksum_verified': True,
          'full_archive_contents_verified': False, 'original_observation_headers_verified': False,
          'results': results,
          'limitations': [
            'A small deterministic one-per-year canary plus a targeted boundary case is not a representative accuracy/completeness test.',
            'Original binary labels are only preserved and compared to embedded labels, never replaced.',
            'Naive serialized timestamps are compared under both UTC and TAI hypotheses; neither is silently adopted.',
            'Filename Z timestamps and explicit metadata tags do not certify the original per-channel observation headers.',
            'Positive signed deltas mean after issue time in that calculation, not automatic proof of archive-wide leakage.',
            'Zero-byte, missing, ambiguous or alternate objects were not silently accepted as canary inputs.',
            'Existing successful caches are reused without a new inventory or automatic refresh.',
            'A missing object is not a negative solar-flare label; missingness support uses existing, not recertified, labels.',
            'Catalogue coverage, feature availability, sequence support and the final split still require review.']}
        write_json(out/'npz_canary_report.json', summary)
        write_csv(out/'object_availability_by_year_and_original_label.csv', support,
                  ['stored_year', 'object_status', 'original_label', 'rows'])
        lines = ['# 17B small NPZ content / timing-evidence canary', '',
                 '**Review required; no training clearance or source repairs.**', '',
                 f'Candidate files: {len(candidates)}; locked payload: {total/1024**2:.2f} MiB.', '',
                 '|Sample|Content check|Format|', '|---|---|---|']
        lines += [f'|{r["sample_id"]}|{r["content_status"]}|{r["format"]}|' for r in results]
        lines += ['', '## Limitations', ''] + ['- '+x for x in summary['limitations']]
        (out/'research_log_npz_canary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        write_json(out/'COMPLETE.json', {'status': summary['status'],
                   'output_sha256': {f.name: sha(f) for f in out.iterdir() if f.is_file()}})
        print('\n===== NPZ CONTENT / TIMING CANARY RESULTS =====')
        print('Content statuses:', json.dumps(summary['content_status_counts'], sort_keys=True))
        for r in results:
            print(f'{r["stored_year"]} | {r["sample_id"]} | {r["content_status"]} | {r["format"]}')
            print('  '+brief_timing(r))
            if r.get('issues'): print('  Issues:', ', '.join(r['issues']))
            if r.get('error'): print('  Read/schema error:', r['error'])
        print('STATUS:', summary['status'])
        print('REPORT:', out/'npz_canary_report.json')
        print('RESEARCH LOG:', out/'research_log_npz_canary.md')
        print('Availability by original label:', out/'object_availability_by_year_and_original_label.csv')
        print('No archive-wide timing approval, cloud writes, original-label changes or training.')
        return 0
    except Exception as exc:
        write_json(out/'STOPPED.json', {'status': 'CANARY_STOPPED_NO_COMPLETION_CLAIM',
                'error_type': type(exc).__name__, 'error': str(exc)[:2000],
                'completed_candidate_files': len(results)})
        raise
    finally:
        lock.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.home()/'solar_flare_aia')
    p.add_argument('--inventory', type=Path, default=Path.home()/'aia17_metadata_stage1/archive_reconciliation_v1')
    p.add_argument('--report-dir', type=Path)
    p.add_argument('--work', type=Path, default=Path.home()/'aia17_metadata_stage1/npz_timing_canary_v1')
    args = p.parse_args()
    try:
        return run(args)
    except Exception as exc:
        print(f'\nSTOP: {exc}', file=sys.stderr)
        print('No absence inference, relabeling, cloud write or training was performed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
