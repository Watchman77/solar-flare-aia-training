#!/usr/bin/env python3
"""Create a PROPOSED chronological cross-cycle role sidecar from an existing index.

Offline, standard-library only. Never runs model fitting, cloud/Git commands,
image reads, label repair, or timing certification. Originals stay unchanged.

The fixed first-benchmark proposal is printed before use. It is NOT a claim that
all of Cycle 24 is used for weight fitting, nor a silently frozen replacement for
an earlier protocol. Inspect retained development support before freezing it.
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

VERSION = 'aia17-cross-cycle-role-proposal-v1'
SOURCE_VERSION = '17c-nominal-history-index-v1'
SOURCE_STATUS = 'TEMPORAL_INDEX_BUILT_TIMING_AND_LABEL_CLEARANCE_PENDING'
SOURCE_RUN = '20260916T143622218859Z'
AVAILABLE = 'NOMINAL_HISTORY_OBJECTS_AVAILABLE_TIMING_PENDING'
INCOMPLETE = 'NOMINAL_HISTORY_INCOMPLETE_OR_EXCLUDED'
LAGS = (288, 192, 96)
CHANNELS = (94, 131, 171, 193, 211, 335)
KNOWN_BAD_FRAME = '20240714_0724_HARP11520_NOAA13753'
SID = re.compile(r'(?P<date>\d{8}_\d{4})_HARP(?P<h>\d+)_NOAA(?P<n>\d+)')
MAX_FILE_BYTES = 250 * 1024**2
MAX_ROWS = 250000
MAX_LINE_BYTES = 128 * 1024
MAX_UNCOMPRESSED_BYTES = 1200 * 1024**2
MIN_FREE_BYTES = 1024**3
UTC = timezone.utc


def dt(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError('Expected an explicit canonical UTC timestamp ending in Z.')
    parsed = datetime.fromisoformat(value[:-1] + '+00:00')
    if parsed.utcoffset().total_seconds() != 0:
        raise ValueError('Expected UTC.')
    return parsed


@dataclass(frozen=True)
class Role:
    name: str
    start: str
    end: str
    purpose: str
    development: bool = False

    @property
    def lower(self): return dt(self.start)
    @property
    def upper(self): return dt(self.end)


# A fixed proposal, not selected by Cycle-25 model performance. The 2014 subperiod
# support is deliberately measured rather than assumed. No silent fallback split.
ROLES = (
    Role('train', '2010-01-01T00:00:00Z', '2014-01-01T00:00:00Z',
         'Fit preprocessing and model weights on this subset of Cycle 24.', True),
    Role('model_validation', '2014-01-01T00:00:00Z', '2014-07-01T00:00:00Z',
         'Model/epoch/hyperparameter selection, not weight fitting.', True),
    Role('calibration_fit', '2014-07-01T00:00:00Z', '2015-01-01T00:00:00Z',
         'Fit a prespecified calibrator to the frozen selected model.', True),
    Role('threshold_selection', '2015-01-01T00:00:00Z', '2016-01-01T00:00:00Z',
         'Assess calibration and select operating threshold; not independent test.', True),
    Role('late_period_diagnostic', '2016-01-01T00:00:00Z', '2020-01-01T00:00:00Z',
         'Post-freeze diagnostic only; this block includes the late-2019 cycle transition.'),
    Role('early_cycle25_diagnostic', '2020-01-01T00:00:00Z', '2021-01-01T00:00:00Z',
         'Separate 2020 low-activity diagnostic, never a development set.'),
    Role('independent_cycle25_test', '2021-01-01T00:00:00Z', '2026-01-01T00:00:00Z',
         'Primary held-out 2021-2025 cross-cycle evaluation, no tuning/refitting.'),
    Role('supplementary_2026', '2026-01-01T00:00:00Z', '2027-01-01T00:00:00Z',
         'Only the actually covered 2026 records, not a complete-year claim.'),
)
ROLE_MAP = {r.name:r for r in ROLES}
OUTSIDE = 'outside_proposed_periods'


def get_role(issue: datetime) -> str:
    for r in ROLES:
        if r.lower <= issue < r.upper: return r.name
    return OUTSIDE


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2), b''): h.update(b)
    return h.hexdigest()


def regular(path: Path):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'Missing or symlinked input: {path}')
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f'Input exceeds metadata cap: {path}')


def load_source(folder: Path):
    names = ('temporal_manifest_report.json', 'temporal_sequence_candidates.jsonl.gz')
    marker = folder / 'COMPLETE.json'
    regular(marker)
    completed = json.loads(marker.read_text(encoding='utf-8'))
    if completed.get('status') != SOURCE_STATUS:
        raise ValueError('Expected the completed temporal-index status, not training clearance.')
    locks = {'COMPLETE.json':sha(marker)}
    for name in names:
        path = folder/name; regular(path)
        expected = completed.get('output_sha256', {}).get(name)
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError(f'Missing recorded checksum: {name}')
        if sha(path) != expected: raise ValueError(f'Input checksum mismatch: {name}')
        locks[name] = expected
    report = json.loads((folder/names[0]).read_text(encoding='utf-8'))
    if (report.get('version') != SOURCE_VERSION or report.get('status') != SOURCE_STATUS
        or report.get('nominal_lags_minutes_oldest_to_newest') != list(LAGS)
        or report.get('channels') != list(CHANNELS)
        or report.get('forecast_horizon_hours_unchanged') != 48
        or report.get('training_authorised') is not False
        or report.get('splits_frozen') is not False):
        raise ValueError('Unexpected source-index protocol; no implicit migration.')
    n = report.get('target_rows')
    if type(n) is not int or not 0 < n <= MAX_ROWS: raise ValueError('Unsupported row count.')
    return report, locks


def records(path: Path):
    total = 0
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for i in range(MAX_ROWS+1):
            line = f.readline(MAX_LINE_BYTES + 1)
            if not line: break
            total += len(line.encode('utf-8'))
            if len(line)>MAX_LINE_BYTES or total>MAX_UNCOMPRESSED_BYTES or i>=MAX_ROWS:
                raise ValueError('Bounded index read exceeded; input not accepted.')
            rec = json.loads(line)
            if not isinstance(rec, dict): raise ValueError('Expected a JSON record.')
            yield rec


@dataclass(slots=True)
class Target:
    sid: str
    harp: int
    noaa: int
    issue: datetime
    end: datetime
    tick: int
    label: int
    role: str
    ready: bool
    label_review: bool


def parse_target(rec: dict) -> Target:
    sid = rec.get('target_sample_id', ''); match = SID.fullmatch(sid)
    if not match or rec.get('version') != SOURCE_VERSION: raise ValueError('Unsupported target schema.')
    h, n = rec.get('HARPNUM'), rec.get('NOAA_AR_clean')
    if type(h) is not int or type(n) is not int or h<=0 or n<=0:
        raise ValueError(f'Invalid region IDs: {sid}')
    if (h,n)!=(int(match['h']),int(match['n'])): raise ValueError(f'Identity mismatch: {sid}')
    issue, end = dt(rec['issue_utc']), dt(rec['forecast_end_utc_48_SI_hours'])
    # The source performs physical-time conversion; do not recompute 48h in UTC.
    # Allow only the known 48h representation, including an inserted leap second.
    if not 172798 <= (end-issue).total_seconds() <= 172802:
        raise ValueError(f'Unexpected preserved forecast interval: {sid}')
    tick = rec.get('issue_tai_us'); label = rec.get('original_label_48h_final')
    if type(tick) is not int or type(label) is not int or label not in (0,1):
        raise ValueError(f'Missing canonical tick or original binary label: {sid}')
    if (rec.get('split') != 'UNASSIGNED' or rec.get('training_authorised') is not False
        or rec.get('label_replaced') is not False):
        raise ValueError('Source already assigned or altered; refusing silent replacement.')
    if type(rec.get('label_boundary_review_required')) is not bool:
        raise ValueError('Missing explicit target-label review flag.')
    status = rec.get('history_status')
    if status not in (AVAILABLE,INCOMPLETE): raise ValueError('Unexpected history status.')
    fs = rec.get('frames')
    if not isinstance(fs,list) or len(fs)!=3 or tuple(f.get('lag_minutes') for f in fs)!=LAGS:
        raise ValueError('Expected the unchanged oldest-to-newest three-frame design.')
    for frame in fs:
        if (type(frame.get('nominal_candidate')) is not bool or
            frame.get('requested_slot_tai_us') != tick-frame['lag_minutes']*60*1000000):
            raise ValueError('Historical slot identity disagrees with source protocol.')
        if frame.get('history_sample_id') == KNOWN_BAD_FRAME and frame['nominal_candidate']:
            raise ValueError('Known excluded source/target pairing was accepted as a frame.')
    ready = status==AVAILABLE
    if ready != all(f['nominal_candidate'] for f in fs): raise ValueError('History status/frames disagree.')
    return Target(sid,h,n,issue,end,tick,label,get_role(issue),ready,
                  rec['label_boundary_review_required'])


class UnionFind:
    def __init__(self): self.parent = {}
    def find(self,x):
        self.parent.setdefault(x,x)
        root=x
        while self.parent[root]!=root: root=self.parent[root]
        while self.parent[x]!=x: old=self.parent[x]; self.parent[x]=root; x=old
        return root
    def union(self,a,b):
        a,b=self.find(a),self.find(b)
        if a!=b: self.parent[max(a,b)]=min(a,b)


def scan(path: Path, report: dict):
    targets={}; graph=UnionFind(); states=Counter()
    for i, rec in enumerate(records(path),1):
        t=parse_target(rec)
        if t.sid in targets: raise ValueError(f'Duplicate target: {t.sid}')
        targets[t.sid]=t; graph.union(('H',t.harp),('N',t.noaa))
        states[rec['history_status']]+=1
        if i%25000==0: print(f'  Read {i:,} existing candidates (no images)',flush=True)
    if len(targets)!=report['target_rows'] or dict(states)!=report['history_status_counts']:
        raise ValueError('Row/status totals differ from the completed source report.')
    members=defaultdict(list)
    for node in graph.parent: members[graph.find(node)].append(node)
    ids={root:'ARCOMP_'+hashlib.sha256(json.dumps(sorted(nodes)).encode()).hexdigest()[:16]
         for root,nodes in members.items()}
    components={}; sid_group={}
    for t in targets.values():
        root=graph.find(('H',t.harp)); gid=ids[root]; sid_group[t.sid]=gid
        c=components.setdefault(gid, {'roles':set(),'harps':set(),'noaa_ids':set(),'rows':0})
        c['roles'].add(t.role);c['harps'].add(t.harp);c['noaa_ids'].add(t.noaa);c['rows']+=1
    return targets, sid_group, components


def reasons_for(rec, t, targets, component):
    reasons=[]
    if t.role==OUTSIDE: reasons.append('OUTSIDE_PROPOSED_PERIODS')
    if len(component['roles'])>1: reasons.append('REGION_COMPONENT_SPANS_ROLES')
    if not t.ready: reasons.append('NOMINAL_HISTORY_INCOMPLETE_OR_EXCLUDED')
    if t.label_review: reasons.append('TARGET_LABEL_BOUNDARY_REVIEW_PENDING')
    role=ROLE_MAP.get(t.role)
    if role and t.end >= role.upper:
        reasons.append('FORECAST_ENDPOINT_REACHES_NEXT_ROLE')
    for frame in rec['frames']:
        sid=frame.get('history_sample_id')
        if sid is None:
            if frame['nominal_candidate']: raise ValueError('A nominal candidate has no identity.')
            continue
        f=targets.get(sid)
        if f is None: raise ValueError(f'Historical target absent from source index: {sid}')
        if (f.harp,f.noaa)!=(t.harp,t.noaa) or f.tick!=frame['requested_slot_tai_us']:
            raise ValueError('A historical frame uses the wrong region or nominal time.')
        if f.issue != dt(frame['record_utc']): raise ValueError('Historical UTC lineage mismatch.')
        if f.role!=t.role: reasons.append('AIA_NOMINAL_HISTORY_CROSSES_ROLE')
        if f.issue>t.issue: raise ValueError('Historical record follows its target.')
        if frame['nominal_candidate']:
            if (frame.get('object_status') != 'EXACT_NONEMPTY_OBJECT'
                or not str(frame.get('object_uri','')).startswith('gs://suryabench-sharp-pipeline-bamidele/')
                or not str(frame.get('object_generation','')).isdecimal()
                or type(frame.get('object_bytes')) is not int or frame['object_bytes']<=0):
                raise ValueError('Historical object lacks a valid locked reference.')
    return sorted(set(reasons))


def write_run(source: Path, out: Path, report, locks):
    path=source/'temporal_sequence_candidates.jsonl.gz'
    targets, memberships, components = scan(path,report)
    fields=['target_sample_id','issue_utc','original_label_48h_final','proposed_role',
            'region_component_id','nominal_history_complete','role_constraints_pass',
            'structural_exclusion_reasons','timing_clearance','label_clearance',
            'sharp_history_clearance','training_authorised']
    totals=defaultdict(Counter); supported=defaultdict(set); used_frames={}; seen=set(); reason_counts=Counter()
    output=out/'cross_cycle_role_assignments.csv.gz'
    with gzip.open(output,'wt',encoding='utf-8',newline='',compresslevel=6) as handle:
        w=csv.DictWriter(handle,fieldnames=fields);w.writeheader()
        for rec in records(path):
            t=targets[rec['target_sample_id']]; gid=memberships[t.sid]
            if t.sid in seen: raise ValueError('Duplicate source during second pass.')
            seen.add(t.sid)
            reasons=reasons_for(rec,t,targets,components[gid]); keep=not reasons
            row={'target_sample_id':t.sid,'issue_utc':rec['issue_utc'],
                 'original_label_48h_final':t.label,'proposed_role':t.role,
                 'region_component_id':gid,'nominal_history_complete':int(t.ready),
                 'role_constraints_pass':int(keep),'structural_exclusion_reasons':';'.join(reasons),
                 'timing_clearance':'PENDING_PER_OBJECT_SOURCE_EVIDENCE',
                 'label_clearance':'PENDING_CATALOGUE_AND_FOLLOWUP',
                 'sharp_history_clearance':'NOT_BUILT_OR_VERIFIED_BY_THIS_STEP',
                 'training_authorised':False}
            w.writerow(row)
            c=totals[t.role];c.update({'targets':1,'nominal_complete':int(t.ready),
                'role_retained':int(keep),'retained_original_positives':int(keep and t.label==1),
                'retained_original_negatives':int(keep and t.label==0)})
            if keep:
                supported[(t.role,'all')].add(gid)
                if t.label==1: supported[(t.role,'positive')].add(gid)
                for frame in rec['frames']:
                    key=(frame['object_uri'],str(frame['object_generation']))
                    if key in used_frames and used_frames[key]!=t.role:
                        raise ValueError('A pinned AIA object is shared across retained roles.')
                    used_frames[key]=t.role
            reason_counts.update(reasons)
    if seen!=set(targets): raise ValueError('Second pass did not preserve all targets.')
    role_rows=[]
    for r in ROLES:
        c=totals[r.name]
        role_rows.append({'role':r.name,'start_utc_inclusive':r.start,'end_utc_exclusive':r.end,
            **{k:c[k] for k in ['targets','nominal_complete','role_retained',
                'retained_original_positives','retained_original_negatives']},
            'retained_region_components':len(supported[(r.name,'all')]),
            'positive_region_components':len(supported[(r.name,'positive')])})
    if OUTSIDE in totals:
        c=totals[OUTSIDE]
        role_rows.append({'role':OUTSIDE,'start_utc_inclusive':'','end_utc_exclusive':'',
            **{k:c[k] for k in ['targets','nominal_complete','role_retained',
                'retained_original_positives','retained_original_negatives']},
            'retained_region_components':0,'positive_region_components':0})
    with (out/'cross_cycle_role_support.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(role_rows[0]));w.writeheader();w.writerows(role_rows)
    with (out/'region_components.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['component_id','roles','HARPNUM_values','NOAA_values','target_rows'])
        for gid,c in sorted(components.items()):
            w.writerow([gid,';'.join(sorted(c['roles'])),';'.join(map(str,sorted(c['harps']))),
                        ';'.join(map(str,sorted(c['noaa_ids']))),c['rows']])
    blockers=[]; warnings=[]
    for r in role_rows:
        if r['role'] in {x.name for x in ROLES if x.development}:
            if not r['retained_original_positives'] or not r['retained_original_negatives']:
                blockers.append(r['role']+': BOTH_CLASSES_NOT_PRESENT_AFTER_STRUCTURAL_EXCLUSIONS')
            if r['positive_region_components']<5:
                warnings.append(r['role']+': FEWER_THAN_5_POSITIVE_COMPONENTS_REVIEW_SUPPORT_NOT_A_SIGNIFICANCE_TEST')
    result={'version':VERSION,'status':'CROSS_CYCLE_ROLE_PROPOSAL_BUILT_NOT_FROZEN',
        'created_utc':datetime.now(UTC).isoformat(),'source_directory':str(source),
        'source_files_sha256':locks,'target_rows_preserved':len(targets),
        'source_index_history_status_counts':dict(Counter(AVAILABLE if t.ready else INCOMPLETE for t in targets.values())),
        'proposed_roles':[{'name':r.name,'start_utc_inclusive':r.start,
                          'end_utc_exclusive':r.end,'purpose':r.purpose} for r in ROLES],
        'role_support':role_rows,'structural_exclusion_reason_counts':dict(reason_counts),
        'reason_counts_can_overlap':True,'cross_role_region_components':sum(len(c['roles'])>1 for c in components.values()),
        'group_policy':'Conservative connected components of retained HARP-NOAA associations; exclude whole components spanning calendar roles.',
        'components_are_not_certified_independent_physical_regions':True,
        'retained_cross_role_pinned_aia_object_overlap':0,
        'development_structural_blockers':blockers,'development_support_warnings':warnings,
        'split_dates_frozen':False,'model_fitted':False,'preprocessing_fitted':False,
        'calibration_fitted':False,'threshold_selected':False,'training_authorised':False,
        'original_labels_changed':False,'cycle25_used_for_model_selection':False,
        'limitations':[
            'This is an explicit FIRST benchmark proposal. Only 2010-2013 fits model weights; it does not use all Cycle-24 data for fitting.',
            '2014 model-selection/calibration subperiods must have their retained support reviewed. No automatic date fallback.',
            '2015 is a threshold/calibration-assessment development set, not an independent test.',
            '2016-2019 diagnostics must not be used to revise the selected model; late 2019 spans the physical cycle transition.',
            'The 2021-2025 test period remains independent; 2020 and the covered portion of 2026 are separate.',
            'Only canonical timestamps and forecast endpoints already in the locked index are used; no new TAI/UTC conversion occurs.',
            '48-hour endpoint and AIA nominal-history boundary checks are structural; actual exposure and product availability are still pending.',
            'SHARP history construction, contributing observation windows, availability, and any further boundary embargo remain to be verified.',
            'A nominal history pass is not source-time clearance. Labels and continuous follow-up are still not certified.',
            'Region links are conservative identifier associations, not independently established physical-region identities.',
            'No calibration-method, significance threshold, model-selection metric or architecture is selected by this program.',
            'Retained class/group counts are based on original labels; diagnostic statistics are not performance results.',
            'A model-time or group cutoff can remove a whole region; excluded targets remain in the sidecar with their reasons.',
            'This new sidecar does not rewrite the source index, fit a model, authorize a GPU, or publish to GitHub.'
        ]}
    (out/'cross_cycle_assignment_report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (out/'first_cross_cycle_protocol_proposal.json').write_text(json.dumps({
        'status':'PROPOSED_FIRST_BENCHMARK_NOT_FROZEN','roles':result['proposed_roles'],
        'forecast_horizon_hours':48,'aia_lags_minutes':list(LAGS),'channels':list(CHANNELS),
        'test_fitting_allowed':False,'training_authorised':False,
        'pinn_track':'SEPARATE_20A_20B_20C','source_index_sha256':locks[path.name]
    },indent=2)+'\n',encoding='utf-8')
    (out/'research_log_cross_cycle_assignment.md').write_text(
        '# Cross-cycle role assignment proposal\n\n'
        'First benchmark proposal, not a frozen scientific or GPU-run approval.\n\n'
        +'\n'.join(f'- {r.name}: [{r.start}, {r.end}) — {r.purpose}' for r in ROLES)
        +'\n\nAll source targets and labels are preserved. Region-component exclusions and '
        'boundary checks are explicit; actual timing, label validity, SHARP support and '
        'development support remain to be cleared. No tests or experiment scores selected '
        'this calendar allocation.\n\n## Limitations\n\n'
        +'\n'.join('- '+x for x in result['limitations'])+'\n',encoding='utf-8')
    return result


def basic_checks():
    assert get_role(dt('2024-07-01T00:00:00Z'))=='independent_cycle25_test'
    assert get_role(dt('2014-06-30T23:59:59Z'))=='model_validation'
    assert get_role(dt('2014-07-01T00:00:00Z'))=='calibration_fit'
    u=UnionFind();u.union(('H',1),('N',10001));u.union(('H',2),('N',10001))
    assert u.find(('H',1))==u.find(('H',2))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    home=Path.home()/'aia17_metadata_stage1'
    p.add_argument('--input-dir',type=Path,default=home/'temporal_manifest_v1/reports'/SOURCE_RUN)
    p.add_argument('--output-root',type=Path,default=home/'cross_cycle_role_proposal_v1')
    p.add_argument('--self-test-only',action='store_true')
    a=p.parse_args(argv)
    try:
        basic_checks()
        print('===== CROSS-CYCLE ROLE PROPOSAL =====',flush=True)
        print('Existing index only; no downloads, fitting, relabelling, or Git operations.',flush=True)
        print('NEW FIRST-BENCHMARK PROPOSAL — NOT FROZEN:',flush=True)
        for r in ROLES: print(f'  {r.name}: [{r.start}, {r.end})',flush=True)
        if a.self_test_only: print('Basic local checks passed.');return 0
        source=a.input_dir.expanduser().resolve(); report, locks=load_source(source)
        dest=a.output_root.expanduser().resolve()
        if dest==source or source in dest.parents or dest in source.parents:
            raise ValueError('Output must be separate from the existing source-run directory.')
        repo=(Path.home()/'solar_flare_aia').resolve()
        if dest==repo or repo in dest.parents or any((x/'.git').exists() for x in [dest,*dest.parents]):
            raise ValueError('Generated outputs must stay outside a Git checkout.')
        ancestor=dest
        while not ancestor.exists():ancestor=ancestor.parent
        if shutil.disk_usage(ancestor).free<MIN_FREE_BYTES:raise ValueError('Less than 1 GiB free; no output started.')
        stamp=datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
        out=dest/'reports'/stamp;out.mkdir(parents=True,exist_ok=False)
        (out/'INCOMPLETE.txt').write_text('Accept this proposal only with COMPLETE.json. Not training clearance.\n')
        result=write_run(source,out,report,locks)
        for name,expected in locks.items():
            if sha(source/name)!=expected:raise ValueError('Source changed during processing: '+name)
        hashes={f.name:sha(f) for f in out.iterdir() if f.is_file() and f.name!='INCOMPLETE.txt'}
        (out/'COMPLETE.json').write_text(json.dumps({'status':result['status'],'output_sha256':hashes},indent=2)+'\n')
        (out/'INCOMPLETE.txt').unlink()
        bundle=out/'cross_cycle_summary_for_review.zip'
        with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for name in ['cross_cycle_assignment_report.json','cross_cycle_role_support.csv',
                         'region_components.csv','first_cross_cycle_protocol_proposal.json',
                         'research_log_cross_cycle_assignment.md','COMPLETE.json']:
                z.write(out/name,arcname=name)
        print('\n===== CROSS-CYCLE ASSIGNMENT RESULTS =====')
        print('All original targets retained:',result['target_rows_preserved'])
        print('Role | targets | nominal histories | retained after structural rules | positive | positive components')
        for row in result['role_support']:
            print(' | '.join(str(row[k]) for k in ['role','targets','nominal_complete','role_retained',
                'retained_original_positives','positive_region_components']))
        print('Development blockers:',json.dumps(result['development_structural_blockers']))
        print('Support warnings:',json.dumps(result['development_support_warnings']))
        print('STATUS:',result['status'])
        print('ROLE SIDECAR:',out/'cross_cycle_role_assignments.csv.gz')
        print('SEND THIS ONE SMALL FILE:',bundle)
        print('Originals unchanged. No real-sequence timing clearance, training, cloud or Git action.')
        return 0
    except Exception as exc:
        print(f'\nSTOP: {type(exc).__name__}: {exc}',file=sys.stderr)
        print('No original source data changed. Partial outputs are not an approved manifest.',file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
