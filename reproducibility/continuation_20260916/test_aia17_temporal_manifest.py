import copy
import csv
from datetime import datetime, timedelta
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import aia17_build_temporal_manifest as m

class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.base=datetime(2024,1,2,4,48)
        self.samples={}
        for mins in (-288,-192,-96,0):
            t=self.base+timedelta(minutes=mins)
            raw=t.strftime('%Y.%m.%d_%H:%M:%S_TAI')
            sid=t.strftime('%Y%m%d_%H%M')+'_HARP1_NOAA10001'
            s=m.Sample(sid,1,10001,m.tai_tick(raw),raw,str(t),
                (t-timedelta(seconds=37)).isoformat(timespec='microseconds')+'Z',
                (t+timedelta(hours=48)-timedelta(seconds=37)).isoformat(timespec='microseconds')+'Z',
                2024,0,0,0,0,'UNVERIFIED','NOT_VERIFIED',m.EXACT,
                f'gs://suryabench-sharp-pipeline-bamidele/samples_npz/2024/{sid}.npz','123',100)
            self.samples[sid]=s
        self.target=list(self.samples.values())[-1]
    def tearDown(self): self.tmp.cleanup()
    def rec(self): return m.candidate_record(self.target,m.build_index(self.samples))
    def evidence(self,rec):
        ev={}
        for f in rec['frames']:
            slot=f['requested_slot_tai_us']
            ev[f['history_sample_id']]={
                **{k:f[k] for k in ('history_sample_id','object_uri','object_generation')},
                'HARPNUM':1,'NOAA_AR_clean':10001,'npz_sha256':'a'*64,
                'channels':[{'wavelength':c,'midpoint_tai_us':slot+10_000_000,
                             'contributing_end_tai_us':slot+12_000_000,'end_bound_verified':True,
                             'source_record':'synthetic_explicit_header',
                             'conversion_provenance':'fixture TAI coordinate; not actual archive'} for c in m.CHANNELS]}
        return ev
    def cached(self,rec):
        paths={}; ev=self.evidence(rec)
        for i,f in enumerate(rec['frames']):
            path=self.root/(str(i)+'.npz')
            np.savez_compressed(path,x=np.full((512,512,6),0.1+i/10,dtype=np.float32),y=1,
                sample_id=f['history_sample_id'],HARPNUM=1,NOAA_AR_clean=10001,wavelengths=np.array(m.CHANNELS))
            f['object_bytes']=path.stat().st_size
            ev[f['history_sample_id']]['npz_sha256']=m.digest(path)
            paths[(f['object_uri'],f['object_generation'])]=path
        return paths,ev
    def test_complete_nominal_history_and_order(self):
        rec=self.rec(); self.assertEqual(rec['history_status'],m.AVAILABLE)
        self.assertEqual([f['lag_minutes'] for f in rec['frames']],[288,192,96])
        self.assertFalse(rec['training_authorised']); self.assertEqual(rec['split'],'UNASSIGNED')
    def test_current_image_not_required(self):
        self.target.object_status='NOT_FOUND_IN_AUDITED_PREFIX'
        self.assertEqual(self.rec()['history_status'],m.AVAILABLE)
    def test_missing_history_not_forward_filled(self):
        self.samples.pop(list(self.samples)[1]); rec=self.rec()
        self.assertEqual(rec['history_status'],m.INCOMPLETE)
        self.assertIsNone(rec['frames'][1]['history_sample_id'])
    def test_other_harp_not_joined(self):
        list(self.samples.values())[1].harp=2
        self.assertEqual(self.rec()['history_status'],m.INCOMPLETE)
    def test_other_noaa_not_joined(self):
        list(self.samples.values())[1].noaa=10002
        self.assertEqual(self.rec()['history_status'],m.INCOMPLETE)
    def test_not_previous_three_rows(self):
        list(self.samples.values())[1].tick += 60_000_000
        self.assertEqual(self.rec()['history_status'],m.INCOMPLETE)
    def test_zero_or_unmatched_history_object_rejected(self):
        list(self.samples.values())[1].object_status='ZERO_BYTE_OBJECT'
        self.assertEqual(self.rec()['frames'][1]['selection_reason'],'HISTORY_OBJECT_NOT_EXACT_NONEMPTY')
    def test_duplicate_region_time_rejected(self):
        s=copy.deepcopy(list(self.samples.values())[1]);s.sid='duplicate'
        self.samples[s.sid]=s
        with self.assertRaises(ValueError):m.build_index(self.samples)
    def test_known_bad_pair_is_not_a_history_frame(self):
        s=list(self.samples.values())[1];self.samples.pop(s.sid);s.sid=m.KNOWN_BAD_FRAME;self.samples[s.sid]=s
        self.assertEqual(self.rec()['frames'][1]['selection_reason'],'KNOWN_SOURCE_SLOT_MISMATCH')
    def test_boundary_label_flag_preserved_without_relabelling(self):
        self.target.label=1;self.target.label_review=1;rec=self.rec()
        self.assertEqual(rec['original_label_48h_final'],1)
        self.assertTrue(rec['label_boundary_review_required'])
        with self.assertRaises(ValueError):m.load_local_sequence(rec,{}, {})
    def test_uniform_tai_interval_at_utc_leap_boundary(self):
        a=m.tai_tick('2016.12.31_23:59:59_TAI');b=m.tai_tick('2017.01.01_00:00:00_TAI')
        self.assertEqual(b-a,1_000_000)
        with self.assertRaises(ValueError):m.tai_tick('2017-01-01T00:00:00Z')
    def test_nominal_match_is_not_real_timing_clearance(self):
        rec=self.rec()
        with self.assertRaises(ValueError):m.validate_frame_evidence(rec,rec['frames'][0],{})
    def test_positive_small_exposure_offset_is_ok_for_historical_frame(self):
        rec=self.rec();f=rec['frames'][0]
        m.validate_frame_evidence(rec,f,self.evidence(rec)[f['history_sample_id']])
    def test_unverified_end_proxy_rejected(self):
        rec=self.rec();f=rec['frames'][0];e=self.evidence(rec)[f['history_sample_id']]
        e['channels'][0]['end_bound_verified']=False
        with self.assertRaises(ValueError):m.validate_frame_evidence(rec,f,e)
    def test_future_contributing_data_rejected(self):
        rec=self.rec();f=rec['frames'][0];e=self.evidence(rec)[f['history_sample_id']]
        e['channels'][0]['contributing_end_tai_us']=rec['issue_tai_us']+1
        with self.assertRaises(ValueError):m.validate_frame_evidence(rec,f,e)
    def test_exact_tolerance_boundary_and_outside(self):
        rec=self.rec();f=rec['frames'][0];e=self.evidence(rec)[f['history_sample_id']]
        e['channels'][0]['midpoint_tai_us']=f['requested_slot_tai_us']+180_000_000
        e['channels'][0]['contributing_end_tai_us']=f['requested_slot_tai_us']+182_000_000
        m.validate_frame_evidence(rec,f,e)
        e['channels'][0]['midpoint_tai_us']+=1
        with self.assertRaises(ValueError):m.validate_frame_evidence(rec,f,e)
    def test_generation_mismatch_rejected(self):
        rec=self.rec();f=rec['frames'][0];e=self.evidence(rec)[f['history_sample_id']];e['object_generation']='124'
        with self.assertRaises(ValueError):m.validate_frame_evidence(rec,f,e)
    def test_loader_returns_temporal_tensor_and_manifest_not_embedded_label(self):
        rec=self.rec();paths,ev=self.cached(rec)
        out=m.load_local_sequence(rec,paths,ev)
        self.assertEqual(out['x_tchw'].shape,(3,6,512,512))
        self.assertEqual(out['original_manifest_target'],0)
        self.assertFalse(out['training_authorised'])
        self.assertTrue(np.allclose(out['x_tchw'][1],0.2))
    def test_loader_never_fills_missing_local_objects(self):
        rec=self.rec();ev=self.evidence(rec)
        with self.assertRaises(ValueError):m.load_local_sequence(rec,{},ev)
    def test_loader_wrong_hash_rejected(self):
        rec=self.rec();paths,ev=self.cached(rec)
        ev[rec['frames'][0]['history_sample_id']]['npz_sha256']='f'*64
        with self.assertRaises(ValueError):m.load_local_sequence(rec,paths,ev)
    def test_loader_repeated_frame_rejected(self):
        rec=self.rec();rec['frames'][1]['history_sample_id']=rec['frames'][0]['history_sample_id']
        with self.assertRaises(ValueError):m.load_local_sequence(rec,{}, {})
    def test_output_keeps_every_target_and_original_labels(self):
        self.target.label=1;self.target.label_review=1
        out=self.root/'out';out.mkdir()
        report=m.write_results(self.samples,out,{})
        self.assertEqual(report['target_rows'],4)
        with gzip.open(out/'temporal_sequence_candidates.jsonl.gz','rt') as f: records=[json.loads(x) for x in f]
        self.assertEqual(len(records),4)
        self.assertEqual(sum(r['original_label_48h_final'] for r in records),1)
        self.assertEqual(report['history_status_counts'][m.AVAILABLE],1)
        self.assertFalse(report['splits_frozen'])
    def write_fixture_inputs(self):
        clocks=[];reg=[]
        for s in self.samples.values():
            clocks.append(dict(sample_id=s.sid,HARPNUM=s.harp,NOAA_AR_clean=s.noaa,T_REC_raw_TAI=s.raw_tai,
                T_REC_dt_original=s.original_clock,T_REC_utc_derived=s.utc,forecast_end_utc_48_SI_hours=s.end_utc,
                stored_year=s.year,original_label_48h_final=s.label,in_baseline_manifest=s.baseline,
                in_extension=s.extension,utc_hypothesis_differs_from_original_label=s.label_review,
                event_scale_status=s.event_scale_status,followup_status=s.followup_status,training_authorised=False))
            reg.append(dict(sample_id=s.sid,HARPNUM=s.harp,NOAA_AR_clean=s.noaa,stored_issue_time=s.original_clock,
                stored_year=s.year,original_label=s.label,in_baseline=s.baseline,object_status=s.object_status,
                expected_uri=s.uri,generation=s.generation,object_bytes=s.object_bytes))
        ip=self.root/'inventory';tp=self.root/'time';ip.mkdir();tp.mkdir()
        cp=tp/'sample_time_and_window_diagnostics.csv.gz';rp=ip/'target_object_register.csv'
        for path,data in [(cp,clocks),(rp,reg)]:
            op=gzip.open if path.suffix=='.gz' else open
            with op(path,'wt',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
        return rp,cp
    def test_end_to_end_cli_on_small_fixture_and_input_preservation(self):
        rp,cp=self.write_fixture_inputs();before=(rp.read_bytes(),cp.read_bytes());load=m.load_inputs
        with patch.object(m,'INPUT_HASHES',{'register':m.digest(rp),'clock_table':m.digest(cp)}), \
             patch.object(m,'load_inputs',lambda a,b:load(a,b,4)),patch.object(m,'MIN_DISK_FREE',0):
            code=m.main(['--inventory-dir',str(rp.parent),'--time-dir',str(cp.parent),
                         '--output-root',str(self.root/'generated')])
        self.assertEqual(code,0);self.assertEqual(before,(rp.read_bytes(),cp.read_bytes()))
        generated=list((self.root/'generated/reports').iterdir());self.assertEqual(len(generated),1)
        self.assertTrue((generated[0]/'COMPLETE.json').exists())
        self.assertTrue((generated[0]/'summary_for_review.zip').exists())
    def test_changed_input_fails_before_outputs(self):
        rp,cp=self.write_fixture_inputs()
        with patch.object(m,'INPUT_HASHES',{'register':'0'*64,'clock_table':m.digest(cp)}):
            code=m.main(['--inventory-dir',str(rp.parent),'--time-dir',str(cp.parent),
                         '--output-root',str(self.root/'generated')])
        self.assertEqual(code,1);self.assertFalse((self.root/'generated').exists())

if __name__=='__main__':unittest.main()
