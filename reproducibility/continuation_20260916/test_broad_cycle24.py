import contextlib
import csv
from datetime import datetime, timedelta, timezone
import gzip
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parent

def imp(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

m=imp('broad_protocol',BASE/'aia17_prepare_broad_cycle24_fit.py')
b=imp('temporal_builder_fixture',BASE/'aia17_build_temporal_manifest.py')
h=m.load_helper(BASE/'aia17_assign_cross_cycle_roles.py')


def fixture(folder):
 folder.mkdir(); samples={}
 # Many whole-region groups per year; a genuinely separate group for each case.
 for year in (2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2025,2026):
  for label in (0,1):
   for j in range(12):
    harp=(year-2000)*100+label*12+j+1;noaa=10000+harp
    for lag in (288,192,96,0):
     d=datetime(year,3,10,4,48)-timedelta(minutes=lag)
     offset=34 if year<2012 else 35 if year<2016 else 36 if year==2016 else 37
     utc=(d-timedelta(seconds=offset)).replace(tzinfo=timezone.utc)
     raw=d.strftime('%Y.%m.%d_%H:%M:%S_TAI');sid=d.strftime('%Y%m%d_%H%M')+f'_HARP{harp}_NOAA{noaa}'
     x=b.Sample(sid,harp,noaa,b.tai_tick(raw),raw,d.isoformat(' '),
      utc.isoformat().replace('+00:00','Z'),(utc+timedelta(hours=48)).isoformat().replace('+00:00','Z'),
      year,label,0,0,0,'UTC_HYPOTHESIS_NOT_VERIFIED','NOT_VERIFIED')
     x.object_status=b.EXACT;x.uri=f'gs://suryabench-sharp-pipeline-bamidele/samples_npz/{year}/{sid}.npz';x.generation='123';x.object_bytes=100
     samples[sid]=x
 report=b.write_results(samples,folder,{'fixture':'synthetic broad-cycle source'})
 hashes={p.name:h.sha(p) for p in folder.iterdir() if p.is_file()}
 (folder/'COMPLETE.json').write_text(json.dumps({'status':report['status'],'output_sha256':hashes}))
 return report


def inspect_fixture(folder,report):
 path=folder/'temporal_sequence_candidates.jsonl.gz'
 with contextlib.redirect_stdout(io.StringIO()):targets,groups,periods,_=m.scan_index(h,path,report)
 records=list(h.records(path)); rs={r['target_sample_id']:m.base_reasons(r,targets[r['target_sample_id']],targets,groups,periods) for r in records}
 assignment,support=m.reserve_groups(targets,groups,rs)
 return records,targets,groups,periods,rs,assignment,support


class BroadTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
  cls.src=cls.root/'source';cls.source_report=fixture(cls.src)
  cls.before={p.name:m.sha(p) for p in cls.src.iterdir()}
  cls.state=inspect_fixture(cls.src,cls.source_report)
  cls.out=cls.root/'out';cls.out.mkdir()
  with contextlib.redirect_stdout(io.StringIO()),patch.object(socket,'create_connection',side_effect=AssertionError('Network not allowed')):
   cls.result=m.build(h,cls.src,cls.out)
  with gzip.open(cls.out/'broad_cycle24_final_role_candidates.csv.gz','rt') as f:cls.rows=list(csv.DictReader(f))
  with gzip.open(cls.out/'forward_development_fold_candidates.csv.gz','rt') as f:cls.folds=list(csv.DictReader(f))
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_all_original_rows_and_labels_preserved(self):
  originals={r['target_sample_id']:r['original_label_48h_final'] for r in self.state[0]}
  self.assertEqual(len(originals),len(self.rows))
  self.assertEqual(originals,{r['target_sample_id']:int(r['original_label_48h_final']) for r in self.rows})
 def test_input_files_unchanged(self):
  self.assertEqual(self.before,{p.name:m.sha(p) for p in self.src.iterdir()})
 def test_later_years_enter_final_fit(self):
  for year in (2014,2015,2016,2017,2018,2019):
   rows=[r for r in self.rows if r['proposed_final_role']==m.FIT and int(r['stored_year'])==year and r['structural_candidate']=='1']
   self.assertTrue(rows,year)
 def test_outer_boundary_is_explicit(self):
  self.assertEqual(m.period(m.dt('2019-11-30T23:59:59Z')),m.DEV)
  self.assertEqual(m.period(m.dt('2019-12-01T00:00:00Z')),'cycle25_early_diagnostic')
  self.assertEqual(m.period(m.dt('2021-01-01T00:00:00Z')),'independent_cycle25_test')
  self.assertEqual(m.period(m.dt('2026-01-01T00:00:00Z')),'supplementary_2026')
 def test_cycle25_never_fitting_or_holdout_calibration(self):
  for row in self.rows:
   if int(row['stored_year'])>=2020:self.assertNotIn(row['proposed_final_role'],(m.FIT,m.CAL,m.THR))
 def test_region_components_are_never_split_across_final_roles(self):
  roles={}
  for r in self.rows:
   if r['structural_candidate']=='1':roles.setdefault(r['region_component_id'],set()).add(r['proposed_final_role'])
  self.assertTrue(all(len(v)==1 for v in roles.values()))
 def test_final_holdouts_excluded_from_every_development_fold(self):
  role={r['target_sample_id']:r['proposed_final_role'] for r in self.rows}
  self.assertTrue(self.folds)
  self.assertTrue(all(role[r['target_sample_id']]==m.FIT for r in self.folds))
 def test_forward_folds_are_temporally_ordered(self):
  originals={r['target_sample_id']:r for r in self.state[0]}
  for r in self.folds:
   if r['structural_candidate']!='1':continue
   rec=originals[r['target_sample_id']];year=int(r['fold_id'][-4:]);lo=m.dt(f'{year}-01-01T00:00:00Z')
   if r['fold_role']=='train':
    self.assertLess(m.dt(rec['issue_utc']),lo)
    self.assertLess(m.dt(rec['forecast_end_utc_48_SI_hours']),lo)
   else:
    self.assertGreaterEqual(m.dt(rec['issue_utc']),lo)
    self.assertLess(m.dt(rec['forecast_end_utc_48_SI_hours']),m.dt(f'{year+1}-01-01T00:00:00Z'))
 def test_each_forward_fold_is_region_disjoint(self):
  from collections import defaultdict
  seen=defaultdict(set)
  for r in self.folds:
   if r['structural_candidate']=='1':seen[(r['fold_id'],r['region_component_id'])].add(r['fold_role'])
  self.assertTrue(all(len(v)==1 for v in seen.values()))
 def test_deterministic_reservations_ignore_input_order(self):
  _,ts,gs,_,rs,assignment,_=self.state
  actual,_=m.reserve_groups(dict(reversed(list(ts.items()))),gs,rs)
  self.assertEqual(actual,assignment)
 def test_test_label_changes_cannot_change_reservations(self):
  import copy
  _,ts,gs,_,rs,assignment,_=self.state
  alt=copy.deepcopy(ts)
  for t in alt.values():
   if m.period(t.issue)!=m.DEV:t.label=1-t.label
  actual,_=m.reserve_groups(alt,gs,rs)
  self.assertEqual(actual,assignment)
 def test_80_10_10_counts_are_components_not_rows(self):
  for r in self.result['reservation_support_by_component_stratum']:
   self.assertEqual(r['calibration_components'],r['components']//10)
   self.assertEqual(r['threshold_components'],r['components']//10)
   self.assertEqual(r['refit_components'],r['components']-2*(r['components']//10))
 def test_retrospective_calibration_disclosed_no_fit_claim(self):
  protocol=json.loads((self.out/'broad_cycle24_protocol_PROPOSED.json').read_text())
  self.assertIn('NOT_CHRONOLOGICALLY_FUTURE',protocol['final_calibration_design'])
  for flag in ('model_fitted','training_authorised'):self.assertFalse(self.result[flag])
  self.assertFalse(self.result['v1_assignment_rewritten']);self.assertFalse(self.result['final_dates_frozen'])
 def test_output_checksums_and_small_bundle(self):
  done=json.loads((self.out/'COMPLETE.json').read_text())
  for file,value in done['output_sha256'].items():self.assertEqual(m.sha(self.out/file),value)
  import zipfile
  with zipfile.ZipFile(self.out/'broad_cycle24_fit_summary.zip') as z:
   self.assertNotIn('broad_cycle24_final_role_candidates.csv.gz',z.namelist())
   self.assertIn('broad_cycle24_protocol_PROPOSED.json',z.namelist())
 def test_bad_helper_checksum_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'helper.py';p.write_text('raise Exception("must not execute")')
   with self.assertRaisesRegex(ValueError,'differs'):m.load_helper(p)
 def test_forecast_boundary_equality_is_excluded(self):
  import copy
  rec=next(r for r in self.state[0] if r['history_status']==b.AVAILABLE)
  _,ts,gs,periods,_,_,_=self.state;t=copy.deepcopy(ts[rec['target_sample_id']]);t.end=m.period_bounds(m.DEV)[1]
  self.assertIn('FORECAST_ENDPOINT_REACHES_OUTER_BOUNDARY',m.base_reasons(rec,t,ts,gs,periods))
 def test_region_outer_crossing_is_excluded(self):
  rec=next(r for r in self.state[0] if r['history_status']==b.AVAILABLE)
  _,ts,gs,periods,_,_,_=self.state;t=ts[rec['target_sample_id']]
  alt=dict(periods);alt[gs[t.sid]]={m.DEV,'independent_cycle25_test'}
  self.assertIn('REGION_COMPONENT_SPANS_OUTER_PERIODS',m.base_reasons(rec,t,ts,gs,alt))
 def test_known_label_review_retained_as_exclusion_not_repaired(self):
  import copy
  rec=next(r for r in self.state[0] if r['history_status']==b.AVAILABLE)
  _,ts,gs,periods,_,_,_=self.state;t=copy.deepcopy(ts[rec['target_sample_id']]);t.label_review=True
  self.assertIn('TARGET_LABEL_BOUNDARY_REVIEW_PENDING',m.base_reasons(rec,t,ts,gs,periods))
 def test_original_temporal_checksum_mismatch_fails(self):
  import shutil
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'source';shutil.copytree(self.src,p)
   with (p/'temporal_sequence_candidates.jsonl.gz').open('ab') as f:f.write(b'changed')
   with self.assertRaisesRegex(ValueError,'Checksum|checksum'):h.load_source(p)
 def test_actual_cli_entrypoint_preserves_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'new'
   with contextlib.redirect_stdout(io.StringIO()):
    ret=m.main(['--input-dir',str(self.src),'--reader-script',str(BASE/'aia17_assign_cross_cycle_roles.py'),'--output-root',str(root)])
   self.assertEqual(ret,0);self.assertTrue(list(root.glob('*/COMPLETE.json')))
   self.assertEqual(self.before,{p.name:m.sha(p) for p in self.src.iterdir()})
 def test_output_cannot_be_inside_source(self):
  with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
   ret=m.main(['--input-dir',str(self.src),'--reader-script',str(BASE/'aia17_assign_cross_cycle_roles.py'),'--output-root',str(self.src/'bad')])
  self.assertEqual(ret,1);self.assertFalse((self.src/'bad').exists())
 def test_full_fixture_has_no_structural_development_blocker(self):
  self.assertEqual(self.result['structural_blockers'],[])
  self.assertEqual(self.result['cross_final_role_pinned_objects'],0)
  self.assertEqual(self.result['within_fold_train_validation_pinned_objects'],0)

if __name__=='__main__':unittest.main(verbosity=2)
