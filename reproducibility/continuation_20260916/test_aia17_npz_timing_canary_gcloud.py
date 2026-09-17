import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import aia17_npz_timing_canary as b
import aia17_npz_timing_canary_gcloud as m
from test_aia17_npz_timing_canary import record, save_npz, CanaryTests, FakeClock, raw_iso

FAKE = r'''#!PYTHON
import json, os, pathlib, sys, time
args = sys.argv[1:]
assert args[:2] == ['storage', 'cp'], args
assert '--do-not-decompress' in args and '--quiet' in args, args
src, dst = args[2], pathlib.Path(args[3])
assert src.startswith('gs://suryabench-sharp-pipeline-bamidele/'), args
assert src.endswith('#1234'), args
assert not any(c in src for c in ['*', '?', '[']), args
assert os.environ['CLOUDSDK_STORAGE_MAX_RETRIES'] == '3'
assert os.environ['CLOUDSDK_STORAGE_CHECK_HASHES'] == 'always'
assert os.environ['CLOUDSDK_STORAGE_RESUMABLE_THRESHOLD'] == '1'
root = pathlib.Path(os.environ['AIA_TEST_DATA'])
with (root/'calls.txt').open('a') as f: f.write(json.dumps(args)+'\n')
mode = os.environ.get('AIA_TEST_MODE','ok')
if mode == 'hang': time.sleep(60)
if mode == 'denied':
    print('ERROR: HTTP 403 permission denied', flush=True); sys.exit(1)
sid = src.split('/')[-1].split('.npz#')[0]
data = (root/(sid+'.npz')).read_bytes()
tmp = dst.with_suffix('.gstmp')
if mode == 'partial_fail':
    tmp.write_bytes(data[:100]); print('ERROR: connection interrupted', flush=True); sys.exit(1)
if tmp.exists():
    assert data.startswith(tmp.read_bytes()); tmp.unlink()
    print('Resumed simulated partial transfer', flush=True)
if mode == 'corrupt': data = b'!' * len(data)
dst.write_bytes(data)
print('Completed files 1/1 (SIMULATED gcloud; not live cloud)', flush=True)
'''

class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.d=Path(self.tmp.name)
        self.bin=self.d/'gcloud'
        self.bin.write_text(FAKE.replace('PYTHON',sys.executable,1));self.bin.chmod(0o700)
        self.data=self.d/'data';self.data.mkdir()
        self.env=patch.dict(os.environ,{'AIA_TEST_DATA':str(self.data),'AIA_TEST_MODE':'ok'})
        self.env.start()
        self.which=patch.object(m.shutil,'which',return_value=str(self.bin));self.which.start()
        self.root=self.d/'canary';self.root.mkdir();self.cache=self.root/'objects';self.cache.mkdir()
        self.client=m.GcloudDownloadClient(b,self.root/'transport_gcloud_v1')
        self.r=record();save_npz(self.data/(self.r['sample_id']+'.npz'),self.r)
    def tearDown(self):
        self.which.stop();self.env.stop();self.tmp.cleanup()
    def calls(self):
        p=self.data/'calls.txt';return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
    def run_obtain(self):
        with redirect_stdout(io.StringIO()):return b.obtain(self.r,self.cache,self.client)
    def test_download_generation_and_checksums(self):
        out,rec=self.run_obtain()
        self.assertEqual(out.read_bytes(),(self.data/(self.r['sample_id']+'.npz')).read_bytes())
        self.assertTrue(self.calls()[0][2].endswith('#1234'))
        self.assertEqual(rec['hashes'],b.file_hashes(out))
    def test_verified_complete_cache_has_no_second_cli_call(self):
        self.run_obtain();out,rec=self.run_obtain()
        self.assertEqual(len(self.calls()),1);self.assertTrue(rec['reused'])
    def test_partial_failure_preserved_then_native_resume(self):
        with patch.dict(os.environ,{'AIA_TEST_MODE':'partial_fail'}):
            with self.assertRaises(RuntimeError):self.run_obtain()
        self.assertEqual(len(list(self.client.root.rglob('*.gstmp'))),1)
        self.assertEqual(len(list(self.cache.glob('*.receipt.json'))),0)
        self.run_obtain();self.assertEqual(len(self.calls()),2)
        self.assertFalse(list(self.client.root.rglob('*.gstmp')))
    def test_checksum_failure_never_gets_receipt(self):
        with patch.dict(os.environ,{'AIA_TEST_MODE':'corrupt'}):
            with self.assertRaisesRegex(ValueError,'mismatch'):self.run_obtain()
        self.assertEqual(list(self.cache.glob('*.receipt.json')),[])
    def test_permission_failure_is_not_retried_by_adapter(self):
        with patch.dict(os.environ,{'AIA_TEST_MODE':'denied'}):
            with self.assertRaisesRegex(RuntimeError,'exit code 1'):self.run_obtain()
        self.assertEqual(len(self.calls()),1)
        saved=list((self.client.root/'logs').glob('*.log'))
        self.assertIn('403',saved[0].read_text())
    def test_timeout_terminates_only_spawned_command(self):
        self.client.timeout=2.0
        with patch.dict(os.environ,{'AIA_TEST_MODE':'hang'}):
            with self.assertRaisesRegex(TimeoutError,'exceeded'):self.run_obtain()
        self.assertEqual(len(self.calls()),1)
    def test_wrong_bucket_rejected_before_cli(self):
        self.r['expected_uri']=self.r['expected_uri'].replace(b.BUCKET,'wrong')
        with self.assertRaises(ValueError):self.run_obtain()
        self.assertEqual(self.calls(),[])
    def test_no_generation_fallback(self):
        self.r['generation']='latest'
        with self.assertRaises(ValueError):self.run_obtain()
        self.assertEqual(self.calls(),[])
    def test_original_module_hash_check(self):
        orig=Path(b.__file__)
        self.assertEqual(m.sha(orig),m.BASE_SHA256)
        self.assertEqual(m.load_base(orig).VERSION,b.VERSION)
        altered=self.d/'altered.py';altered.write_bytes(orig.read_bytes()+b'\n')
        with self.assertRaises(ValueError):m.load_base(altered)
    def test_child_environment_no_persistent_setting_changes(self):
        before=dict(os.environ);env=m.private_env(self.d/'trackers')
        self.assertEqual(dict(os.environ),before)
        self.assertEqual(env['CLOUDSDK_STORAGE_DOWNLOAD_CHUNK_SIZE'],str(1024**2))
        self.assertEqual(env['CLOUDSDK_CORE_LOG_HTTP'],'false')
    def test_corrupt_existing_native_result_not_overwritten(self):
        with patch.dict(os.environ,{'AIA_TEST_MODE':'corrupt'}):
            with self.assertRaises(ValueError):self.run_obtain()
        staged=next(self.client.root.rglob('payload.npz'));saved=staged.read_bytes()
        with self.assertRaises(ValueError):self.run_obtain()
        self.assertEqual(staged.read_bytes(),saved);self.assertEqual(len(self.calls()),1)
    def test_missing_locked_hash_rejected(self):
        self.r['crc32c']='';self.r['md5Hash']=''
        with self.assertRaisesRegex(ValueError,'checksum'):self.run_obtain()
        self.assertEqual(self.calls(),[])
    def test_transport_record_written_and_sources_preserved(self):
        source=self.data/(self.r['sample_id']+'.npz');before=b.sha(source)
        self.run_obtain();self.assertEqual(b.sha(source),before)
        rec=json.loads(next((self.client.root/'logs').glob('*.json')).read_text())
        self.assertEqual(rec['status'],'TRANSFER_COMPLETE_LOCKED_CHECKSUMS_PASSED')
        self.assertNotIn('Authorization',json.dumps(rec))
    def test_full_18_sample_analysis_with_fake_native_transport(self):
        fixture=CanaryTests();fixture.d=self.d
        args,blobs,master=fixture._fixture()
        for sid,data in blobs.items():(self.data/(sid+'.npz')).write_bytes(data)
        client=m.GcloudDownloadClient(b,args.work/'transport_gcloud_v1')
        before=b.sha(master)
        bundle=(np,FakeClock(),raw_iso,{'passed':True,'scope':'synthetic reference clock'})
        with redirect_stdout(io.StringIO()):self.assertEqual(b.run(args,client,bundle),0)
        self.assertEqual(len(self.calls()),18);self.assertEqual(b.sha(master),before)
        rd=sorted((args.work/'reports').iterdir())[-1]
        report=json.loads((rd/'npz_canary_report.json').read_text())
        self.assertFalse(report['training_authorised'])
        self.assertEqual(report['content_status_counts'],{'CONTENT_CHECKS_PASSED_ON_THIS_FILE':18})
        with redirect_stdout(io.StringIO()):self.assertEqual(b.run(args,client,bundle),0)
        self.assertEqual(len(self.calls()),18)

if __name__=='__main__':unittest.main(verbosity=2)
