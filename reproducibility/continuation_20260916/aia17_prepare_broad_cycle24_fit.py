#!/usr/bin/env python3
"""Propose a two-stage, broader Cycle-24 fit WITHOUT training or replacing v1.

Use only the existing checksum-locked nominal temporal index. Reserve whole
Cycle-24 HARP/NOAA components for calibration and threshold selection, use
forward-chaining development folds on the remaining components, then define a
broader final-refit pool spanning the available pre-December-2019 period.

Calibration/threshold reservations are RETROSPECTIVE REGION HOLDOUTS, not future-
period validation. The final Cycle-25 evaluation remains time-held-out. Output
is a separately versioned proposal, not a clearance, frozen split or fitted model.

No network, image reads, cloud commands, package installation or Git writes.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import zipfile

VERSION = 'aia17-broad-cycle24-finalfit-proposal-v2'
STATUS = 'BROAD_CYCLE24_FIT_PROPOSAL_BUILT_NOT_FROZEN'
HELPER_SHA256 = '1273dbbcf12fd554db40380bb7d10470e11b8b1b3b52076a5563483dcb460bc6'
UTC = timezone.utc
SEED = 'aia17-broad-cycle24-v2-20260916'
FOLD_YEARS = (2013, 2014, 2015)
DEV = 'cycle24_development'
FIT = 'cycle24_final_refit_pool'
CAL = 'cycle24_calibration_holdout'
THR = 'cycle24_threshold_holdout'
OUTSIDE = 'outside_proposal'
UNSUPPORTED = 'cycle24_no_structural_candidates'
PERIODS = (
    (DEV, '2010-01-01T00:00:00Z', '2019-12-01T00:00:00Z'),
    ('cycle25_early_diagnostic', '2019-12-01T00:00:00Z', '2021-01-01T00:00:00Z'),
    ('independent_cycle25_test', '2021-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
    ('supplementary_2026', '2026-01-01T00:00:00Z', '2027-01-01T00:00:00Z'),
)
# Month-level operational boundary convention, NOT an exact physical phase change.

def require(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024**2), b''): h.update(b)
    return h.hexdigest()


def stamp(): return datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')


def dt(value):
    require(isinstance(value, str) and value.endswith('Z'), 'Explicit UTC timestamp required.')
    return datetime.fromisoformat(value[:-1] + '+00:00')


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def load_helper(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f'Missing original role-reader script: {path}')
    require(sha(path) == HELPER_SHA256, 'Original role-reader script differs from the reviewed version. No automatic replacement.')
    spec = importlib.util.spec_from_file_location('_aia17_original_role_reader', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def period(issue):
    for name, lo, hi in PERIODS:
        if dt(lo) <= issue < dt(hi): return name
    return OUTSIDE


def period_bounds(name):
    return next(((dt(lo), dt(hi)) for n,lo,hi in PERIODS if n == name), None)


def scan_index(helper, source, report):
    # This uses the existing source-schema validation and graph builder, not v1's
    # role assignments. No existing assignment CSV is read or rewritten.
    targets, groups, old_components = helper.scan(source, report)
    component_periods = defaultdict(set)
    for t in targets.values(): component_periods[groups[t.sid]].add(period(t.issue))
    return targets, groups, component_periods, old_components


def base_reasons(rec, t, targets, groups, component_periods):
    p = period(t.issue)
    reasons = []
    if p == OUTSIDE: reasons.append('OUTSIDE_PROPOSED_PERIODS')
    if len(component_periods[groups[t.sid]]) > 1:
        reasons.append('REGION_COMPONENT_SPANS_OUTER_PERIODS')
    if not t.ready: reasons.append('NOMINAL_HISTORY_INCOMPLETE_OR_EXCLUDED')
    if t.label_review: reasons.append('TARGET_LABEL_BOUNDARY_REVIEW_PENDING')
    bounds = period_bounds(p)
    if bounds and t.end >= bounds[1]: reasons.append('FORECAST_ENDPOINT_REACHES_OUTER_BOUNDARY')
    for f in rec['frames']:
        sid = f.get('history_sample_id')
        if sid is None:
            require(not f['nominal_candidate'], 'Nominal candidate has no historical identity.')
            continue
        require(sid in targets, f'Historical record absent from index: {sid}')
        h = targets[sid]
        require((h.harp,h.noaa) == (t.harp,t.noaa) and h.tick == f['requested_slot_tai_us'],
                'Wrong-region or wrong-slot historical record.')
        require(h.issue == dt(f['record_utc']) and h.issue < t.issue,
                'Historical record clock disagrees with its saved lineage.')
        require(groups[sid] == groups[t.sid], 'Historical and target region components differ.')
        if period(h.issue) != p: reasons.append('AIA_HISTORY_CROSSES_OUTER_BOUNDARY')
        if f['nominal_candidate']:
            require(f.get('object_status') == 'EXACT_NONEMPTY_OBJECT'
                    and str(f.get('object_uri','')).startswith('gs://suryabench-sharp-pipeline-bamidele/')
                    and str(f.get('object_generation','')).isdecimal()
                    and type(f.get('object_bytes')) is int and f['object_bytes'] > 0,
                    'Historical object lacks valid pinned inventory metadata.')
    return sorted(set(reasons))


def reserve_groups(targets, groups, reasons):
    """80/10/10 approx by components in two label strata, NEVER by test labels.

    A positive component has at least one positive STRUCTURALLY ELIGIBLE Cycle-24
    target. This is retrospective split design, not a feature or proof of truth.
    No seed search or forced row-class balancing. Every row in a reserved group
    remains assigned with the group, including its negative snapshots.
    """
    strata = {}
    for t in targets.values():
        if period(t.issue) == DEV and not reasons[t.sid]:
            g = groups[t.sid]
            strata[g] = max(strata.get(g, 0), t.label)
    assignment = {}
    support = []
    for positive in (0, 1):
        ids = sorted([g for g,v in strata.items() if v == positive],
                     key=lambda g: (hashlib.sha256(f'{SEED}|{positive}|{g}'.encode()).hexdigest(),g))
        n = len(ids)
        # No fallback split when a stratum is too small. Return blockers for review.
        k = max(1, n // 10) if n >= 3 else 0
        for j,g in enumerate(ids):
            assignment[g] = CAL if j < k else THR if j < 2*k else FIT
        support.append({'positive_component_stratum': positive, 'components': n,
                        'calibration_components': k, 'threshold_components': k,
                        'refit_components': n-2*k})
    return assignment, support


def final_role(t, groups, assignment):
    p = period(t.issue)
    if p != DEV: return p
    return assignment.get(groups[t.sid], UNSUPPORTED)


def fold_role(t, year):
    lo, hi = dt(f'{year}-01-01T00:00:00Z'), dt(f'{year+1}-01-01T00:00:00Z')
    if period(t.issue) != DEV: return None
    if t.issue < lo: return 'train'
    if t.issue < hi: return 'validation'
    return None


def fold_reasons(t, rec, year, base, targets, groups, assignment, crossing):
    reasons = list(base)
    fr = fold_role(t, year)
    if fr is None: reasons.append('OUTSIDE_FORWARD_FOLD')
    if final_role(t,groups,assignment) != FIT:
        reasons.append('FINAL_HOLDOUT_NOT_AVAILABLE_FOR_MODEL_SELECTION')
    if groups[t.sid] in crossing: reasons.append('REGION_COMPONENT_SPANS_FOLD_TRAIN_VALIDATION')
    if fr:
        hi = dt(f'{year if fr=="train" else year+1}-01-01T00:00:00Z')
        if t.end >= hi: reasons.append('FORECAST_ENDPOINT_REACHES_FOLD_BOUNDARY')
        for f in rec['frames']:
            sid = f.get('history_sample_id')
            if sid and fold_role(targets[sid],year) != fr:
                reasons.append('AIA_HISTORY_CROSSES_FOLD_BOUNDARY')
    return sorted(set(reasons))


def write_csv(path, rows, fields):
    with Path(path).open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def build(helper, source_dir, output):
    source_report, locks = helper.load_source(source_dir)
    source = source_dir/'temporal_sequence_candidates.jsonl.gz'
    targets, groups, component_periods, old_components = scan_index(helper, source, source_report)
    reasons = {}
    for rec in helper.records(source):
        sid=rec['target_sample_id']
        reasons[sid]=base_reasons(rec,targets[sid],targets,groups,component_periods)
    assignment, reservation_support = reserve_groups(targets,groups,reasons)
    # Group split crossing is determined using ALL records, not just surviving
    # histories, so an unavailable frame cannot hide a train/validation link.
    crossing = {}
    for year in FOLD_YEARS:
        spans=defaultdict(set)
        for t in targets.values():
            fr=fold_role(t,year)
            if final_role(t,groups,assignment)==FIT and fr: spans[groups[t.sid]].add(fr)
        crossing[year]={g for g,roles in spans.items() if len(roles)>1}
    fields=['target_sample_id','issue_utc','stored_year','HARPNUM','NOAA_AR_clean',
            'original_label_48h_final','region_component_id','proposed_final_role',
            'nominal_history_complete','structural_candidate','exclusion_reasons',
            'source_timing_clearance','label_clearance','sharp_clearance','training_authorised']
    fold_fields=['fold_id','target_sample_id','region_component_id','fold_role',
                 'structural_candidate','exclusion_reasons']
    totals=defaultdict(Counter); year_totals=defaultdict(Counter)
    support=defaultdict(set); fold_counts=defaultdict(Counter); fold_support=defaultdict(set)
    owned={}; fold_owned={year:{} for year in FOLD_YEARS}; all_reasons=Counter()
    n=0
    final_path=output/'broad_cycle24_final_role_candidates.csv.gz'
    folds_path=output/'forward_development_fold_candidates.csv.gz'
    with gzip.open(final_path,'wt',encoding='utf-8',newline='',compresslevel=6) as fh, \
         gzip.open(folds_path,'wt',encoding='utf-8',newline='',compresslevel=6) as gh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
        fw=csv.DictWriter(gh,fieldnames=fold_fields);fw.writeheader()
        for rec in helper.records(source):
            n+=1;t=targets[rec['target_sample_id']];gid=groups[t.sid]
            role=final_role(t,groups,assignment);rr=list(reasons[t.sid])
            if role==UNSUPPORTED:rr.append('REGION_HAS_NO_ELIGIBLE_DEVELOPMENT_RECORD')
            rr=sorted(set(rr)); keep=not rr
            w.writerow(dict(zip(fields,[t.sid,rec['issue_utc'],rec['stored_year'],t.harp,t.noaa,
                t.label,gid,role,int(t.ready),int(keep),';'.join(rr),
                'PENDING_PER_OBJECT_EVIDENCE','PENDING_CATALOGUE_FOLLOWUP',
                'NOT_BUILT_BY_ROLE_ASSIGNMENT',False])))
            tally={'targets':1,'nominal_histories':int(t.ready),'retained':int(keep),
                   'positive':int(keep and t.label==1),'negative':int(keep and t.label==0)}
            totals[role].update(tally);year_totals[(role,rec['stored_year'])].update(tally)
            all_reasons.update(rr)
            if keep:
                support[(role,'all')].add(gid)
                if t.label: support[(role,'positive')].add(gid)
                for f in rec['frames']:
                    key=(f['object_uri'],str(f['object_generation']))
                    require(key not in owned or owned[key]==role,'Pinned AIA object shared across final roles.')
                    owned[key]=role
            if role==FIT:
                for year in FOLD_YEARS:
                    fr=fold_role(t,year)
                    if fr is None: continue
                    freasons=fold_reasons(t,rec,year,rr,targets,groups,assignment,crossing[year])
                    fk=not freasons; fold_id=f'cycle24_forward_validate_{year}'
                    fw.writerow(dict(zip(fold_fields,[fold_id,t.sid,gid,fr,int(fk),';'.join(freasons)])))
                    fold_counts[(fold_id,fr)].update({'targets':1,'retained':int(fk),
                        'positive':int(fk and t.label==1),'negative':int(fk and t.label==0)})
                    if fk:
                        fold_support[(fold_id,fr,'all')].add(gid)
                        if t.label:fold_support[(fold_id,fr,'positive')].add(gid)
                        for f in rec['frames']:
                            key=(f['object_uri'],str(f['object_generation']))
                            require(key not in fold_owned[year] or fold_owned[year][key]==fr,
                                    'Pinned AIA object shared within a forward train/validation fold.')
                            fold_owned[year][key]=fr
            if n%25000==0:print(f'  Assigned {n:,} existing target records; no images read.',flush=True)
    require(n==len(targets),'Output row count differs from input.')
    # Inputs remain unchanged; recheck the actual source streams after all passes.
    for name in ('temporal_manifest_report.json','temporal_sequence_candidates.jsonl.gz','COMPLETE.json'):
        require(sha(source_dir/name)==locks[name], f'Source changed during processing: {name}')
    role_rows=[]
    for role,c in sorted(totals.items()):
        role_rows.append({'role':role,**dict(c),'components':len(support[(role,'all')]),
                          'positive_components':len(support[(role,'positive')])})
    yr_rows=[{'role':role,'stored_year':year,**dict(c)} for (role,year),c in sorted(year_totals.items())]
    fr_rows=[]
    for year in FOLD_YEARS:
        fid=f'cycle24_forward_validate_{year}'
        for role in ('train','validation'):
            c=fold_counts[(fid,role)]
            fr_rows.append({'fold_id':fid,'role':role,
                            **{k:c[k] for k in ('targets','retained','positive','negative')},
                            'components':len(fold_support[(fid,role,'all')]),
                            'positive_components':len(fold_support[(fid,role,'positive')])})
    write_csv(output/'final_role_support.csv',role_rows,list(role_rows[0]))
    write_csv(output/'final_roles_by_year.csv',yr_rows,list(yr_rows[0]))
    write_csv(output/'forward_fold_support.csv',fr_rows,list(fr_rows[0]))
    group_rows=[]
    for gid,c in sorted(old_components.items()):
        group_rows.append({'component_id':gid,'outer_periods':';'.join(sorted(component_periods[gid])),
           'reserved_cycle24_role':assignment.get(gid,''),'HARPNUM_values':';'.join(map(str,sorted(c['harps']))),
           'NOAA_values':';'.join(map(str,sorted(c['noaa_ids']))),'target_rows':c['rows']})
    write_csv(output/'region_reservations.csv',group_rows,list(group_rows[0]))
    blockers=[]; warnings=[]
    rd={r['role']:r for r in role_rows}
    for role in (FIT,CAL,THR):
        r=rd.get(role,{})
        if not r.get('positive',0) or not r.get('negative',0):blockers.append(role+': BOTH_CLASSES_REQUIRED')
        if r.get('positive_components',0)<5:warnings.append(role+': FEWER_THAN_FIVE_POSITIVE_COMPONENTS')
    for r in fr_rows:
        key=r['fold_id']+'/'+r['role']
        if not r['positive'] or not r['negative']:blockers.append(key+': BOTH_CLASSES_REQUIRED')
        if r['positive_components']<5:warnings.append(key+': FEWER_THAN_FIVE_POSITIVE_COMPONENTS')
    for year in (2015,2016,2017):
        if year_totals[(FIT,year)]['retained']==0:
            warnings.append(f'FINAL_REFIT_NO_RETAINED_TARGETS_IN_{year}; no resampling to conceal this')
    protocol={
        'version':VERSION,'proposal_not_frozen':True,'model_fitted':False,'training_authorised':False,
        'source_index_unchanged':True,'original_v1_role_assignment_unchanged':True,
        'outer_periods':[{'role':n,'start_inclusive':lo,'end_exclusive':hi} for n,lo,hi in PERIODS],
        'december_2019_boundary':'2019-12-01 is an operational month-boundary convention, not an exact physical transition instant.',
        'reserved_fraction_of_each_component_stratum':{'final_fit_pool_approximately':0.8,'calibration_approximately':0.1,'threshold_approximately':0.1},
        'integer_allocation':'k=max(1,n//10) if n>=3 else 0; first k calibration, next k threshold, remaining final fit; same rule for both strata.',
        'reservation_seed':SEED,'reservation_strata':'Any original-positive structurally eligible Cycle-24 target in component vs none. Test labels never used.',
        'reservation_unit':'Whole connected HARP/NOAA component, with all its positive and negative snapshots.',
        'final_calibration_design':'RETROSPECTIVE_REGION_HELDOUT_WITHIN_CYCLE24_NOT_CHRONOLOGICALLY_FUTURE',
        'model_selection':'Forward train-before-validation folds at 2013, 2014, 2015 from final-fit pool only; remove fold-crossing components and purge endpoints/history.',
        'final_refit':'After hyperparameters and training duration are fixed from the development folds, fit on the broader eligible fit pool through November 2019. Never include reserved calibration/threshold groups.',
        'final_calibration':'Fit only on reserved calibration groups to final-model predictions. Old debug scalers and earlier-model calibrators/thresholds are not reusable.',
        'threshold_selection':'Assess prespecified calibration candidates and select operating threshold using only threshold-holdout groups. This is development, not independent performance.',
        'test_protocol':'Freeze model/preprocessing/calibrator/threshold/ensemble weights before 2021-2025 testing. Same frozen pipeline for available 2026. No test-score-based method choice.',
        'repeated_folds':'A fitting-pool record may be validation in an earlier development fold and training in a later one. No train/validation overlap is permitted WITHIN each fold.',
        'shared_object_policy':'No identical generation-pinned AIA object across final roles or across train/validation within a development fold.',
        'no_performance_tuning_of_assignment':True,'model_selection_performance_used':False,
        'cycle25_labels_used_for_assignment':False,
        'label_counts_note':'Original labels in test rows are only copied and counted for reporting, never used in reservation selection.',
        'input_history':'Three frames at lags 288/192/96 minutes; SHARP full temporal-window policy remains a separate implementation.',
        'label_horizon':'Original 48-physical-hour endpoint is preserved from the canonical index; no labels replaced.',
        'pinn_piml':'Separate; unchanged.',
        'remaining_clearance':'Per-object timing, SHARP contributing times/quality, event labels, complete follow-up and reporting latency are NOT certified by this proposal.',
        'support_warning':'Five-positive-component warning is a simple screen, not proof of calibration adequacy or statistical significance.',
        'data_dependence_limitation':'Whole-AR holdout reduces direct region reuse but does not guarantee independence across simultaneous solar regions or remove temporal distribution shift.',
        'scientific_scope':'Candidate design for retrospective cross-cycle research; not proof of historical operational availability.'}
    write_json(output/'broad_cycle24_protocol_PROPOSED.json',protocol)
    result={'version':VERSION,'status':STATUS,'created_utc':datetime.now(UTC).isoformat(),
        'source_directory':str(source_dir),'source_files_sha256':locks,
        'original_role_reader_sha256':HELPER_SHA256,'target_rows_preserved':n,
        'source_index_nominal_counts':source_report['history_status_counts'],
        'role_support':role_rows,'support_by_stored_year':yr_rows,'forward_fold_support':fr_rows,
        'reservation_support_by_component_stratum':reservation_support,
        'outer_crossing_components':sum(len(p)>1 for p in component_periods.values()),
        'structural_exclusion_reason_counts':dict(all_reasons),'reason_counts_overlap':True,
        'cross_final_role_pinned_objects':0,'within_fold_train_validation_pinned_objects':0,
        'structural_blockers':blockers,'support_warnings':warnings,
        'warning_does_not_certify_support':True,'source_index_rewritten':False,
        'v1_assignment_rewritten':False,'model_fitted':False,'training_authorised':False,
        'final_dates_frozen':False,'test_predictions_or_scores_computed':False,
        'final_calibration_is_chronological':False,
        'next_if_accepted':'Generate full SHARP feature arrays on these pinned memberships, then score prespecified CPU development baselines. Final fits/testing remain gated by separate scientific checks.'}
    write_json(output/'broad_cycle24_fit_report.json',result)
    note='''# Broader Cycle-24 final-fit proposal — 16 September 2026

17C four-sequence AIA+SHARP integration was reported as successful by the user.
This step does not repeat that test and does not review or certify its unseen JSON.

This is a separate proposed experiment, not a silent rewrite of v1. Retain the
v1 canary assignments and old snapshot benchmarks. For the main design, reserve
whole Cycle-24 region components approximately 10% for calibration and 10% for
threshold assessment within positive/negative component strata; the remaining
approximately 80% are a broader fitting pool. Fractions refer to groups, not rows.
No test label or model score selects the split and no seed is searched.

Use chronological forward development folds within that fitting pool. After
selection, refit from scratch on all eligible fitting-pool observations through
November 2019, including 2015–2017 wherever retained. Refit preprocessing too.
Holdout groups stay excluded from every model-development and final-model fit.
Calibrate the final model on the calibration holdout, assess prespecified
calibration choices and choose a threshold on the threshold holdout, then freeze.
The 2021–2025 test and covered 2026 extension remain time-held-out evaluations.

IMPORTANT: the final within-Cycle-24 calibration/threshold design is a
RETROSPECTIVE REGION HOLDOUT, not a future-period chronological holdout. It does
not estimate future-regime calibration; that is assessed on the independent
cycle. It trades chronological calibration ordering for broader fitting-year
coverage. Adopting it requires an explicit protocol decision. A strict future-
period calibration alternative is not implemented by this file.

All targets and original labels remain preserved with structural exclusions.
Region components are linked identifiers, not certified independent physical
regions. Nominal history availability and these assignments do not certify
all source timestamps, SHARP time support, event completeness or follow-up.
No GPU, cloud or Git operations and no model fitting were performed.
'''
    (output/'research_log_broad_cycle24_proposal.md').write_text(note,encoding='utf-8')
    hashes={p.name:sha(p) for p in output.iterdir() if p.is_file()}
    write_json(output/'COMPLETE.json',{'status':STATUS,'output_sha256':hashes})
    small=['broad_cycle24_protocol_PROPOSED.json','broad_cycle24_fit_report.json',
           'final_role_support.csv','final_roles_by_year.csv','forward_fold_support.csv',
           'region_reservations.csv','research_log_broad_cycle24_proposal.md','COMPLETE.json']
    with zipfile.ZipFile(output/'broad_cycle24_fit_summary.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in small:z.write(output/name,name)
    print('\n===== BROADER CYCLE-24 FIT PROPOSAL RESULTS =====')
    print('All original targets retained:',n)
    print('Role | structurally retained | original positive | positive region components')
    for r in role_rows: print(' | '.join(str(r[k]) for k in ('role','retained','positive','positive_components')))
    print('\nFINAL REFIT POOL BY STORED YEAR: year | candidates | positives')
    for r in yr_rows:
        if r['role']==FIT:print(r['stored_year'],'|',r['retained'],'|',r['positive'])
    print('\nFORWARD DEVELOPMENT FOLDS: fold | role | candidates | positives | positive components')
    for r in fr_rows:print(' | '.join(str(r[k]) for k in ('fold_id','role','retained','positive','positive_components')))
    print('Structural blockers:',json.dumps(blockers))
    print('Support warnings:',json.dumps(warnings))
    print('Final calibration: REGION-HELD-OUT; NOT chronologically after all fitting observations.')
    print('STATUS:',STATUS)
    print('REPORT:',output/'broad_cycle24_fit_report.json')
    print('SUMMARY:',output/'broad_cycle24_fit_summary.zip')
    print('Original index/v1 roles unchanged. No training, cloud, labels changed or Git actions.')
    return result


def main(argv=None):
    home=Path.home()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=home/'aia17_metadata_stage1/temporal_manifest_v1/reports/20260916T143622218859Z')
    parser.add_argument('--reader-script',type=Path,default=home/'aia17_assign_cross_cycle_roles.py')
    parser.add_argument('--output-root',type=Path,default=home/'aia17_metadata_stage1/broad_cycle24_finalfit_v2/reports')
    a=parser.parse_args(argv)
    try:
        source=a.input_dir.resolve();root=a.output_root.resolve()
        require(source.is_dir(),'Existing temporal index directory not found. No redownload needed.')
        require(root!=source and source not in root.parents,'Output must be outside the source directory.')
        helper=load_helper(a.reader_script)
        parent=root
        while not parent.exists():parent=parent.parent
        require(shutil.disk_usage(parent).free>1024**3,'Less than 1 GiB free; do not delete research files blindly.')
        out=root/stamp();out.mkdir(parents=True,exist_ok=False)
        print('===== BROADER CYCLE-24 FINAL-FIT PROPOSAL =====')
        print('Separate v2 proposal. 80/10/10 approximate component reservations inside Cycle 24.')
        print('Chronological model-development folds; retrospective region-held-out final calibration.')
        print('No model fitting, test scoring, network, images or v1 replacement.')
        build(helper,source,out)
        return 0
    except (Exception,KeyboardInterrupt) as exc:
        print(f'\nSTOP: {type(exc).__name__}: {exc}',file=sys.stderr)
        print('Originals unchanged; no automatic seed/split replacement or clearance.',file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
