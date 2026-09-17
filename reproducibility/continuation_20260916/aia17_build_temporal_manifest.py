#!/usr/bin/env python3
"""17C preparation: build a versioned, NOMINAL history-object index offline.

Uses the completed object register and canonical issue-time diagnostics. No network,
source edits, relabelling, training, Git commands or package installation. It does
NOT infer exposure end-times, product availability, or label validity from a nominal
lag. The strict local loader below refuses unverified channel-time evidence.

Default three-frame candidate experiment: nominal slots t-288, t-192, t-96 minutes.
This is a new proposed experiment, not a rewrite of previous snapshot benchmarks.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

VERSION = '17c-nominal-history-index-v1'
LAGS_MINUTES = (288, 192, 96)  # Oldest to newest; exact nominal slots, no row shift.
CHANNELS = (94, 131, 171, 193, 211, 335)
KNOWN_BAD_FRAME = '20240714_0724_HARP11520_NOAA13753'
INVENTORY_RUN = '20260916T073559880010Z'
TIME_RUN = 'time_label_impact_20260915T172829490191Z'
INPUT_HASHES = {
    'register': 'b4bbf9098d2005cfacd7eff7649fdbac3b82fc55162fcbfb822024b1abcd6931',
    'clock_table': 'f950276f473574b717914d630ea2591245037f262bdc0e2962a74db68d78bb39',
}
SID_RE = re.compile(r'(?P<ymd>\d{8})_(?P<hm>\d{4})_HARP(?P<harp>\d+)_NOAA(?P<noaa>\d+)')
TAI_RE = re.compile(r'(\d{4})\.(\d{2})\.(\d{2})_(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)_TAI')
EXACT = 'EXACT_NONEMPTY_OBJECT'
AVAILABLE = 'NOMINAL_HISTORY_OBJECTS_AVAILABLE_TIMING_PENDING'
INCOMPLETE = 'NOMINAL_HISTORY_INCOMPLETE_OR_EXCLUDED'
MIN_DISK_FREE = 1024 ** 3
MAX_SOURCE_BYTES = 250 * 1024**2


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()


def check_file(path: Path, expected: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'Missing input or unexpected symbolic link: {path}')
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError(f'Input exceeds the bounded metadata size: {path}')
    if digest(path) != expected:
        raise ValueError(f'Input hash differs from the recorded completed run: {path}')


def tai_tick(raw: str) -> int:
    """Uniform TAI coordinate in integer microseconds; NOT naive UTC arithmetic.

    Raw fields must explicitly end in _TAI. TAI has no inserted leap seconds;
    UTC conversion is reused from the previous verified diagnostics, not repeated.
    """
    m = TAI_RE.fullmatch(raw)
    if not m:
        raise ValueError(f'Explicit raw TAI required: {raw!r}')
    t = datetime.fromisoformat(f'{m[1]}-{m[2]}-{m[3]}T{m[4]}')
    delta = t - datetime(1970, 1, 1)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def bool_int(s: str) -> int:
    if s not in ('0', '1'):
        raise ValueError(f'Expected an unchanged binary indicator, got {s!r}')
    return int(s)


def csv_rows(path: Path, required: set[str]):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f, strict=True)
        fields = r.fieldnames or []
        if len(set(fields)) != len(fields) or not required.issubset(fields):
            raise ValueError(f'Unexpected CSV schema: {path}')
        for row in r:
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'Malformed CSV row {r.line_num}: {path}')
            yield row


@dataclass(slots=True)
class Sample:
    sid: str
    harp: int
    noaa: int
    tick: int
    raw_tai: str
    original_clock: str
    utc: str
    end_utc: str
    year: int
    label: int
    baseline: int
    extension: int
    label_review: int
    event_scale_status: str
    followup_status: str
    object_status: str = ''
    uri: str = ''
    generation: str = ''
    object_bytes: int = 0


def load_inputs(clock_path: Path, register_path: Path, expected_rows: int = 141644) -> dict[str, Sample]:
    samples: dict[str, Sample] = {}
    required = {'sample_id', 'HARPNUM', 'NOAA_AR_clean', 'T_REC_raw_TAI',
                'T_REC_dt_original', 'T_REC_utc_derived', 'forecast_end_utc_48_SI_hours',
                'stored_year', 'original_label_48h_final', 'in_baseline_manifest',
                'in_extension', 'utc_hypothesis_differs_from_original_label',
                'event_scale_status', 'followup_status', 'training_authorised'}
    for r in csv_rows(clock_path, required):
        sid = r['sample_id']; m = SID_RE.fullmatch(sid)
        if not m or sid in samples:
            raise ValueError(f'Duplicate/unsupported target identifier: {sid}')
        harp, noaa = int(r['HARPNUM']), int(r['NOAA_AR_clean'])
        if (harp, noaa) != (int(m['harp']), int(m['noaa'])):
            raise ValueError(f'Region identity mismatch: {sid}')
        raw = r['T_REC_raw_TAI']; tick = tai_tick(raw)
        old = datetime.fromisoformat(r['T_REC_dt_original'])
        if old.tzinfo is not None or old.strftime('%Y%m%d_%H%M') != sid[:13]:
            raise ValueError(f'Original sample clock mismatch: {sid}')
        if tai_tick(old.strftime('%Y.%m.%d_%H:%M:%S.%f_TAI')) != tick:
            raise ValueError(f'Raw TAI and preserved clock disagree: {sid}')
        year = int(r['stored_year'])
        if year != old.year or not 2010 <= year <= 2026:
            raise ValueError(f'Unsupported stored-year assignment: {sid}')
        if not r['T_REC_utc_derived'].endswith('Z') or not r['forecast_end_utc_48_SI_hours'].endswith('Z'):
            raise ValueError(f'Canonical UTC fields absent: {sid}')
        # These were converted in the hash-locked earlier audit; do not reinterpret them.
        if r['training_authorised'] not in ('False', 'false', '0'):
            raise ValueError('Unexpected earlier training-authorisation state.')
        samples[sid] = Sample(sid, harp, noaa, tick, raw, r['T_REC_dt_original'],
            r['T_REC_utc_derived'], r['forecast_end_utc_48_SI_hours'], year,
            bool_int(r['original_label_48h_final']), bool_int(r['in_baseline_manifest']),
            bool_int(r['in_extension']), bool_int(r['utc_hypothesis_differs_from_original_label']),
            r['event_scale_status'], r['followup_status'])
    if len(samples) != expected_rows:
        raise ValueError(f'Clock-table count differs from locked run: {len(samples)} != {expected_rows}')
    seen = set()
    for r in csv_rows(register_path, {'sample_id', 'HARPNUM', 'NOAA_AR_clean', 'stored_issue_time',
            'stored_year', 'original_label', 'in_baseline', 'object_status', 'expected_uri',
            'generation', 'object_bytes'}):
        sid = r['sample_id']
        if sid not in samples or sid in seen:
            raise ValueError(f'Unknown/duplicate object-register target: {sid}')
        seen.add(sid); s = samples[sid]
        if (int(r['HARPNUM']), int(r['NOAA_AR_clean']), int(r['stored_year']),
            int(r['original_label']), int(r['in_baseline'])) != (s.harp, s.noaa, s.year, s.label, s.baseline):
            raise ValueError(f'Object and clock identities/labels disagree: {sid}')
        if datetime.fromisoformat(r['stored_issue_time']) != datetime.fromisoformat(s.original_clock):
            raise ValueError(f'Object and clock times disagree: {sid}')
        root = 'samples_npz' if s.year <= 2024 else 'jsoc_2025_2026_production_v1/samples_npz'
        expected_uri = f'gs://suryabench-sharp-pipeline-bamidele/{root}/{s.year}/{sid}.npz'
        if r['expected_uri'] != expected_uri:
            raise ValueError(f'Object path does not match the frozen archive layout: {sid}')
        s.object_status, s.uri = r['object_status'], r['expected_uri']
        s.generation = r['generation']; s.object_bytes = int(r['object_bytes'] or 0)
        if s.object_status == EXACT and (not s.generation.isdecimal() or s.object_bytes <= 0):
            raise ValueError(f'Exact object lacks its pinned version or positive size: {sid}')
    if seen != set(samples):
        raise ValueError('Object register does not cover the complete clock table.')
    return samples


def build_index(samples: dict[str, Sample]):
    index: dict[tuple[int, int, int], Sample] = {}
    for s in samples.values():
        key = (s.harp, s.noaa, s.tick)
        if key in index:
            raise ValueError('Duplicate region/nominal-time entries; no arbitrary choice permitted.')
        index[key] = s
    return index


def candidate_record(target: Sample, index) -> dict:
    frames = []
    for lag in LAGS_MINUTES:
        desired = target.tick - lag * 60 * 1_000_000
        s = index.get((target.harp, target.noaa, desired))
        reason = ('NOMINAL_SLOT_NOT_IN_CURATED_TARGET_TABLE' if s is None else
                  'KNOWN_SOURCE_SLOT_MISMATCH' if s.sid == KNOWN_BAD_FRAME else
                  'HISTORY_OBJECT_NOT_EXACT_NONEMPTY' if s.object_status != EXACT else '')
        frames.append({'lag_minutes': lag, 'requested_slot_tai_us': desired,
            'history_sample_id': s.sid if s else None,
            'raw_T_REC_TAI': s.raw_tai if s else None,
            'record_utc': s.utc if s else None,
            'object_uri': s.uri if s else None,
            'object_generation': s.generation if s else None,
            'object_bytes': s.object_bytes if s else None,
            'object_status': s.object_status if s else 'NO_CURATED_RECORD',
            'selection_reason': reason or 'EXACT_NOMINAL_SLOT_AND_NONEMPTY_OBJECT',
            'nominal_candidate': not bool(reason),
            'channel_timing_status': 'NOT_ATTACHED_NOT_INFERRED_FROM_NOMINAL_LAG'})
    complete = all(f['nominal_candidate'] for f in frames)
    return {'version': VERSION, 'target_sample_id': target.sid,
        'HARPNUM': target.harp, 'NOAA_AR_clean': target.noaa, 'stored_year': target.year,
        'issue_raw_TAI': target.raw_tai, 'issue_tai_us': target.tick,
        'issue_utc': target.utc, 'forecast_end_utc_48_SI_hours': target.end_utc,
        'original_label_48h_final': target.label, 'label_replaced': False,
        'label_boundary_review_required': bool(target.label_review),
        'event_scale_status': target.event_scale_status, 'followup_status': target.followup_status,
        'in_baseline_manifest': bool(target.baseline), 'in_extension': bool(target.extension),
        'target_current_image_status': target.object_status,
        'target_current_image_required_for_this_history_index': False,
        'history_status': AVAILABLE if complete else INCOMPLETE, 'frames': frames,
        'split': 'UNASSIGNED', 'training_authorised': False}


def validate_frame_evidence(record: dict, frame: dict, evidence: dict) -> None:
    """Fail closed on actual channel-time evidence; nominal lag alone cannot pass.

    Times must already be on the uniform integer-microsecond TAI coordinate. The
    supplied verified bound is on contributing observations, not a mean-exposure
    proxy. This gate does not certify historical product/publication availability.
    """
    required = {'history_sample_id': frame['history_sample_id'], 'object_uri': frame['object_uri'],
                'object_generation': frame['object_generation'], 'HARPNUM': record['HARPNUM'],
                'NOAA_AR_clean': record['NOAA_AR_clean']}
    if any(evidence.get(k) != v for k, v in required.items()):
        raise ValueError('Timing evidence is not tied to this exact frame/region/object version.')
    if not re.fullmatch(r'[0-9a-f]{64}', str(evidence.get('npz_sha256', ''))):
        raise ValueError('A verified whole-NPZ SHA256 is required for loader use.')
    channels = evidence.get('channels', [])
    if sorted(c.get('wavelength', -1) for c in channels) != list(CHANNELS):
        raise ValueError('Exactly six wavelength-specific timing records are required.')
    for ch in channels:
        mid = ch.get('midpoint_tai_us'); end = ch.get('contributing_end_tai_us')
        if type(mid) is not int or type(end) is not int:
            raise ValueError('Verified integer TAI times are required, not nominal/file-name guesses.')
        if ch.get('end_bound_verified') is not True or not ch.get('source_record') or not ch.get('conversion_provenance'):
            raise ValueError('Actual source provenance and verified contributing-time bound are required.')
        if abs(mid - frame['requested_slot_tai_us']) > 180 * 1_000_000:
            raise ValueError('Channel observation misses its historical slot tolerance.')
        if end < mid or mid > record['issue_tai_us'] or end > record['issue_tai_us']:
            raise ValueError('Channel observations extend beyond issue time or have invalid end ordering.')


def load_local_sequence(record: dict, local_objects: dict, timing_evidence: dict) -> dict:
    """Strict, no-download loader for a future verified local canary.

    Returns (time, channel, height, width) plus the original manifest target and
    metadata, not permission for training. local_objects keys are (URI,generation).
    timing_evidence keys are history_sample_id; see README for full schema.
    """
    import numpy as np
    if record.get('history_status') != AVAILABLE or len(record.get('frames', [])) != 3:
        raise ValueError('Three complete nominal history-object candidates are required.')
    if record.get('label_boundary_review_required'):
        raise ValueError('Target label is pending the separate boundary decision.')
    if type(record.get('issue_tai_us')) is not int:
        raise ValueError('Canonical integer TAI issue coordinate required.')
    if type(record.get('original_label_48h_final')) is not int or record['original_label_48h_final'] not in (0,1):
        raise ValueError('The preserved binary manifest target is required.')
    if tuple(f.get('lag_minutes') for f in record['frames']) != LAGS_MINUTES:
        raise ValueError('Historical sequence must use the specified chronological lag order.')
    if len({f.get('history_sample_id') for f in record['frames']}) != 3:
        raise ValueError('A historical frame cannot be repeated to fill a missing step.')
    for f in record['frames']:
        if (f.get('requested_slot_tai_us') != record['issue_tai_us']-f['lag_minutes']*60*1_000_000
            or not f.get('nominal_candidate') or f.get('history_sample_id') == KNOWN_BAD_FRAME):
            raise ValueError('Historical slot does not follow the fixed-issue candidate protocol.')
    frames_out = []
    for f in record['frames']:
        ev = timing_evidence.get(f['history_sample_id'], {})
        validate_frame_evidence(record, f, ev)
        key = (f['object_uri'], f['object_generation'])
        if key not in local_objects:
            raise ValueError('Verified history object is not cached locally; no automatic download.')
        path = Path(local_objects[key])
        if path.stat().st_size != f['object_bytes'] or digest(path) != ev['npz_sha256']:
            raise ValueError('Local NPZ bytes do not match their pinned verified receipt.')
        with zipfile.ZipFile(path) as z:
            members = z.infolist()
            if len(members) > 64 or len({m.filename for m in members}) != len(members):
                raise ValueError('Invalid NPZ member count or duplicated members.')
            if sum(m.file_size for m in members) > 32 * 1024**2:
                raise ValueError('NPZ expanded-size limit exceeded.')
            if any(m.filename.startswith('/') or '..' in Path(m.filename).parts for m in members):
                raise ValueError('Unsafe NPZ member names.')
        with np.load(path, allow_pickle=False) as z:
            x = z['x']
            if x.shape != (512, 512, 6) or x.dtype != np.dtype('float32') or not np.isfinite(x).all():
                raise ValueError('Expected a finite float32 512x512x6 tensor.')
            if str(z['sample_id'].item()) != f['history_sample_id'] or int(z['HARPNUM'].item()) != record['HARPNUM'] or int(z['NOAA_AR_clean'].item()) != record['NOAA_AR_clean']:
                raise ValueError('NPZ identity does not match the selected historical sample.')
            declaration = z['wavelengths'] if 'wavelengths' in z else z['channels']
            parsed = tuple(int(str(v).removeprefix('aia')) for v in declaration.tolist())
            if parsed != CHANNELS:
                raise ValueError('NPZ channel order differs from the experimental contract.')
            # Deliberately never read z['y'] or z['label_48h_final'] as the target.
            frames_out.append(np.transpose(x, (2, 0, 1)))
    return {'x_tchw': np.stack(frames_out), 'original_manifest_target': record['original_label_48h_final'],
            'target_sample_id': record['target_sample_id'], 'training_authorised': False,
            'label_and_product_availability_certified': False}


def built_in_checks() -> None:
    raw = '2024.01.02_04:48:00_TAI'; tick = tai_tick(raw)
    def row(sid, delta=0, **extra):
        s = Sample(sid, 1, 10001, tick+delta, raw, '2024-01-02 04:48:00',
                   '2024-01-02T04:47:23Z', '2024-01-04T04:47:23Z', 2024, 1, 0, 0, 0, 'UNVERIFIED', 'NOT_VERIFIED')
        s.object_status=EXACT; s.uri='gs://synthetic/'+sid; s.generation='1'; s.object_bytes=1
        for k,v in extra.items(): setattr(s,k,v)
        return s
    target = row('target'); vals = [target]+[row(f'h{lag}', -lag*60*1_000_000) for lag in LAGS_MINUTES]
    rec = candidate_record(target, build_index({x.sid:x for x in vals}))
    if rec['history_status'] != AVAILABLE or rec['original_label_48h_final'] != 1:
        raise ValueError('Internal history-index check failed.')
    if [f['lag_minutes'] for f in rec['frames']] != [288,192,96]:
        raise ValueError('Internal chronological frame order check failed.')
    rec2 = candidate_record(target, build_index({x.sid:x for x in vals[:-1]}))
    if rec2['history_status'] != INCOMPLETE:
        raise ValueError('Missing history did not fail closed.')
    if tai_tick('2017.01.01_00:00:00_TAI') - tai_tick('2016.12.31_23:59:59_TAI') != 1_000_000:
        raise ValueError('TAI-coordinate interval check failed.')
    try:
        validate_frame_evidence(rec, rec['frames'][0], {})
    except ValueError:
        pass
    else:
        raise ValueError('Missing real timing evidence did not block the loader.')
    print('Local index self-checks: passed (not new astronomy conversion tests).', flush=True)


def write_results(samples: dict[str, Sample], out: Path, inputs: dict) -> dict:
    index = build_index(samples)
    summary = defaultdict(Counter); groups = defaultdict(set)
    reasons = Counter(); all_states = Counter(); label_review_count = 0
    seqpath = out/'temporal_sequence_candidates.jsonl.gz'
    with gzip.open(seqpath, 'wt', encoding='utf-8', newline='\n', compresslevel=6) as f:
        for n, s in enumerate(sorted(samples.values(), key=lambda x:(x.tick,x.harp,x.noaa)),1):
            rec = candidate_record(s,index)
            f.write(json.dumps(rec, separators=(',',':'), allow_nan=False)+'\n')
            ready = rec['history_status'] == AVAILABLE
            key=(s.year,s.label); c=summary[key]
            c.update({'targets':1,'nominal_history_objects_available':int(ready),
                      'incomplete_or_excluded_history':int(not ready),
                      'available_history_with_current_image_missing':int(ready and s.object_status != EXACT),
                      'boundary_label_review_targets':s.label_review})
            if ready: groups[key].add((s.harp,s.noaa))
            all_states[rec['history_status']]+=1; label_review_count += s.label_review
            for frame in rec['frames']:
                if not frame['nominal_candidate']: reasons[frame['selection_reason']]+=1
            if n%20000==0: print(f'  Indexed {n:,} targets into three nominal history slots',flush=True)
    rows=[]
    for (year,label), c in sorted(summary.items()):
        rows.append({'stored_year':year,'original_label':label,**dict(c),
                     'distinct_HARP_NOAA_pairs_with_nominal_history':len(groups[(year,label)])})
    with (out/'sequence_coverage_by_year_and_original_label.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader();w.writerows(rows)
    report={'version':VERSION,'status':'TEMPORAL_INDEX_BUILT_TIMING_AND_LABEL_CLEARANCE_PENDING',
        'created_utc':datetime.now(timezone.utc).isoformat(),'input_files':inputs,
        'experimental_status':'PROPOSED_HISTORY_ONLY_DESIGN_NOT_HISTORICAL_RELABELLING',
        'nominal_lags_minutes_oldest_to_newest':list(LAGS_MINUTES),'channels':list(CHANNELS),
        'nominal_match':'exact raw TAI coordinate; not previous three rows; same HARP and NOAA',
        'requested_history_horizon_hours':6,'forecast_horizon_hours_unchanged':48,
        'actual_channel_slot_tolerance_seconds':180,'target_rows':len(samples),
        'history_status_counts':dict(all_states),'missing_or_excluded_slot_counts':dict(reasons),
        'label_boundary_review_target_count':label_review_count,'year_label_coverage':rows,
        'known_excluded_frame_pairings':[KNOWN_BAD_FRAME],
        'frames_have_all_observation_headers':False,'training_authorised':False,
        'original_labels_changed':False,'splits_frozen':False,'model_fitted':False,
        'limitations':[
            'Nominal history completeness is not verified exposure-time or product-availability completeness.',
            'Only samples in the curated table are used as historical frames; other raw source frames may exist.',
            'The current target image is not required for a history-only sequence; absent history is not a negative label.',
            'Every target remains in this index, including incomplete histories and the unresolved boundary target.',
            'The known stale source/target pairing is excluded as a frame, not repaired or deleted.',
            'The one conditional label disagreement is flagged; labels are not silently replaced.',
            'Same HARP/NOAA is a conservative identity restriction, not independent region-group certification.',
            'Full split/purge/calibration design, label follow-up and per-modality contributing times remain separate gates.',
            'SHARP row time alone is not verification of its contributing observation window or availability.',
            'AIA/SHARP/GOES final experiment ladder and separate PINN/PIML scope are not changed by this index.',
            'The local loader is implemented and fixture-tested, not run here against a verified real three-frame sequence.'
        ]}
    (out/'temporal_manifest_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    lines=['# Temporal candidate index — implementation checkpoint','',
        '**Candidate objects indexed; scientific training clearance remains pending.**','',
        f'Target rows: {len(samples):,}. Original labels and source objects unchanged.',
        'Nominal frame slots: t−288, t−192, t−96 minutes; original 48-hour forecast window unchanged.',
        'This is an explicit proposed history-only experiment, not replacement of prior snapshot benchmarks.','',
        '## Nominal object support','',json.dumps(dict(all_states),indent=2),'','## Remaining checks','']
    lines += ['- '+x for x in report['limitations']]
    (out/'research_log_temporal_manifest.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    root=Path.home()/'aia17_metadata_stage1'
    p.add_argument('--inventory-dir',type=Path,default=root/'archive_reconciliation_v1/reports'/INVENTORY_RUN)
    p.add_argument('--time-dir',type=Path,default=root/'reviews'/TIME_RUN)
    p.add_argument('--output-root',type=Path,default=root/'temporal_manifest_v1')
    p.add_argument('--self-test-only',action='store_true')
    args=p.parse_args(argv)
    try:
        print('===== 17C PREPARATION: BUILD TEMPORAL SAMPLE INDEX =====',flush=True)
        print('Existing local outputs only; no cloud calls, downloads, input repairs or training.',flush=True)
        built_in_checks()
        if args.self_test_only: return 0
        register=args.inventory_dir.expanduser()/'target_object_register.csv'
        clocktable=args.time_dir.expanduser()/'sample_time_and_window_diagnostics.csv.gz'
        inputs={}
        for key,path in [('register',register),('clock_table',clocktable)]:
            print(f'Checking pinned local input: {key}',flush=True)
            check_file(path,INPUT_HASHES[key]);inputs[key]={'path':str(path.resolve()),'sha256':INPUT_HASHES[key]}
        samples=load_inputs(clocktable,register)
        print(f'Loaded {len(samples):,} existing target records; building history index.',flush=True)
        rootout=args.output_root.expanduser().resolve()
        repo=(Path.home()/'solar_flare_aia').resolve()
        if rootout==repo or repo in rootout.parents:
            raise ValueError('Generated data must stay outside the Git repository.')
        # Guard against accidentally mixing generated outputs into source-run directories.
        for src in (register.parent.resolve(),clocktable.parent.resolve()):
            if rootout==src or src in rootout.parents:
                raise ValueError('Do not put new outputs inside a completed source-run directory.')
        ancestor=rootout
        while not ancestor.exists(): ancestor=ancestor.parent
        if shutil.disk_usage(ancestor).free < MIN_DISK_FREE:
            raise ValueError('Less than 1 GiB free disk; no output has been started.')
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        out=rootout/'reports'/stamp;out.mkdir(parents=True,exist_ok=False)
        (out/'INCOMPLETE.txt').write_text('Only accept outputs when COMPLETE.json is present.\n')
        report=write_results(samples,out,inputs)
        # Detect input mutation during index generation.
        for v in inputs.values(): check_file(Path(v['path']),v['sha256'])
        output_hashes={f.name:digest(f) for f in out.iterdir() if f.is_file() and f.name!='INCOMPLETE.txt'}
        (out/'COMPLETE.json').write_text(json.dumps({'status':report['status'],'output_sha256':output_hashes},indent=2)+'\n')
        (out/'INCOMPLETE.txt').unlink()
        with zipfile.ZipFile(out/'summary_for_review.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
            for name in ['temporal_manifest_report.json','sequence_coverage_by_year_and_original_label.csv','research_log_temporal_manifest.md','COMPLETE.json']:
                z.write(out/name,arcname=name)
        print('\n===== TEMPORAL MANIFEST BUILD RESULTS =====')
        print('Target rows retained:',report['target_rows'])
        print('History status counts:',json.dumps(report['history_status_counts']))
        print('Year | label | targets | nominal complete | incomplete | region pairs')
        for r in report['year_label_coverage']:
            print(' | '.join(str(r[k]) for k in ['stored_year','original_label','targets','nominal_history_objects_available','incomplete_or_excluded_history','distinct_HARP_NOAA_pairs_with_nominal_history']))
        print('STATUS:',report['status'])
        print('MANIFEST:',out/'temporal_sequence_candidates.jsonl.gz')
        print('SEND THIS SMALL FILE:',out/'summary_for_review.zip')
        print('No source labels, source images, previous results, cloud resources or Git files changed.')
        return 0
    except Exception as exc:
        print(f'\nSTOP: {type(exc).__name__}: {exc}',file=sys.stderr)
        print('Original inputs remain unchanged; incomplete output is never a training manifest.',file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
