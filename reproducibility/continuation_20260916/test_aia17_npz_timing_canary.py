import argparse
import base64
from contextlib import redirect_stdout
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
import aia17_npz_timing_canary as m


class FakeClock:
    """Fixed-offset synthetic test clock, NOT an astronomical implementation."""
    def ticks(self, iso, scale):
        return [round(((datetime.fromisoformat(s)-datetime(1970,1,1)).total_seconds()
                      + (37 if scale == 'utc' else 0))*1000000) for s in iso]
    def utc_text(self, ticks):
        return [(datetime(1970,1,1)+timedelta(microseconds=t-37000000)).isoformat(timespec='microseconds')+'Z'
                for t in ticks]


def raw_iso(s):
    return s[:10].replace('.', '-')+'T'+s[11:-4]


def record(year=2025, sid=None):
    sid = sid or f'{year}0101_0100_HARP100_NOAA13000'
    g = m.SID.fullmatch(sid)
    dt = datetime.strptime(sid[:13], '%Y%m%d_%H%M')
    return {'sample_id': sid, 'stored_year': str(year), 'expected_uri': f'gs://{m.BUCKET}/{m.prefix(year)}{sid}.npz',
            'name': m.prefix(year)+sid+'.npz', 'object_status': 'EXACT_NONEMPTY_OBJECT',
            'generation': '1234', 'object_bytes': '10', 'original_label': '0',
            'stored_issue_time': str(dt), 'raw_T_REC': dt.strftime('%Y.%m.%d_%H:%M:%S_TAI'),
            'HARPNUM': g[3], 'NOAA_AR_clean': g[4], 'in_baseline': '0',
            'selection_reason': 'one_label_independent_hash_sample_per_stored_year'}


def save_npz(p, r, per_channel=False, **overrides):
    x = np.broadcast_to(np.linspace(0,1,512,dtype=np.float32)[:,None,None], (512,512,6)).copy()
    fields = {'x': x, 'sample_id': np.array(r['sample_id']), 'HARPNUM': np.array(int(r['HARPNUM'])),
              'NOAA_AR_clean': np.array(int(r['NOAA_AR_clean'])), 'T_REC_dt': np.array(r['stored_issue_time']),
              'y': np.array(1), 'channels': np.array(['aia'+str(v) for v in m.CHANNELS])}
    if per_channel:
        fields['wavelengths'] = np.array(m.CHANNELS)
        fields['channel_metadata'] = np.array(json.dumps({str(w): {
            'used_time': r['stored_issue_time'], 'delta_seconds': 0,
            'source_file': f'aia.lev1_euv_12s.2025-01-01T010000Z.{w}.image.fits'} for w in m.CHANNELS}))
    else:
        fields['used_timestamp'] = np.array(r['stored_issue_time'])
        fields['used_s3_path'] = np.array('s3://example/20250101_0100.nc')
    fields.update(overrides)
    np.savez_compressed(p, **fields)
    r['object_bytes'] = str(p.stat().st_size)
    h = m.file_hashes(p)
    r.update(crc32c=h['crc32c'], md5Hash=h['md5Hash'])


class FakeClient:
    def __init__(self, blobs): self.blobs = blobs; self.calls=[]
    def download(self, c, partial):
        self.calls.append((c['expected_uri'], c['generation']))
        partial.write_bytes(self.blobs[c['sample_id']])


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.d=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_crc32c_and_sha_known_vector(self):
        p=self.d/'vector'; p.write_bytes(b'123456789')
        self.assertEqual(m.file_hashes(p)['crc32c'], '4waSgw==')
        self.assertEqual(m.file_hashes(p)['sha256'], hashlib.sha256(b'123456789').hexdigest())
    def test_candidate_wrong_bucket_rejected(self):
        r=record(); r['expected_uri']=r['expected_uri'].replace(m.BUCKET, 'other')
        with self.assertRaises(ValueError): m.validate_candidates([r],1)
    def test_candidate_duplicate_rejected(self):
        r=record()
        with self.assertRaises(ValueError): m.validate_candidates([r,r],2)
    def test_total_payload_guard(self):
        records=[record(y) for y in range(2010,2019)]
        for r in records:r['object_bytes']=str(m.MAX_OBJECT_BYTES)
        with self.assertRaisesRegex(ValueError, '128 MiB'):m.validate_candidates(records,9)
    def test_naive_scale_not_assumed_utc(self):
        clock=FakeClock(); t=clock.ticks(['2025-01-01T01:00:00'],'tai')[0]
        r=m.timing_entry('used_timestamp','2025-01-01 01:00:00',t,clock)
        self.assertEqual(r['utc_hypothesis']['delta_seconds_frame_minus_issue'],37)
        self.assertEqual(r['tai_hypothesis']['delta_seconds_frame_minus_issue'],0)
        self.assertEqual(r['status'],'UNRESOLVED_SCALE_CONDITIONAL_COMPARISONS')
    def test_explicit_tai_is_not_utc(self):
        clock=FakeClock(); t=clock.ticks(['2025-01-01T01:00:00'],'tai')[0]
        r=m.timing_entry('field','2025.01.01_01:00:00_TAI',t,clock)
        self.assertTrue(r['tai_declared']['passes_both_timing_rules'])
        self.assertNotIn('utc_hypothesis',r)
        self.assertFalse(r['observation_header_verified'])
    def test_utc_z_and_zero_offset_explicit(self):
        for suffix in ['Z','+00:00']:
            r=m.normal_time('2025-01-01T01:00:00'+suffix)
            self.assertEqual(r[1],'utc')
    def test_unknown_timestamp_stays_unparsed(self):
        r=m.timing_entry('field','not a time',0,FakeClock())
        self.assertEqual(r['status'],'TIMESTAMP_UNPARSED')
    def test_both_rules_need_past_and_tolerance(self):
        clock=FakeClock(); t=clock.ticks(['2025-01-01T01:00:00'],'utc')[0]
        for timestamp, expected in [('00:57:00',True),('00:56:59',False),('01:00:01',False),('01:00:00',True)]:
            r=m.timing_entry('field','2025-01-01T'+timestamp+'Z',t,clock)
            self.assertEqual(r['utc_declared']['passes_both_timing_rules'],expected)
    def test_legacy_content_and_label_preservation(self):
        r=record(); p=self.d/'sample.npz'; save_npz(p,r)
        out=m.inspect_file(p,r,np,FakeClock(),raw_iso)
        self.assertEqual(out['content_status'],'CONTENT_CHECKS_PASSED_ON_THIS_FILE')
        self.assertEqual(out['original_label'],0)
        self.assertFalse(out['embedded_label_comparisons']['y']['matches_original_manifest_label'])
        self.assertEqual(out['format'],'SHARED_USED_TIMESTAMP')
        self.assertFalse(out['training_authorised'])
    def test_production_channels_and_filename_are_separate(self):
        r=record(); p=self.d/'sample.npz'; save_npz(p,r,per_channel=True)
        out=m.inspect_file(p,r,np,FakeClock(),raw_iso)
        self.assertEqual(out['content_status'],'CONTENT_CHECKS_PASSED_ON_THIS_FILE')
        self.assertEqual(len(out['timing_evidence']),12)
        self.assertFalse(any(t['observation_header_verified'] for t in out['timing_evidence']))
    def test_bad_shape_is_flagged_not_training_clearance(self):
        r=record(); p=self.d/'sample.npz'; save_npz(p,r,x=np.ones((8,8,6)))
        out=m.inspect_file(p,r,np,FakeClock(),raw_iso)
        self.assertIn('TENSOR_SHAPE_OR_DTYPE_REVIEW',out['issues'])
    def test_nan_tensor_is_flagged(self):
        r=record(); p=self.d/'sample.npz'
        x=np.ones((512,512,6),dtype=np.float32);x[0,0,0]=float('nan')
        save_npz(p,r,x=x)
        out=m.inspect_file(p,r,np,FakeClock(),raw_iso)
        self.assertIn('NONFINITE_CHANNEL_94',out['issues'])
    def test_wrong_channel_order_is_flagged(self):
        r=record(); p=self.d/'sample.npz';save_npz(p,r,channels=np.array(m.CHANNELS[::-1]))
        out=m.inspect_file(p,r,np,FakeClock(),raw_iso)
        self.assertIn('CHANNEL_ORDER_OR_DECLARATION_REVIEW',out['issues'])
    def test_pickle_array_is_rejected(self):
        p=self.d/'sample.npz';np.savez(p,x=np.array({'bad':'object'},dtype=object))
        with self.assertRaisesRegex(ValueError,'pickle'):m.safe_npz(p,np)
    def test_malformed_npy_declared_allocation_rejected(self):
        b=io.BytesIO();np.lib.format.write_array_header_1_0(b,{'descr':'<f8','fortran_order':False,'shape':(1000000000,)})
        p=self.d/'bad.npz'
        with zipfile.ZipFile(p,'w') as z:z.writestr('x.npy',b.getvalue())
        with self.assertRaisesRegex(ValueError,'allocation'):m.safe_npz(p,np)
    def test_zip_path_member_rejected(self):
        p=self.d/'bad.npz'
        with zipfile.ZipFile(p,'w') as z:z.writestr('../x.npy',b'no')
        with self.assertRaises(ValueError):m.safe_npz(p,np)
    def test_checksum_cache_reuse(self):
        r=record();p=self.d/'src.npz';save_npz(p,r); cache=self.d/'cache';cache.mkdir()
        client=FakeClient({r['sample_id']:p.read_bytes()})
        out,receipt=m.obtain(r,cache,client)
        out2,receipt2=m.obtain(r,cache,client)
        self.assertEqual(len(client.calls),1);self.assertEqual(out,out2);self.assertTrue(receipt2['reused'])
    def test_tampered_download_rejected(self):
        r=record();p=self.d/'src.npz';save_npz(p,r);cache=self.d/'cache';cache.mkdir()
        client=FakeClient({r['sample_id']:b'x'*p.stat().st_size})
        with self.assertRaisesRegex(ValueError,'mismatch'):m.obtain(r,cache,client)
        self.assertEqual(list(cache.glob('*.receipt.json')),[])
    def test_redirect_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'redirect'):
            m.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://untrusted.invalid/')

    def _fixture(self):
        repo=self.d/'repo';root=self.d/'inventory';rd=root/'reports'/m.REPORT_ID
        rd.mkdir(parents=True);(root/'listings').mkdir();repo.mkdir()
        cand=[];blobs={};receipts=[]
        for y in range(2010,2027):
            cand.append(record(y))
        cand.append(record(2024,m.BOUNDARY));cand[-1]['selection_reason']='previously_identified_boundary_case'
        for i,r in enumerate(cand):
            p=self.d/f'object{i}.npz';save_npz(p,r,per_channel=(int(r['stored_year'])>=2025))
            blobs[r['sample_id']]=p.read_bytes()
            r['in_baseline']='1' if int(r['stored_year'])<=2016 else '0'
        master=self.d/'master.csv'
        masterrows=[{'sample_id':r['sample_id'],'T_REC_dt':r['stored_issue_time'], 'T_REC':r['raw_T_REC'],
                     'HARPNUM':r['HARPNUM'],'NOAA_AR_clean':r['NOAA_AR_clean'],
                     'label_48h_final':r['original_label']} for r in cand]
        m.write_csv(master,masterrows,list(masterrows[0]))
        lockrel='docs/research_audit/2026-09-15/stage1/source_lock_snapshot.json'
        lockpath=repo/lockrel;lockpath.parent.mkdir(parents=True)
        m.write_json(lockpath,{'sources':[{'id':'curated_master','local_path':str(master),
                           'size_bytes':master.stat().st_size,'sha256':m.sha(master)}]})
        fields=list(cand[0]);m.write_csv(rd/'timing_canary_candidates.csv',cand,fields)
        m.write_csv(rd/'target_object_register.csv',cand,fields)
        m.write_csv(rd/'yearly_object_coverage.csv',[{'year':2010}],['year'])
        for y in range(2010,2027):
            lp=root/'listings'/f'objects_{y}.json'
            objects=[{'name':r['name'],'generation':r['generation'],'size':r['object_bytes'],
                      'crc32c':r['crc32c'],'md5Hash':r['md5Hash']} for r in cand if int(r['stored_year'])==y]
            lp.write_text(json.dumps(objects))
            receipts.append({'year':y,'sha256':m.sha(lp)})
        report={'status':m.EXPECTED_STATUS,'input_contract':{'bucket':m.BUCKET,'source_sha256':{lockrel:m.sha(lockpath)}},
                'canary_candidate_count':18,'master_targets':18,'status_counts':{'EXACT_NONEMPTY_OBJECT':18},
                'listing_receipts':receipts}
        m.write_json(rd/'archive_reconciliation_report.json',report)
        m.write_json(rd/'COMPLETE.json',{'status':m.EXPECTED_STATUS,'output_sha256':{f.name:m.sha(f) for f in rd.iterdir()}})
        args=argparse.Namespace(repo=repo,inventory=root,report_dir=None,work=self.d/'canary')
        return args,blobs,master
    def test_full_18_file_simulated_workflow_and_reuse(self):
        args,blobs,master=self._fixture(); before=m.sha(master);client=FakeClient(blobs)
        b=(np,FakeClock(),raw_iso,{'passed':True,'scope':'synthetic fixed-offset fake; not real astronomy'})
        with redirect_stdout(io.StringIO()):self.assertEqual(m.run(args,client,b),0)
        self.assertEqual(len(client.calls),18);self.assertEqual(m.sha(master),before)
        out=sorted((args.work/'reports').iterdir())[-1]
        report=m.read_json(out/'npz_canary_report.json')
        self.assertEqual(report['content_status_counts'],{'CONTENT_CHECKS_PASSED_ON_THIS_FILE':18})
        self.assertFalse(report['training_authorised']);self.assertTrue((out/'COMPLETE.json').exists())
        with redirect_stdout(io.StringIO()):self.assertEqual(m.run(args,client,b),0)
        self.assertEqual(len(client.calls),18)
    def test_inventory_tamper_stops_before_network(self):
        args,blobs,master=self._fixture();client=FakeClient(blobs)
        p=args.inventory/'reports'/m.REPORT_ID/'timing_canary_candidates.csv'
        p.write_text(p.read_text()+'\n')
        with redirect_stdout(io.StringIO()),self.assertRaises(ValueError):
            m.run(args,client,(np,FakeClock(),raw_iso,{'passed':True}))
        self.assertEqual(client.calls,[])


if __name__=='__main__':unittest.main(verbosity=2)
