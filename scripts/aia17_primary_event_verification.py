#!/usr/bin/env python3
"""Collect primary-source evidence for the three flagged 2024 event groups.

Default: local review and bounded code-lineage scan only. --fetch-public permits
at most THREE HTTPS GETs to NOAA's archive, each with a 128 KiB payload limit.
No gcloud, GPU, package installation, Git writes, label/time repair or deduplication.
Downloaded primary-source reports and review outputs are NEW files outside the repo.
A candidate match is evidence for review, never an automatic correction.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = 'aia17-primary-event-verification-v1'
BASE = 'https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/solar_event_reports'
DEFAULT_REVIEW = 'event_time_20260915T103446628773Z'
MAX_BYTES = 128 * 1024
NA = {'', 'none', 'null', 'nan', 'nat'}


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def json_object(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 25 * 1024**2:
        raise ValueError(f'Missing or unexpectedly large JSON input: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'Expected a JSON object: {path}')
    return data


def parse_report(payload: bytes, day: str) -> dict:
    """Preserve SWPC HHMM/qualifier tokens. Do not infer rollover or fill a peak."""
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError('Empty or oversized NOAA report.')
    text = payload.decode('utf-8-sig')
    if '<html' in text.lower() or '<!doctype' in text.lower():
        raise ValueError('Server returned HTML, not the requested report.')
    product = re.search(r'^:Product:\s*(\S+)', text, re.M)
    dt = re.search(r'^:Date:\s*(\d{4})\s+(\d{2})\s+(\d{2})\s*$', text, re.M)
    if not product or product[1] != day + 'events.txt' or not dt or ''.join(dt.groups()) != day:
        raise ValueError('NOAA report product/date does not match the requested day.')
    if 'Space Weather Prediction Center' not in text:
        raise ValueError('Expected NOAA SWPC attribution not present.')
    parsed = []
    unparsed = []
    # Event number, optional preferred-observation '+', begin/max/end, obs/Q/type,
    # band, GOES class, remaining particulars and optional region.
    pattern = re.compile(
        r'^\s*(\d+)\s+(\+\s+)?(\S+)\s+(\S+)\s+(\S+)\s+'
        r'(\S+)\s+(\S+)\s+XRA\s+(\S+)\s+([ABCMX]\d+(?:\.\d+)?)\s*(.*?)\s*$')
    for number, line in enumerate(text.splitlines(), 1):
        if not re.search(r'\bXRA\b', line) or line.lstrip().startswith('#'):
            continue
        m = pattern.fullmatch(line)
        if not m:
            unparsed.append({'line_number': number, 'line': line})
            continue
        event_id, preferred, begin, peak, end, obs, quality, band, cls, tail = m.groups()
        extras = tail.split()
        region = extras[-1] if extras and re.fullmatch(r'\d{4,5}', extras[-1]) else None
        parsed.append({'line_number': number, 'event_number_raw': event_id,
            'preferred_marker_raw': '+' if preferred else '', 'begin_raw': begin,
            'max_raw': peak, 'end_raw': end, 'observer': obs, 'quality': quality,
            'band': band, 'class_raw': cls, 'region_raw': region,
            'particulars_after_class_raw': tail, 'raw_line': line,
            'all_clock_tokens_plain_HHMM': all(re.fullmatch(r'(?:[01]\d|2[0-3])[0-5]\d', x)
                                             is not None for x in (begin, peak, end))})
    if not parsed and not unparsed:
        raise ValueError('No XRA entries in this report; target cannot be verified.')
    headers = [line for line in text.splitlines() if line.startswith(':')]
    return {'product_date': day, 'header_lines': headers, 'xra_records': parsed,
            'unparsed_xra_lines': unparsed,
            'interpretation': 'Raw catalogue tokens only. No time-scale, date-rollover or event-identity repair.'}


def targets_from_review(review: dict) -> list[dict]:
    """Use this exact forensic output, not independently guessed flare IDs."""
    events = review['events']
    grouped = {}
    for g in events['duplicate_groups']:
        grouped[g['audit_key']] = {'audit_key': g['audit_key'],
            'reason': 'duplicate_key_with_exported_field_review', 'records': g['records']}
    for rec in events['time_anomaly_records']:
        grouped.setdefault(rec['audit_key'], {'audit_key': rec['audit_key'],
            'reason': 'event_time_order', 'records': []})['records'].append(rec)
    targets = []
    for group in grouped.values():
        raw = group['records'][0]['raw']
        start = datetime.fromisoformat(raw['event_starttime'])
        if start.tzinfo is not None:
            raise ValueError('New explicitly offset event source requires protocol review.')
        if start.year != 2024:
            raise ValueError('This targeted source check is intentionally limited to 2024.')
        region = raw['NOAA_AR_clean'].strip()
        if not re.fullmatch(r'13\d{3}', region):
            raise ValueError('Unexpected full NOAA region format; do not guess mapping.')
        group.update({'day_from_stored_start': start.strftime('%Y%m%d'),
            'begin_from_stored_start': start.strftime('%H%M'), 'class_from_export': raw['fl_goescls'],
            'full_noaa_from_export': region,
            'candidate_archive_region_tokens': [region, region[-4:]],
            'mapping_note': 'Full ID and its four-digit suffix are candidate matching tokens ONLY, not a general AR-renumbering rule.'})
        targets.append(group)
    if len(targets) > 3 or len({t['day_from_stored_start'] for t in targets}) > 3:
        raise ValueError('More than three target groups/days. Increase scope only after review.')
    return targets


def candidate_match(target: dict, primary: dict) -> dict:
    # Exact raw-clock and class candidates, irrespective of region, remain visible.
    time_class = [r for r in primary['xra_records']
        if r['begin_raw'] == target['begin_from_stored_start']
        and r['class_raw'] == target['class_from_export']]
    same_region = [r for r in time_class if r['region_raw'] in target['candidate_archive_region_tokens']]
    return {'audit_key': target['audit_key'], 'status': 'CANDIDATES_ONLY_NO_CORRECTION',
        'time_class_candidates': time_class, 'time_class_region_candidates': same_region,
        'raw_unique_max_tokens': sorted({r['max_raw'] for r in same_region}),
        'raw_unique_end_tokens': sorted({r['end_raw'] for r in same_region}),
        'warning': 'Catalogue candidates need manual/source-lineage review. A missing, qualified or conflicting MAX is not replaced. Clock matching does not establish export-time-scale provenance.'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect needs explicit review; avoid hidden requests or host changes.
        raise urllib.error.HTTPError(req.full_url, code, 'Redirect refused by request cap', headers, fp)


def fetch_report(day: str, destination: Path) -> tuple[bytes, dict]:
    if not re.fullmatch(r'2024\d{4}', day):
        raise ValueError('Date outside fixed 2024 archive scope.')
    url = f'{BASE}/{day[:4]}/{day[4:6]}/{day}events.txt'
    request = urllib.request.Request(url, headers={'User-Agent': VERSION,
                                                  'Accept': 'text/plain', 'Accept-Encoding': 'identity'})
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=25) as response:
        length = response.headers.get('Content-Length')
        if length and int(length) > MAX_BYTES:
            raise ValueError('Declared NOAA response exceeds the byte cap.')
        payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValueError('NOAA response exceeds the byte cap.')
        metadata = {'url': url, 'http_status': response.status,
            'last_modified': response.headers.get('Last-Modified'),
            'etag': response.headers.get('ETag'), 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
            'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
    # Save even a bounded unexpected response, for diagnosing a server/schema change.
    with destination.open('xb') as f:
        f.write(payload)
    return payload, metadata


def code_lineage_scan(repo: Path) -> dict:
    """Search local code cells only; no Git fetch, execution, secrets or outputs."""
    needles = ('hek_mx_ar_flares', 'label_48h_ar_specific', 'event_peaktime',
               'to_datetime', 'HEKClient', 'a.hek', 'hek.search', 'event_starttime')
    roots = ('src', 'scripts', 'notebooks', 'harp_block_miner')
    files = []; snippets = []; read_bytes = 0; skipped = []
    for root_name in roots:
        root = repo / root_name
        if not root.is_dir() or root.is_symlink(): continue
        for parent, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in
                             {'executed','__pycache__','venv','train_venv'} and not (Path(parent)/d).is_symlink())
            for name in sorted(names):
                path = Path(parent)/name
                if path.is_symlink() or path.suffix not in {'.py','.ipynb'}: continue
                if name.startswith(('aia17_', 'run17_')) or name.startswith(('17A_', '17B_')): continue
                files.append(path)
    for path in files[:300]:
        n = path.stat().st_size
        if n > 5*1024**2 or read_bytes+n > 30*1024**2:
            skipped.append(str(path.relative_to(repo))); continue
        read_bytes += n
        try:
            raw = path.read_text(encoding='utf-8')
            if path.suffix == '.ipynb':
                nb = json.loads(raw)
                blocks = []
                for idx, cell in enumerate(nb.get('cells', [])):
                    if cell.get('cell_type') != 'code': continue
                    src = cell.get('source', '')
                    blocks.append((f'code_cell_{idx}', ''.join(src) if isinstance(src,list) else src))
            else: blocks = [('file', raw)]
            retained = 0
            for where, text in blocks:
                lines = text.splitlines()
                for i, line in enumerate(lines):
                    matched = [s for s in needles if s in line]
                    if not matched or retained >= 6: continue
                    a=max(0,i-2); b=min(len(lines),i+4)
                    snippets.append({'path':str(path.relative_to(repo)), 'file_sha256':digest_file(path),
                        'block':where, 'line_in_block':i+1, 'needles':matched,
                        'excerpt':'\n'.join(f'{j+1}: {lines[j][:400]}' for j in range(a,b))})
                    retained += 1
        except (OSError,ValueError,TypeError) as exc:
            skipped.append(f'{path.relative_to(repo)}: {exc}')
    return {'bytes_scanned':read_bytes, 'candidate_files':len(files), 'snippets':snippets,
        'skipped':skipped, 'scope_note':'Bounded local code/cell excerpts, not proof of executed extraction lineage. Sparse-checkout omissions, other repos and historical revisions are not covered.'}


def run(args) -> Path:
    run_dir = args.run.expanduser().resolve()
    review_file = (args.review.expanduser().resolve() if args.review else
                   run_dir.parent.parent/'reviews'/DEFAULT_REVIEW/'event_time_review.json')
    review = json_object(review_file)
    if review.get('status') != 'FORENSIC_REVIEW_COMPLETE_NO_REPAIRS':
        raise ValueError('Not the expected completed forensic review.')
    if Path(review['source_run']).resolve() != run_dir:
        raise ValueError('Forensic source run differs from requested Stage-1 run.')
    for rel,key in [('stage1_report.json','stage1_report_sha256'),
                    ('source_lock_snapshot.json','source_lock_snapshot_sha256')]:
        if digest_file(run_dir/rel) != review[key]:
            raise ValueError(f'{rel} changed since the forensic review.')
    event_file = Path(review['events']['source_path']).expanduser().resolve()
    if digest_file(event_file) != review['events']['source_sha256']:
        raise ValueError('Cached event source changed since the forensic review.')
    targets = targets_from_review(review)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = run_dir.parent.parent/'reviews'/f'primary_sources_{stamp}'
    out.mkdir(parents=True, exist_ok=False)
    originals = {str(p):digest_file(p) for p in (review_file, run_dir/'stage1_report.json',
                 run_dir/'source_lock_snapshot.json', event_file)}
    result = {'version':VERSION, 'started_utc':datetime.now(timezone.utc).isoformat(),
        'forensic_review':str(review_file), 'input_sha256':originals,
        'network_authorised':bool(args.fetch_public), 'targets':targets,
        'primary_sources':[], 'comparisons':[], 'repairs_applied':False, 'training_authorised':False,
        'event_scale_provenance':'Still unverified for the full exported event catalogue',
        'requests_cap':3, 'response_cap_bytes_each':MAX_BYTES}
    print('===== 17B PRIMARY-SOURCE VERIFICATION =====', flush=True)
    print('Verifying three event groups; original sources and labels stay unchanged.', flush=True)
    for day in sorted({t['day_from_stored_start'] for t in targets}):
        source = {'day':day}
        try:
            if args.offline_dir:
                source_path = args.offline_dir.expanduser().resolve()/(day+'events.txt')
                if source_path.stat().st_size > MAX_BYTES: raise ValueError('Oversized offline report.')
                payload = source_path.read_bytes()
                source.update({'mode':'offline_file', 'path':str(source_path),
                               'sha256':hashlib.sha256(payload).hexdigest()})
                (out/(day+'events.txt')).write_bytes(payload)
            elif args.fetch_public:
                print('Fetching NOAA report:',day,flush=True)
                payload,meta=fetch_report(day,out/(day+'events.txt'))
                source.update(meta)
            else:
                source['status']='NOT_FETCHED_NO_NETWORK_PERMISSION'
                result['primary_sources'].append(source); continue
            primary = parse_report(payload,day)
            source.update(primary); source['status']='PRIMARY_REPORT_READ'
            for target in targets:
                if target['day_from_stored_start'] == day:
                    result['comparisons'].append(candidate_match(target,primary))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            source['status']='SOURCE_UNRESOLVED'
            source['error']=f'{type(exc).__name__}: {exc}'
        result['primary_sources'].append(source)
    result['code_lineage_scan']=code_lineage_scan(args.repo.expanduser().resolve())
    result['uq_protocol_presence']={rel:(args.repo.expanduser()/rel).is_file() for rel in (
        'docs/TRUSTWORTHY_RESEARCH_STANDARD.md','docs/AIA_UQ_CALIBRATION_PROTOCOL.md',
        'configs/aia_uq_calibration_protocol.json')}
    if any(digest_file(Path(p)) != h for p,h in originals.items()):
        raise ValueError('An input changed during source verification. Review not accepted.')
    result['status']='PRIMARY_EVIDENCE_COLLECTED_REVIEW_REQUIRED_NO_REPAIRS'
    report=out/'primary_source_review.json'
    report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('\n===== PRIMARY-SOURCE RESULTS =====')
    for source in result['primary_sources']:
        print(source['day'],source['status'],source.get('error',''))
        if source.get('unparsed_xra_lines'):
            print('Unparsed XRA lines:',json.dumps(source['unparsed_xra_lines']))
    for comparison in result['comparisons']:
        print('\nCATALOGUE KEY:',comparison['audit_key'])
        print('Matching raw start/class/region candidates:',len(comparison['time_class_region_candidates']))
        for rec in comparison['time_class_region_candidates']:
            print(rec['raw_line'])
        print('Raw MAX tokens:',comparison['raw_unique_max_tokens'])
        print('Raw END tokens:',comparison['raw_unique_end_tokens'])
        if not comparison['time_class_region_candidates']:
            print('Same time/class without region restriction:',json.dumps(comparison['time_class_candidates']))
    print('\n===== LOCAL LINEAGE EXCERPTS (NOT EXECUTION PROOF) =====')
    # Prefer actual export/client references over ubiquitous generic time parsing.
    snippets=result['code_lineage_scan']['snippets']
    rank=lambda s: (0 if any(x in s['needles'] for x in ('hek_mx_ar_flares','HEKClient','hek.search','a.hek'))
                    else 1 if 'label_48h_ar_specific' in s['needles'] else 2)
    for snip in sorted(snippets,key=rank)[:8]:
        print('\n',snip['path'],snip['block'],snip['line_in_block'])
        print(snip['excerpt'])
    print('Total saved lineage excerpts:',len(snippets))
    print('UQ files:',json.dumps(result['uq_protocol_presence']))
    print('\nSTATUS:',result['status'])
    print('REPORT:',report)
    print('Raw reports are in the same new directory. No originals, labels, IDs, or Git files were changed.')
    return out


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=Path.home()/'aia17_metadata_stage1'/'runs'/'20260915T005020436079Z')
    parser.add_argument('--review',type=Path)
    parser.add_argument('--repo',type=Path,default=Path.home()/'solar_flare_aia')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--fetch-public',action='store_true',help='Allow up to 3 bounded public NOAA HTTP requests (no Google Cloud calls).')
    mode.add_argument('--offline-dir',type=Path,help='Use supplied original SWPC daily text reports without network access.')
    args=parser.parse_args()
    try:
        run(args); return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'STOP: {type(exc).__name__}: {exc}\nNo source repair or training attempted.',file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
