#!/usr/bin/env python3
"""17B: reconcile locked target IDs with live AIA object metadata, not pixels.

Default execution reads Google Cloud Storage through the authenticated gcloud CLI.
Only object LIST operations are used, scoped to 17 documented yearly prefixes.
No image/data-object downloads, clock conversions, label repair, cloud writes,
Git operations, model loading, package installation or training are performed.
Successful yearly listings are checksum-cached; reruns reuse them. Use a new
--work directory for a deliberately new inventory, not a silently refreshed one.
An object existing is NOT proof of its contents or its image-observation time.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

VERSION = 'aia17-archive-reconciliation-v1'
PROJECT = 'sonorous-shore-450510-i4'
BUCKET = 'suryabench-sharp-pipeline-bamidele'
SNAPSHOT = Path('docs/research_audit/2026-09-15')
YEARS = list(range(2010, 2027))
LIMIT = 25001  # Reaching this limit is incomplete; never converted into absences.
MAX_LIST_BYTES = 32 * 1024**2
MAX_CACHE_BYTES = 256 * 1024**2
MIN_FREE_BYTES = 1024**3
SID = re.compile(r'(?P<date>\d{8})_(?P<hm>\d{4})_HARP(?P<harp>\d+)_NOAA(?P<noaa>\d+)')
BOUNDARY_SID = '20240714_0724_HARP11520_NOAA13753'
FINAL_OK = 'OBJECT_RECONCILIATION_COMPLETE_CONTENT_AND_TIMING_NOT_VERIFIED'


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def document(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_LIST_BYTES:
        raise ValueError(f'Missing or oversized JSON: {path}')
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return obj


def save_json(path: Path, obj: Any) -> None:
    data = json.dumps(obj, indent=2, allow_nan=False) + '\n'
    tmp = path.with_name(path.name + '.partial')
    tmp.write_text(data, encoding='utf-8')
    os.replace(tmp, path)


def verified(path: Path, expected: str) -> str:
    if not re.fullmatch(r'[0-9a-f]{64}', expected or ''):
        raise ValueError(f'Missing/invalid recorded checksum: {path}')
    if not path.is_file() or sha256(path) != expected:
        raise ValueError(f'Checksum mismatch or missing input: {path}')
    return expected


def prefix(year: int) -> str:
    if year not in YEARS:
        raise ValueError('Year outside audited scope.')
    root = 'samples_npz' if year <= 2024 else 'jsoc_2025_2026_production_v1/samples_npz'
    return f'{root}/{year}/'


def expected_uri(sid: str) -> str:
    match = SID.fullmatch(sid)
    if not match:
        raise ValueError(f'Unsupported sample_id: {sid!r}')
    return f'gs://{BUCKET}/{prefix(int(sid[:4]))}{sid}.npz'


def numeric_id(value: str) -> int:
    # These CSV ID columns can be serialized as integral floats.
    value = value.strip()
    if not re.fullmatch(r'\d+(?:\.0+)?', value):
        raise ValueError(f'Invalid region identifier: {value!r}')
    return int(value.split('.')[0])


def load_inputs(repo: Path) -> tuple[dict, dict, dict]:
    manifest = document(repo / SNAPSHOT / 'checkpoint_file_manifest.json')
    entries = {x['path']: x for x in manifest['files']}
    reports = {}
    hashes = {}
    for name in ('source_lock_snapshot.json', 'stage1_report.json'):
        rel = str(SNAPSHOT / 'stage1' / name)
        if rel not in entries:
            raise ValueError(f'Checkpoint does not record {rel}')
        path = repo / rel
        hashes[rel] = verified(path, entries[rel]['sha256'])
        reports[name] = document(path)
    lock, report = reports['source_lock_snapshot.json'], reports['stage1_report.json']
    if lock['project'] != PROJECT:
        raise ValueError('Source-lock project differs from the agreed project.')
    sources = {}
    for source_id in ('curated_master', 'baseline_manifest'):
        matches = [x for x in lock['sources'] if x['id'] == source_id]
        if len(matches) != 1:
            raise ValueError(f'Missing/ambiguous source entry: {source_id}')
        spec = matches[0]
        path = Path(spec['local_path']).expanduser()
        if path.stat().st_size != spec['size_bytes']:
            raise ValueError(f'Source size mismatch: {source_id}')
        print(f'Checking existing local metadata checksum: {source_id}', flush=True)
        hashes[str(path)] = verified(path, spec['sha256'])
        sources[source_id] = path
    profiles = {x['source']: x for x in report['source_profiles']}
    return sources, profiles, hashes


def read_targets(path: Path, expected_rows: int) -> dict[str, dict]:
    out = {}
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, strict=True)
        needed = {'sample_id', 'HARPNUM', 'NOAA_AR_clean', 'T_REC_dt', 'label_48h_final'}
        if not needed.issubset(reader.fieldnames or []):
            raise ValueError(f'Missing target identity columns: {path}')
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('Duplicate source headers.')
        for r in reader:
            if None in r or any(v is None for v in r.values()):
                raise ValueError(f'Malformed source record: {path}:{reader.line_num}')
            sid = r['sample_id'].strip()
            match = SID.fullmatch(sid)
            if not match or sid in out:
                raise ValueError(f'Invalid or duplicate target ID: {sid!r}')
            t = datetime.fromisoformat(r['T_REC_dt'].strip())
            if t.strftime('%Y%m%d_%H%M') != sid[:13]:
                raise ValueError(f'Stored clock and sample ID disagree: {sid}')
            if (numeric_id(r['HARPNUM']) != int(match['harp']) or
                    numeric_id(r['NOAA_AR_clean']) != int(match['noaa'])):
                raise ValueError(f'Region and sample ID disagree: {sid}')
            label = r['label_48h_final'].strip()
            if label not in ('0', '1', '0.0', '1.0'):
                raise ValueError(f'Invalid existing label: {sid}')
            if t.year not in YEARS:
                raise ValueError(f'Target outside supported years: {sid}')
            out[sid] = {'sample_id': sid, 'stored_year': t.year,
                        'HARPNUM': match['harp'], 'NOAA_AR_clean': match['noaa'],
                        'original_label': int(float(label)),
                        'stored_issue_time': r['T_REC_dt'],
                        'source_gcp_path': r.get('gcp_path', '').strip()}
    if len(out) != expected_rows:
        raise ValueError(f'Source row count differs from saved audit: {path}')
    return out


def target_contract(master: dict, baseline: dict) -> dict:
    if not set(baseline).issubset(master):
        raise ValueError('Baseline is not a subset of the locked master.')
    for sid, row in master.items():
        historical = baseline.get(sid)
        if historical:
            for field in ('stored_year', 'HARPNUM', 'NOAA_AR_clean', 'original_label', 'stored_issue_time'):
                if row[field] != historical[field]:
                    raise ValueError(f'Baseline/master disagree on {field}: {sid}')
        declared = [r['source_gcp_path'] for r in (row, historical) if r and r['source_gcp_path']]
        if len(set(declared)) > 1:
            raise ValueError(f'Conflicting explicit object paths: {sid}')
        uri = declared[0] if declared else expected_uri(sid)
        expected_start = f'gs://{BUCKET}/{prefix(row["stored_year"])}'
        if not uri.startswith(expected_start) or not uri.endswith('/' + sid + '.npz'):
            raise ValueError(f'Explicit URI outside documented layout: {sid}: {uri}')
        row['expected_uri'] = uri
        row['path_basis'] = 'explicit_metadata_path' if declared else 'documented_layout_plus_sample_id'
        row['in_baseline'] = int(historical is not None)
    return master


def validate_listing(items: Any, year: int) -> list[dict]:
    if not isinstance(items, list):
        raise ValueError('Cloud CLI did not return a JSON list.')
    if len(items) >= LIMIT:
        raise ValueError(f'Year {year} reached the listing cap; completeness is unknown.')
    seen = set()
    result = []
    for obj in items:
        if not isinstance(obj, dict):
            raise ValueError('Unexpected object-list schema.')
        name = obj.get('name')
        if not isinstance(name, str) or not name.startswith(prefix(year)):
            raise ValueError(f'Unexpected object name/prefix for {year}: {name!r}')
        if name in seen or obj.get('bucket', BUCKET) != BUCKET:
            raise ValueError('Duplicate returned object name or unexpected bucket.')
        seen.add(name)
        generation = str(obj.get('generation', ''))
        if not generation.isdecimal():
            raise ValueError(f'Missing/invalid generation: {name}')
        size = str(obj.get('size', ''))
        if not size.isdecimal():
            raise ValueError(f'Missing/invalid object size: {name}')
        result.append({**obj, 'name': name, 'generation': generation, 'size': int(size)})
    return result


def fetch_listing(year: int, cache: Path) -> tuple[list[dict], dict]:
    listing = cache / f'objects_{year}.json'
    receipt = cache / f'objects_{year}.receipt.json'
    if receipt.exists():
        record = document(receipt)
        if record['prefix'] != prefix(year) or record['bucket'] != BUCKET or record['complete'] is not True:
            raise ValueError('Cached listing receipt differs from this protocol.')
        verified(listing, record['sha256'])
        items = validate_listing(json.loads(listing.read_text()), year)
        print(f'  {year}: reusing {len(items):,} listed objects from {record["finished_utc"]}', flush=True)
        return items, {**record, 'reused': True}
    if listing.exists():
        raise ValueError(f'Unverified listing exists without receipt: {listing}; no silent reuse.')
    fields = 'name,bucket,size,generation,crc32c,md5Hash,timeCreated,updated'
    cmd = ['gcloud', 'storage', 'objects', 'list', f'gs://{BUCKET}/{prefix(year)}**',
           '--raw', f'--format=json({fields})', f'--limit={LIMIT}', '--page-size=1000',
           f'--project={PROJECT}', '--quiet']
    started = now()
    env = dict(os.environ, CLOUDSDK_CORE_DISABLE_PROMPTS='1')
    print(f'  {year}: listing gs://{BUCKET}/{prefix(year)} (object metadata only)', flush=True)
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            completed = subprocess.run(cmd, stdout=stdout, stderr=stderr, env=env, timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f'Year {year} listing timed out; no absence claim made.') from exc
        stdout.seek(0, 2)
        length = stdout.tell()
        stderr.seek(0)
        err = stderr.read(16384).decode('utf-8', errors='replace')
        if completed.returncode:
            raise RuntimeError(f'Year {year} listing failed ({completed.returncode}): {err.strip()}')
        if length > MAX_LIST_BYTES:
            raise ValueError('Returned listing exceeds local response-size cap.')
        stdout.seek(0)
        payload = stdout.read()
    items = validate_listing(json.loads(payload), year)
    used = sum(p.stat().st_size for p in cache.glob('objects_*.json'))
    if used + len(payload) > MAX_CACHE_BYTES:
        raise ValueError('Listing cache-size cap would be exceeded.')
    if shutil.disk_usage(cache).free < MIN_FREE_BYTES + len(payload):
        raise ValueError('Insufficient disk reserve; nothing downloaded from image objects.')
    # Keep exactly the captured CLI bytes so its checksum is reproducible.
    listing.write_bytes(payload)
    record = {'year': year, 'bucket': BUCKET, 'prefix': prefix(year), 'command': cmd,
              'started_utc': started, 'finished_utc': now(), 'complete': True,
              'object_count': len(items), 'sha256': sha256(listing), 'listing_file': str(listing),
              'reused': False}
    save_json(receipt, record)
    return items, record


def classify(row: dict, candidates: list[dict]) -> dict:
    exact = [o for o in candidates if f'gs://{BUCKET}/{o["name"]}' == row['expected_uri']]
    if len(candidates) > 1:
        state = 'MULTIPLE_OBJECTS_FOR_ID'
    elif exact:
        state = 'EXACT_NONEMPTY_OBJECT' if exact[0]['size'] > 0 else 'ZERO_BYTE_OBJECT'
    elif candidates:
        state = 'ALTERNATE_PATH_REVIEW'
    else:
        state = 'NOT_FOUND_IN_AUDITED_PREFIX'
    chosen = exact[0] if len(exact) == 1 else None
    return {k: v for k, v in row.items() if k != 'source_gcp_path'} | {
        'object_status': state, 'same_id_object_count': len(candidates),
        'exact_object_present': int(bool(exact)),
        'generation': chosen['generation'] if chosen else '',
        'object_bytes': chosen['size'] if chosen else '',
        'crc32c_as_listed': chosen.get('crc32c', '') if chosen else '',
        'candidate_uris': json.dumps([f'gs://{BUCKET}/{o["name"]}' for o in candidates]),
        'image_contents_checked': False, 'image_observation_times_checked': False}


def reconcile(targets: dict, per_year: dict[int, list[dict]]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    rows, extras, summaries = [], [], []
    for year in YEARS:
        objects = per_year[year]  # Missing listing cannot produce a zero count.
        by_sid = defaultdict(list)
        year_targets = {sid: r for sid, r in targets.items() if r['stored_year'] == year}
        for obj in objects:
            base = PurePosixPath(obj['name']).name
            sid = base[:-4] if base.endswith('.npz') else ''
            if SID.fullmatch(sid) and int(sid[:4]) == year:
                by_sid[sid].append(obj)
            if sid not in year_targets:
                extras.append({'listed_year': year, 'name': obj['name'], 'bytes': obj['size'],
                               'generation': obj['generation'], 'possible_sample_id': sid,
                               'reason': 'OBJECT_WITHOUT_TARGET_IN_THIS_YEAR', 'delete_authorised': False})
        year_rows = [classify(r, by_sid.get(sid, [])) for sid, r in sorted(year_targets.items())]
        rows.extend(year_rows)
        counts = Counter(r['object_status'] for r in year_rows)
        summaries.append({'stored_year': year, 'expected_targets': len(year_targets),
                          'listed_objects': len(objects),
                          'exact_nonempty': counts['EXACT_NONEMPTY_OBJECT'],
                          'not_found': counts['NOT_FOUND_IN_AUDITED_PREFIX'],
                          'zero_byte': counts['ZERO_BYTE_OBJECT'],
                          'ambiguous_ids': counts['MULTIPLE_OBJECTS_FOR_ID'],
                          'alternate_paths': counts['ALTERNATE_PATH_REVIEW'],
                          'other_objects': sum(1 for e in extras if e['listed_year'] == year),
                          'baseline_targets': sum(r['in_baseline'] for r in year_rows),
                          'baseline_exact_nonempty': sum(r['in_baseline'] and r['object_status']=='EXACT_NONEMPTY_OBJECT' for r in year_rows)})
    canaries = []
    for year in YEARS:
        eligible = [r for r in rows if r['stored_year'] == year and r['object_status'] == 'EXACT_NONEMPTY_OBJECT']
        if eligible:
            chosen = min(eligible, key=lambda r: hashlib.sha256(('aia17-timing-canary-v1|' + r['sample_id']).encode()).digest())
            canaries.append({**chosen, 'selection_reason': 'one_label_independent_hash_sample_per_stored_year'})
    boundary = [r for r in rows if r['sample_id'] == BOUNDARY_SID and r['object_status'] == 'EXACT_NONEMPTY_OBJECT']
    if boundary and BOUNDARY_SID not in {r['sample_id'] for r in canaries}:
        canaries.append({**boundary[0], 'selection_reason': 'previously_identified_boundary_case'})
    return rows, extras, summaries, canaries


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.home()/'solar_flare_aia')
    p.add_argument('--work', type=Path, default=Path.home()/'aia17_metadata_stage1/archive_reconciliation_v1')
    args = p.parse_args()
    repo, work = args.repo.expanduser().resolve(), args.work.expanduser().resolve()
    if work == repo or repo in work.parents:
        raise SystemExit('STOP: audit outputs must remain outside the Git repository.')
    work.mkdir(parents=True, exist_ok=True)
    lockfile = work / '.running.lock'
    try:
        fd = os.open(lockfile, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    except FileExistsError:
        raise SystemExit('STOP: this archive inventory already has a run lock. Check for an active process.')
    os.write(fd, f'pid={os.getpid()}\n'.encode()); os.close(fd)
    try:
        print('===== 17B AIA ARCHIVE OBJECT RECONCILIATION =====', flush=True)
        print('Read-only cloud LIST operations; no image-object downloads or source repairs.', flush=True)
        if not shutil.which('gcloud'):
            raise RuntimeError('gcloud is unavailable; run inside your restored Cloud Shell.')
        if shutil.disk_usage(work).free < MIN_FREE_BYTES + MAX_CACHE_BYTES:
            raise RuntimeError('Need 1 GiB disk reserve plus 256 MiB inventory allowance.')
        sources, profiles, hashes = load_inputs(repo)
        master = read_targets(sources['curated_master'], profiles['curated_master']['rows'])
        baseline = read_targets(sources['baseline_manifest'], profiles['baseline_manifest']['rows'])
        targets = target_contract(master, baseline)
        contract = {'version': VERSION, 'project': PROJECT, 'bucket': BUCKET, 'years': YEARS,
                    'source_sha256': hashes, 'listing_limit': LIMIT, 'label_column_unchanged': 'label_48h_final'}
        cp = work / 'input_contract.json'
        if cp.exists() and document(cp) != contract:
            raise ValueError('This inventory was created with different inputs; use a new --work directory.')
        if not cp.exists():
            save_json(cp, contract)
        cache = work / 'listings'; cache.mkdir(exist_ok=True)
        per_year, receipts = {}, []
        for year in YEARS:
            per_year[year], receipt = fetch_listing(year, cache)
            receipts.append(receipt)
        rows, extras, yearly, canaries = reconcile(targets, per_year)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        out = work / 'reports' / stamp; out.mkdir(parents=True, exist_ok=False)
        write_csv(out/'target_object_register.csv', rows, list(rows[0]))
        write_csv(out/'yearly_object_coverage.csv', yearly, list(yearly[0]))
        write_csv(out/'objects_without_target.csv', extras, ['listed_year','name','bytes','generation','possible_sample_id','reason','delete_authorised'])
        write_csv(out/'timing_canary_candidates.csv', canaries, list(rows[0]) + ['selection_reason'])
        counts = dict(Counter(r['object_status'] for r in rows))
        report = {'version': VERSION, 'status': FINAL_OK, 'created_utc': now(),
                  'input_contract': contract, 'listing_receipts': receipts,
                  'master_targets': len(rows), 'status_counts': counts,
                  'yearly': yearly, 'boundary_case': next((r for r in rows if r['sample_id']==BOUNDARY_SID), None),
                  'canary_candidate_count': len(canaries), 'canary_images_downloaded': 0,
                  'source_labels_replaced': False, 'training_authorised': False,
                  'limitations': [
                      'Listings are current-object metadata as observed at the recorded times, not an atomic archive snapshot.',
                      'Cached successful listings are deliberately reused, not silently refreshed.',
                      'Missing means no matching object in the specified yearly prefix, not absence everywhere or a negative flare label.',
                      'Names, nonzero byte sizes and listed checksums do not validate NPZ contents.',
                      'Storage creation/update times and sample-ID clocks are NOT AIA observation times.',
                      'Neither the 180-second tolerance nor no-future-image condition has been tested in this run.',
                      'Next canary selection is deterministic and not a representative statistical sample or a completeness certificate.',
                      'Catalogue completeness, reporting availability, qualified histories and final split/calibration design remain open.']}
        save_json(out/'archive_reconciliation_report.json', report)
        lines = ['# AIA archive object reconciliation', '', '**Status: object inventory only; no training clearance.**', '',
                 f'Locked master target rows: {len(rows):,}.', '', '|Stored year|Targets|Exact nonempty|Not found|Zero-byte|Multiple|Alternate|', '|---|---:|---:|---:|---:|---:|---:|']
        for r in yearly:
            lines.append('|'+ '|'.join(str(r[k]) for k in ('stored_year','expected_targets','exact_nonempty','not_found','zero_byte','ambiguous_ids','alternate_paths'))+'|')
        lines += ['', '## Interpretation', ''] + ['- '+t for t in report['limitations']]
        (out/'research_log_archive_reconciliation.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        save_json(out/'COMPLETE.json', {'status': FINAL_OK, 'output_sha256': {f.name:sha256(f) for f in sorted(out.iterdir()) if f.is_file()}})
        print('\n===== ARCHIVE RECONCILIATION RESULTS =====')
        print('Stored year | targets | exact nonempty | not found | zero-byte | multiple | alternate')
        for r in yearly:
            print(' | '.join(str(r[k]) for k in ('stored_year','expected_targets','exact_nonempty','not_found','zero_byte','ambiguous_ids','alternate_paths')))
        print('MASTER STATUS COUNTS:', json.dumps(counts, sort_keys=True))
        br = report['boundary_case']
        print('BOUNDARY SAMPLE:', br['sample_id'] if br else 'not in target table', '|', br['object_status'] if br else 'UNKNOWN')
        print('Next timing-canary candidates:', len(canaries), '(no images downloaded)')
        print('STATUS:', FINAL_OK)
        print('REPORT:', out/'archive_reconciliation_report.json')
        print('RESEARCH LOG:', out/'research_log_archive_reconciliation.md')
        print('No bucket writes, original label changes, Git operations, model loading or training.')
        return 0
    except Exception as exc:
        save_json(work/'last_failure.json', {'status': 'INVENTORY_STOPPED_NO_COMPLETENESS_CLAIM', 'time_utc': now(), 'error_type': type(exc).__name__, 'error': str(exc)})
        print(f'\nSTOP: {exc}', file=sys.stderr)
        print('No missing-object totals or training clearance are inferred from a failed listing.', file=sys.stderr)
        return 1
    finally:
        lockfile.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
