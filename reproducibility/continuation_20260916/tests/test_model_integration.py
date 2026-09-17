from __future__ import annotations
import contextlib
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('integration', ROOT/'aia17_model_integration.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
EVIDENCE=ROOT/'reviewed_canary'
BASEPLAN=json.loads((EVIDENCE/'canary_plan.json').read_text())
BASEREPORT=json.loads((EVIDENCE/'real_sequence_canary_report.json').read_text())


def csv_fixture(path, selected, mutate=None, omit=None, repeat=None):
    cols=['HARPNUM','NOAA_AR_clean','T_REC','QUALITY']+m.FEATURES
    rows=[]
    for i,s in enumerate(selected):
        for j,f in enumerate(s['frames']):
            r={'HARPNUM':str(s['HARPNUM']),'NOAA_AR_clean':str(s['NOAA_AR_clean']),
               'T_REC':f['raw_T_REC_TAI'],'QUALITY':'0'}
            r.update({n:str((i+1)*3+(j+1)*(k+1)*0.31) for k,n in enumerate(m.FEATURES)})
            rows.append(r)
    if mutate: mutate(rows)
    if omit is not None: rows.pop(omit)
    if repeat is not None: rows.append(rows[repeat].copy())
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
    return rows


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.plan=copy.deepcopy(BASEPLAN);self.report=copy.deepcopy(BASEREPORT)
        self.selected=self.plan['selected_targets']

    def test_supplied_plan_and_report_schema_accepted(self):
        self.assertEqual(len(m.checked_plan(self.plan,self.report)),4)

    def test_reject_test_target(self):
        self.selected[0]['canary_role']='independent_cycle25_test'
        with self.assertRaises(ValueError):m.checked_plan(self.plan,self.report)

    def test_reject_duplicated_region(self):
        self.selected[1]['region_component_id']=self.selected[0]['region_component_id']
        with self.assertRaises(ValueError):m.checked_plan(self.plan,self.report)

    def test_reject_report_order_mismatch(self):
        self.report['sequence_results'].reverse()
        with self.assertRaises(ValueError):m.checked_plan(self.plan,self.report)

    def test_reject_wrong_historical_region(self):
        self.selected[0]['frames'][0]['history_sample_id']='20121005_1300_HARP99_NOAA11588'
        with self.assertRaises(ValueError):m.checked_plan(self.plan,self.report)

    def test_reject_wrong_lag(self):
        self.selected[0]['frames'].reverse()
        with self.assertRaises(ValueError):m.checked_plan(self.plan,self.report)

    def test_tai_tag_mandatory(self):
        with self.assertRaises(ValueError):m.tai_clock('2012-10-05 13:00:00')

    def test_exact_twelve_row_join_and_feature_order(self):
        p=self.root/'sharp.csv';rows=csv_fixture(p,self.selected)
        x,info=m.select_sharp(p,self.selected)
        self.assertEqual(x.shape,(4,3,15));self.assertEqual(info['matched_record_count'],12)
        self.assertFalse(info['TOTUSJH_used']);self.assertFalse(info['is_24hour_aggregate_branch'])
        self.assertAlmostEqual(x[0,0,0],float(rows[0]['MEANGBZ']))

    def test_missing_exact_sharp_row_rejected(self):
        p=self.root/'sharp.csv';csv_fixture(p,self.selected,omit=0)
        with self.assertRaisesRegex(ValueError,'absent'):m.select_sharp(p,self.selected)

    def test_duplicate_sharp_key_rejected(self):
        p=self.root/'sharp.csv';csv_fixture(p,self.selected,repeat=0)
        with self.assertRaisesRegex(ValueError,'More than one'):m.select_sharp(p,self.selected)

    def test_wrong_noaa_rejected(self):
        p=self.root/'sharp.csv';csv_fixture(p,self.selected,mutate=lambda r:r[0].update(NOAA_AR_clean='9999'))
        with self.assertRaisesRegex(ValueError,'NOAA'):m.select_sharp(p,self.selected)

    def test_missing_field_not_fabricated(self):
        p=self.root/'sharp.csv';csv_fixture(p,self.selected)
        p.write_text(p.read_text().replace('MEANGBZ','absent_column'))
        with self.assertRaisesRegex(ValueError,'absent'):m.select_sharp(p,self.selected)

    def test_nonfinite_values_retained_for_train_only_imputation(self):
        p=self.root/'sharp.csv';csv_fixture(p,self.selected,mutate=lambda r:r[2].update(MEANGBZ='NaN'))
        x,info=m.select_sharp(p,self.selected)
        self.assertTrue(np.isnan(x[0,2,0]));y,params=m.train_only_preprocess(x,[0,1])
        self.assertTrue(np.isfinite(y).all());self.assertEqual(params['missing_values_by_sequence'][0],1)

    def test_validation_values_cannot_change_scaler(self):
        raw=np.arange(180,dtype=float).reshape(4,3,15)
        a,pa=m.train_only_preprocess(raw,[0,1])
        raw[2:]+=1e5;b,pb=m.train_only_preprocess(raw,[0,1])
        self.assertEqual(pa,pb);np.testing.assert_array_equal(a[:2],b[:2])

    def test_all_missing_train_feature_rejected(self):
        raw=np.ones((4,3,15));raw[:2,:,0]=np.nan
        with self.assertRaises(ValueError):m.train_only_preprocess(raw,[0,1])

    def test_hash_failure_not_repaired(self):
        p=self.root/'x';p.write_bytes(b'changed')
        with self.assertRaises(ValueError):m.verify_file(p,'a'*64,100)
        self.assertEqual(p.read_bytes(),b'changed')

    def test_forward_backward_and_validation_label_isolation(self):
        rng=np.random.default_rng(1)
        x=rng.random((4,3,6,32,32),dtype=np.float32);s=rng.standard_normal((4,3,15)).astype('f4')
        roles=['train','train','model_validation','model_validation']
        a=m.smoke_test(x,s,np.array([0,1,0,1]),roles,steps=2)
        b=m.smoke_test(x,s,np.array([0,1,1,0]),roles,steps=2)
        self.assertEqual(a['final_parameter_digest_for_regression_only'],b['final_parameter_digest_for_regression_only'])
        self.assertTrue(all(a['branch_parameters_changed'].values()))
        self.assertEqual(a['output_shape'],[4]);self.assertEqual(a['validation_weight_updates'],0)
        self.assertFalse(a['model_weights_saved']);self.assertFalse(a['forecasting_performance_metrics_calculated'])

    def test_validation_input_cannot_change_optimization(self):
        rng=np.random.default_rng(2)
        x=rng.random((4,3,6,32,32),dtype=np.float32);s=rng.standard_normal((4,3,15)).astype('f4')
        labels=np.array([0,1,0,1]);roles=['train','train','model_validation','model_validation']
        a=m.smoke_test(x,s,labels,roles,steps=1)
        x[2:]*=8;s[2:]*=4;b=m.smoke_test(x,s,labels,roles,steps=1)
        self.assertEqual(a['final_parameter_digest_for_regression_only'],b['final_parameter_digest_for_regression_only'])

    def test_no_test_roles_accepted_by_smoke_test(self):
        with self.assertRaises(ValueError):
            m.smoke_test(np.zeros((4,3,6,32,32),dtype='f4'),np.ones((4,3,15),dtype='f4'),np.array([0,1,0,1]),['train','train','test','test'])

    def test_complete_offline_synthetic_run_preserves_inputs(self):
        can=self.root/'canary';can.mkdir()
        (can/'canary_plan.json').write_text(json.dumps(self.plan))
        (can/'real_sequence_canary_report.json').write_text(json.dumps(self.report))
        # Pixel data and magnetic values are synthetic. Metadata comes from supplied report.
        image=np.empty((4,3,6,512,512),dtype='f4')
        base=np.arange(512,dtype='f4')/512
        image[:]=base[None,None,None,None,:]
        image[1]*=.7;image[2]*=.9;image[3]*=.6
        np.save(can/'engineering_batch.npy',image,allow_pickle=False);del image
        np.save(can/'manifest_targets.npy',np.array([0,1,0,1]),allow_pickle=False)
        hashes={p.name:m.digest(p) for p in can.iterdir()}
        (can/'COMPLETE.json').write_text(json.dumps({'output_sha256':hashes}))
        sharp=self.root/'sharp96.csv';csv_fixture(sharp,self.selected)
        lock=self.root/'lock.json';lock.write_text(json.dumps({'sources':[{'id':'sharp96','local_path':str(sharp),'sha256':m.digest(sharp),'size_bytes':sharp.stat().st_size}]}))
        before={str(p):m.digest(p) for p in [*can.iterdir(),sharp,lock]}
        # The driver must work offline without importing a previous download script.
        with patch('socket.socket.connect',side_effect=AssertionError('Unexpected network')):
            with contextlib.redirect_stdout(io.StringIO()):
                r=m.run(can,lock,self.root/'out')
        self.assertEqual(r['status'],m.STATUS)
        self.assertEqual(r['operations']['disposable_train_weight_updates'],10)
        self.assertEqual(r['operations']['network_requests'],0)
        self.assertFalse(r['scientific_clearance']['official_training_authorised'])
        self.assertEqual(before,{p:m.digest(Path(p)) for p in before})
        self.assertEqual(len(list((self.root/'out').rglob('model_integration_summary.zip'))),1)

if __name__=='__main__':unittest.main(verbosity=2)
