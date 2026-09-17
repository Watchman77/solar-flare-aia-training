import contextlib
import csv
from datetime import datetime, timedelta, timezone
import gzip
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE=Path(__file__).resolve().parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod
m=load('role_module',BASE/'aia17_assign_cross_cycle_roles.py')
b=load('original_temporal_builder',BASE/'aia17_build_temporal_manifest.py')


def make_samples(dates=None):
    if dates is None:
        dates=['2012-03-10T04:48:00','2014-03-10T04:48:00','2014-09-10T04:48:00',
               '2015-03-10T04:48:00','2018-03-10T04:48:00','2020-03-10T04:48:00',
               '2024-03-10T04:48:00','2026-03-10T04:48:00']
    vals={}
    for ix,date in enumerate(dates):
        for lab in (0,1):
            harp=100+ix*2+lab;noaa=11000+ix*2+lab
            for lag in (288,192,96,0):
                d=datetime.fromisoformat(date)-timedelta(minutes=lag)
                offset=35 if 2012<=d.year<2016 else 37
                utc=(d-timedelta(seconds=offset)).replace(tzinfo=timezone.utc)
                raw=d.strftime('%Y.%m.%d_%H:%M:%S_TAI')
                sid=d.strftime('%Y%m%d_%H%M')+f'_HARP{harp}_NOAA{noaa}'
                s=b.Sample(sid,harp,noaa,b.tai_tick(raw),raw,d.isoformat(' '),
                    utc.isoformat().replace('+00:00','Z'),
                    (utc+timedelta(hours=48)).isoformat().replace('+00:00','Z'),
                    d.year,lab,0,0,0,'UTC_HYPOTHESIS_NOT_VERIFIED','NOT_VERIFIED')
                s.object_status=b.EXACT;s.uri=f'gs://suryabench-sharp-pipeline-bamidele/samples_npz/{d.year}/{sid}.npz'
                s.generation='123';s.object_bytes=100
                vals[sid]=s
    return vals


def fixture(folder,dates=None):
    folder.mkdir()
    vals=make_samples(dates)
    report=b.write_results(vals,folder,{'fixture':'synthetic only'})
    hashes={f.name:m.sha(f) for f in folder.iterdir()}
    (folder/'COMPLETE.json').write_text(json.dumps({'status':report['status'],'output_sha256':hashes}))
    return report


def one_record():
    ss=make_samples(['2024-03-10T04:48:00'])
    index=b.build_index(ss)
    rs=[b.candidate_record(s,index) for s in ss.values()]
    return next(r for r in rs if r['history_status']==b.AVAILABLE),rs


class RoleTests(unittest.TestCase):
    def test_exact_calendar_boundaries(self):
        self.assertEqual(m.get_role(m.dt('2014-06-30T23:59:59Z')),'model_validation')
        self.assertEqual(m.get_role(m.dt('2014-07-01T00:00:00Z')),'calibration_fit')
        self.assertEqual(m.get_role(m.dt('2026-01-01T00:00:00Z')),'supplementary_2026')
    def test_cycle25_never_development(self):
        for year in range(2021,2026):
            role=m.ROLE_MAP[m.get_role(m.dt(f'{year}-07-01T00:00:00Z'))]
            self.assertEqual(role.name,'independent_cycle25_test')
            self.assertFalse(role.development)
    def test_disjoint_chronological_development(self):
        dev=[r for r in m.ROLES if r.development]
        self.assertEqual(len(dev),4)
        self.assertTrue(all(r.upper<=m.dt('2016-01-01T00:00:00Z') for r in dev))
        self.assertTrue(all(a.upper<=bb.lower for a,bb in zip(dev,dev[1:])))
    def test_explicit_utc_required(self):
        with self.assertRaises(ValueError):m.dt('2024-01-01T00:00:00')
    def test_connected_components_merge_shared_identifier(self):
        g=m.UnionFind();g.union(('H',1),('N',101));g.union(('H',2),('N',101))
        g.union(('H',2),('N',102))
        self.assertEqual(g.find(('H',1)),g.find(('N',102)))
    def test_cross_role_component_excluded(self):
        rec,rs=one_record();targets={r['target_sample_id']:m.parse_target(r) for r in rs}
        t=targets[rec['target_sample_id']]
        reasons=m.reasons_for(rec,t,targets,{'roles':{'train','independent_cycle25_test'}})
        self.assertIn('REGION_COMPONENT_SPANS_ROLES',reasons)
    def test_exact_horizon_boundary_is_purged(self):
        rec,rs=one_record();ts={r['target_sample_id']:m.parse_target(r) for r in rs};t=ts[rec['target_sample_id']]
        t.end=m.ROLE_MAP[t.role].upper
        self.assertIn('FORECAST_ENDPOINT_REACHES_NEXT_ROLE',m.reasons_for(rec,t,ts,{'roles':{t.role}}))
    def test_history_cross_role_flag(self):
        rec,rs=one_record();ts={r['target_sample_id']:m.parse_target(r) for r in rs};t=ts[rec['target_sample_id']]
        ts[rec['frames'][0]['history_sample_id']].role='train'
        self.assertIn('AIA_NOMINAL_HISTORY_CROSSES_ROLE',m.reasons_for(rec,t,ts,{'roles':{t.role}}))
    def test_existing_split_not_reassigned(self):
        rec,_=one_record();rec['split']='train'
        with self.assertRaises(ValueError):m.parse_target(rec)
    def test_wrong_region_rejected(self):
        rec,_=one_record();rec['HARPNUM']+=1
        with self.assertRaises(ValueError):m.parse_target(rec)
    def test_label_flag_excluded_not_relabelled(self):
        rec,rs=one_record();rec['label_boundary_review_required']=True
        rec['original_label_48h_final']=1; t=m.parse_target(rec)
        ts={r['target_sample_id']:m.parse_target(r) for r in rs};ts[t.sid]=t
        self.assertIn('TARGET_LABEL_BOUNDARY_REVIEW_PENDING',m.reasons_for(rec,t,ts,{'roles':{t.role}}))
        self.assertEqual(rec['original_label_48h_final'],1)
    def test_missing_history_preserves_target(self):
        _,rs=one_record();rec=next(r for r in rs if r['history_status']==b.INCOMPLETE)
        ts={r['target_sample_id']:m.parse_target(r) for r in rs};t=ts[rec['target_sample_id']]
        self.assertIn('NOMINAL_HISTORY_INCOMPLETE_OR_EXCLUDED',m.reasons_for(rec,t,ts,{'roles':{t.role}}))
    def test_checksum_mismatch_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'source';fixture(d)
            with (d/'temporal_sequence_candidates.jsonl.gz').open('ab') as f:f.write(b'x')
            with self.assertRaises(ValueError):m.load_source(d)
    def test_real_builder_output_full_offline_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'source';source_report=fixture(d)
            before={f.name:m.sha(f) for f in d.iterdir()}
            with contextlib.redirect_stdout(io.StringIO()):
                status=m.main(['--input-dir',str(d),'--output-root',str(Path(tmp)/'output')])
            self.assertEqual(status,0)
            out=next((Path(tmp)/'output/reports').iterdir())
            rep=json.loads((out/'cross_cycle_assignment_report.json').read_text())
            self.assertEqual(rep['target_rows_preserved'],64)
            self.assertEqual(rep['development_structural_blockers'],[])
            self.assertFalse(rep['training_authorised']);self.assertFalse(rep['split_dates_frozen'])
            self.assertEqual(rep['retained_cross_role_pinned_aia_object_overlap'],0)
            with gzip.open(out/'cross_cycle_role_assignments.csv.gz','rt') as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),64)
            self.assertEqual(sum(int(r['role_constraints_pass']) for r in rows),16)
            self.assertEqual(before,{f.name:m.sha(f) for f in d.iterdir()})
            self.assertTrue((out/'cross_cycle_summary_for_review.zip').is_file())
    def test_output_inside_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'source';fixture(d)
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                status=m.main(['--input-dir',str(d),'--output-root',str(d/'new')])
            self.assertEqual(status,1);self.assertFalse((d/'new').exists())
    def test_actual_component_scan_cross_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'source';report=fixture(d)
            # First phase two regions are linked to new-role entries through shared NOAA.
            recs=list(m.records(d/'temporal_sequence_candidates.jsonl.gz'))
            for r in recs:
                if r['stored_year']==2012:r['NOAA_AR_clean']=13000;r['target_sample_id']=r['target_sample_id'].split('_NOAA')[0]+'_NOAA13000'
                if r['stored_year']==2024:r['NOAA_AR_clean']=13000;r['target_sample_id']=r['target_sample_id'].split('_NOAA')[0]+'_NOAA13000'
            path=d/'synthetic_linked.jsonl.gz'
            with gzip.open(path,'wt') as f:
                for r in recs:f.write(json.dumps(r)+'\n')
            with contextlib.redirect_stdout(io.StringIO()):targets,groups,components=m.scan(path,report)
            selected=[c for c in components.values() if 13000 in c['noaa_ids']]
            self.assertEqual(len(selected),1)
            self.assertEqual(selected[0]['roles'],{'train','independent_cycle25_test'})
    def test_undefined_development_support_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'source';fixture(d,dates=['2024-03-10T04:48:00'])
            with contextlib.redirect_stdout(io.StringIO()):
                code=m.main(['--input-dir',str(d),'--output-root',str(Path(tmp)/'output')])
            self.assertEqual(code,0)
            out=next((Path(tmp)/'output/reports').iterdir())
            report=json.loads((out/'cross_cycle_assignment_report.json').read_text())
            self.assertEqual(len(report['development_structural_blockers']),4)
            self.assertFalse(report['training_authorised'])

if __name__=='__main__':unittest.main(verbosity=2)
