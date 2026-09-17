import contextlib
import csv
from datetime import datetime, timedelta, timezone
import gzip
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

SCRIPT = Path(__file__).resolve().parent / 'aia18_build_sharp_training_arrays.py'
spec=importlib.util.spec_from_file_location('sharp_arrays',SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def dump(path,data):
    path.write_text(json.dumps(data),encoding='utf-8')


def gzjson(path,rows):
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row)+'\n')


def marker(folder,status,names):
    dump(folder/'COMPLETE.json',{'status':status,'output_sha256':{n:m.sha(folder/n) for n in names}})


def fixture(root):
    idx=root/'index';pro=root/'proposal';idx.mkdir();pro.mkdir()
    records=[];role_rows=[];selected=[];raw_rows=[]
    choices=[(2011,m.FIT,0),(2013,m.FIT,1),(2014,m.CAL,0),(2015,m.CAL,1),(2016,m.THR,0),(2017,m.THR,1),(2024,'independent_cycle25_test',1)]
    for h,(year,role,label) in enumerate(choices,100):
        noaa=h+11000;t=datetime(year,6,15,12,0,0);frames=[]
        group=f'component_{h}'
        def utc(z):return (z-timedelta(seconds=34 if z.year<2012 else 35 if z.year<2016 else 36 if z.year==2016 else 37)).isoformat()+'.000000Z'
        def sid(z):return z.strftime('%Y%m%d_%H%M')+f'_HARP{h}_NOAA{noaa}'
        for j,lag in enumerate(m.LAGS):
            z=t-timedelta(minutes=lag);raw=z.strftime('%Y.%m.%d_%H:%M:%S_TAI');ft=m.tick(raw)
            f={'lag_minutes':lag,'history_sample_id':sid(z),'raw_T_REC_TAI':raw,'requested_slot_tai_us':ft,
               'record_utc':utc(z),'object_uri':'gs://suryabench-sharp-pipeline-bamidele/samples_npz/'+str(year)+'/'+sid(z)+'.npz',
               'object_generation':'12345','object_status':'EXACT_NONEMPTY_OBJECT','nominal_candidate':True}
            frames.append(f)
            raw_rows.append({'HARPNUM':h,'T_REC':raw,'NOAA_AR_clean':noaa,'NOAA_ARS':str(noaa),'QUALITY':'0',**{name:float(h+j+k) for k,name in enumerate(m.FEATURES)}})
            records.append({'target_sample_id':sid(z)})
            role_rows.append({'target_sample_id':sid(z),'issue_utc':utc(z),'stored_year':year,'HARPNUM':h,'NOAA_AR_clean':noaa,'original_label_48h_final':label,
                             'region_component_id':group,'proposed_final_role':role,'structural_candidate':0,'exclusion_reasons':'HISTORY_INCOMPLETE','training_authorised':False})
        rec={'target_sample_id':sid(t),'issue_raw_TAI':t.strftime('%Y.%m.%d_%H:%M:%S_TAI'),'issue_tai_us':m.tick(t.strftime('%Y.%m.%d_%H:%M:%S_TAI')),
             'issue_utc':utc(t),'stored_year':year,'HARPNUM':h,'NOAA_AR_clean':noaa,'original_label_48h_final':label,'frames':frames,
             'training_authorised':False,'label_boundary_review_required':False}
        records.append(rec)
        row={'target_sample_id':sid(t),'issue_utc':utc(t),'stored_year':year,'HARPNUM':h,'NOAA_AR_clean':noaa,'original_label_48h_final':label,
             'region_component_id':group,'proposed_final_role':role,'structural_candidate':1,'exclusion_reasons':'','training_authorised':False}
        role_rows.append(row)
        if role in m.ROLES:selected.append(row)
    gzjson(idx/'temporal_sequence_candidates.jsonl.gz',records)
    dump(idx/'temporal_manifest_report.json',{'status':m.INDEX_STATUS})
    marker(idx,m.INDEX_STATUS,['temporal_sequence_candidates.jsonl.gz','temporal_manifest_report.json'])
    m.write_csv(pro/'broad_cycle24_final_role_candidates.csv.gz',role_rows,list(role_rows[0]))
    fold_rows=[]
    for row in selected[:2]:
        fold_rows.append({'fold_id':'cycle24_forward_validate_2013','target_sample_id':row['target_sample_id'],'region_component_id':row['region_component_id'],
                         'fold_role':'train' if row['stored_year']==2011 else 'validation','structural_candidate':1,'exclusion_reasons':''})
    m.write_csv(pro/'forward_development_fold_candidates.csv.gz',fold_rows,list(fold_rows[0]))
    report={'target_rows_preserved':len(records),'structural_blockers':[],'model_fitted':False,'source_directory':str(idx),
            'source_files_sha256':{n:m.sha(idx/n) for n in ('temporal_sequence_candidates.jsonl.gz','temporal_manifest_report.json','COMPLETE.json')},
            'role_support':[{'role':r,'retained':2,'positive':1} for r in m.ROLES],
            'forward_fold_support':[{'fold_id':'cycle24_forward_validate_2013','role':'train','retained':1,'positive':0},
                                    {'fold_id':'cycle24_forward_validate_2013','role':'validation','retained':1,'positive':1}]}
    dump(pro/'broad_cycle24_fit_report.json',report)
    dump(pro/'broad_cycle24_protocol_PROPOSED.json',{'proposal_not_frozen':True})
    pnames=['broad_cycle24_fit_report.json','broad_cycle24_protocol_PROPOSED.json','broad_cycle24_final_role_candidates.csv.gz','forward_development_fold_candidates.csv.gz']
    marker(pro,m.PROPOSAL_STATUS,pnames)
    raw=root/'sharp.csv';m.write_csv(raw,raw_rows,list(raw_rows[0]))
    lock=root/'lock.json';dump(lock,{'sources':[{'id':'sharp96','local_path':str(raw),'sha256':m.sha(raw),'size_bytes':raw.stat().st_size}]})
    return {'proposal':pro,'index':idx,'raw':raw,'lock':lock,'roles':role_rows,'selected':selected,'raw_rows':raw_rows,'records':records,'report':report,'pnames':pnames}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.fx=fixture(self.root)
    def tearDown(self):self.tmp.cleanup()
    def go(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result=m.build(self.fx['proposal'],self.fx['lock'],self.root/'out')
        out=next((self.root/'out').iterdir());return result,out
    def requests(self):
        selected=m.load_roles(self.fx['proposal']/'broad_cycle24_final_role_candidates.csv.gz',self.fx['report'])
        return m.requested_slots(self.fx['index']/'temporal_sequence_candidates.jsonl.gz',selected,len(self.fx['records']))[0]
    def rewrite_raw(self,rows):m.write_csv(self.fx['raw'],rows,list(rows[0]))
    def test_full_build_shapes_roles_and_no_test_arrays(self):
        r,out=self.go();self.assertEqual(r['array_shape'],[6,3,15]);self.assertFalse(r['test_arrays_constructed'])
        rows=list(m.csv_rows(out/'cycle24_array_rows.csv.gz',{'target_sample_id'}))
        self.assertEqual({x['proposed_final_role'] for x in rows},set(m.ROLES))
        self.assertFalse(any(x['stored_year']=='2024' for x in rows))
        self.assertEqual(np.load(out/'original_manifest_targets.npy',allow_pickle=False).tolist(),[0,1,0,1,0,1])
    def test_source_unchanged(self):
        paths=[p for p in self.root.rglob('*') if p.is_file()];before={p:m.sha(p) for p in paths};self.go()
        self.assertEqual(before,{p:m.sha(p) for p in paths})
    def test_all_output_hashes(self):
        _,out=self.go();marker=m.load_json(out/'COMPLETE.json')
        for name,h in marker['output_sha256'].items():self.assertEqual(m.sha(out/name),h)
    def test_raw_values_not_scaled(self):
        _,out=self.go();x=np.load(out/'sharp_raw_three_slot.npy');self.assertEqual(x[0,0,0],100.)
        self.assertEqual(x[0,2,14],116.)
    def test_missing_record_stays_missing(self):
        req=self.requests();self.rewrite_raw(self.fx['raw_rows'][1:]);_,_,raw,matches,_,_=m.scan_sharp(self.fx['raw'],req)
        self.assertEqual((matches==0).sum(),1);self.assertTrue(np.isnan(raw[matches==0]).all())
    def test_duplicate_invalidates_entire_slot(self):
        req=self.requests();self.rewrite_raw(self.fx['raw_rows']+[self.fx['raw_rows'][0]])
        _,_,raw,mc,_,_=m.scan_sharp(self.fx['raw'],req);self.assertEqual((mc==2).sum(),1);self.assertTrue(np.isnan(raw[mc==2]).all())
    def test_nonfinite_values_not_zero_filled(self):
        req=self.requests();rows=self.fx['raw_rows'];rows[0][m.FEATURES[0]]='inf';rows[0][m.FEATURES[1]]='bad';self.rewrite_raw(rows)
        _,_,x,_,_,info=m.scan_sharp(self.fx['raw'],req);self.assertTrue(np.isnan(x[0,:2]).all());self.assertEqual(len(info['numeric_input_flags']),2)
    def test_quality_preserved_not_filtered(self):
        req=self.requests();rows=self.fx['raw_rows'];rows[0]['QUALITY']='65536';self.rewrite_raw(rows)
        _,_,x,_,info,_=m.scan_sharp(self.fx['raw'],req);self.assertEqual(info[0]['raw_QUALITY'],['65536']);self.assertTrue(np.isfinite(x[0]).all())
    def test_explicit_noaa_conflict_flagged(self):
        req=self.requests();rows=self.fx['raw_rows'];rows[0]['NOAA_AR_clean']=99999;self.rewrite_raw(rows)
        _,_,_,_,info,_=m.scan_sharp(self.fx['raw'],req);self.assertTrue(info[0]['noaa_conflict'])
    def test_missing_feature_not_invented(self):
        req=self.requests();rows=[dict(x) for x in self.fx['raw_rows']]
        for x in rows:del x['USFLUX']
        self.rewrite_raw(rows)
        with self.assertRaisesRegex(ValueError,'columns missing'):m.scan_sharp(self.fx['raw'],req)
    def test_no_tai_tag_rejected(self):
        with self.assertRaisesRegex(ValueError,'Explicit TAI'):m.tick('2012-01-01 00:00:00')
    def test_tai_time_difference_is_exact(self):
        self.assertEqual(m.tick('2015.07.01_00:00:00_TAI')-m.tick('2015.06.30_23:00:00_TAI'),3600*10**6)
    def test_source_checksum_failure(self):
        with self.fx['raw'].open('a') as f:f.write('\n')
        with self.assertRaisesRegex(ValueError,'Checksum'):self.go()
    def test_role_report_count_mismatch(self):
        report=dict(self.fx['report'],target_rows_preserved=1)
        with self.assertRaisesRegex(ValueError,'count disagrees'):m.load_roles(self.fx['proposal']/'broad_cycle24_final_role_candidates.csv.gz',report)
    def test_holdout_cannot_enter_forward_fold(self):
        pro=self.fx['proposal'];rows=list(m.csv_rows(pro/'forward_development_fold_candidates.csv.gz',{'target_sample_id'}))
        rows[0]['target_sample_id']=self.fx['selected'][2]['target_sample_id'];rows[0]['region_component_id']=self.fx['selected'][2]['region_component_id']
        m.write_csv(pro/'forward_development_fold_candidates.csv.gz',rows,list(rows[0]));marker(pro,m.PROPOSAL_STATUS,self.fx['pnames'])
        with self.assertRaisesRegex(ValueError,'Holdout or test'):self.go()
    def test_later_years_preserved_in_role_array(self):
        _,out=self.go();rows=list(m.csv_rows(out/'cycle24_array_rows.csv.gz',{'stored_year'}))
        self.assertTrue({'2015','2016','2017'} <= {r['stored_year'] for r in rows})
    def test_wrong_lag_rejected(self):
        selected=m.load_roles(self.fx['proposal']/'broad_cycle24_final_role_candidates.csv.gz',self.fx['report'])
        for r in self.fx['records']:
            if r.get('frames'):r['frames'][0]['lag_minutes']=287;break
        path=self.fx['index']/'temporal_sequence_candidates.jsonl.gz';gzjson(path,self.fx['records'])
        with self.assertRaisesRegex(ValueError,'historical slots'):m.requested_slots(path,selected,len(self.fx['records']))
    def test_no_training_clearance_granted(self):
        r,_=self.go()
        for k in ('training_authorised','model_trained','imputation_or_scaling_fitted','calibration_or_threshold_fitted','split_frozen'):
            self.assertFalse(r[k])

if __name__=='__main__':unittest.main(verbosity=2)
