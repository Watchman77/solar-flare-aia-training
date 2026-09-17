import base64,csv,hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import h5py
import aia17_consolidated_resolution as m

S='20130411_2036_HARP2651_NOAA11721'
C={'results':[{'sample_id':S,'original_label':0,'metadata':{'y':1},'embedded_label_comparisons':{'y':{'matches_original_manifest_label':False}}}]}

def scan(old='1',final='0'):
    return {'matches':{S:[{'record_number':1,'raw':{'label_48h_global_old':old,'label_48h_final':final}}]}}

class Response(io.BytesIO):
    def __init__(self,data,status,headers):super().__init__(data);self.status=status;self.headers=headers

class Remote:
    def __init__(self,data,mode='ok'):self.data=data;self.mode=mode;self.calls=[]
    def __call__(self,req,timeout=20):
        self.calls.append(req)
        if req.get_method()=='HEAD':return Response(b'',200,{'Content-Length':str(len(self.data)),'ETag':'"fixed"'})
        raw=req.get_header('Range');start,end=map(int,raw.removeprefix('bytes=').split('-'))
        headers={'Content-Range':f'bytes {start}-{end}/{len(self.data)}','ETag':'"fixed"'}
        if self.mode=='changed':headers['ETag']='"changed"'
        data=self.data[start:end+1]
        if self.mode=='short':data=data[:-1]
        return Response(data,200 if self.mode=='full' else 206,headers)

class Tests(unittest.TestCase):
    def test_legacy_confirmed(self):
        r=m.label_findings(C,{'master':scan()})
        self.assertEqual(r[0]['status'],'LEGACY_GLOBAL_LABEL_MATCH_CONFIRMED_FOR_THIS_SAMPLE')
    def test_no_invented_legacy_explanation(self):
        self.assertIn('NOT_YET',m.label_findings(C,{'master':scan('0')})[0]['status'])
    def test_manifest_conflict_not_overruled(self):
        self.assertEqual(m.label_findings(C,{'a':scan(),'b':scan('1','1')})[0]['status'],'MANIFEST_CONFLICT_REVIEW')
    def test_duplicates_not_first_row_selected(self):
        x=scan();x['matches'][S]*=2
        self.assertEqual(m.label_findings(C,{'a':x})[0]['status'],'MANIFEST_CONFLICT_REVIEW')
    def test_csv_preserves_all_records_and_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv';p.write_text('sample_id,label_48h_final\n'+S+',0\n'+S+',1\n')
            before=p.read_bytes();r=m.pick_csv(p,{S})
            self.assertEqual(len(r['matches'][S]),2);self.assertEqual(p.read_bytes(),before)
    def test_csv_malformed_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv';p.write_text('sample_id,y\n'+S+',0,unexpected\n')
            with self.assertRaises(ValueError):m.pick_csv(p,{S})
    def test_exact_allowlist(self):
        x=m.selected_manifests();self.assertEqual(len(x),13)
        self.assertNotIn('manifests/2013/manifest_2013_GLOBAL_BACKUP.csv',x)
    def test_ranges_seek_and_cache(self):
        data=bytes(range(256))*300
        with tempfile.TemporaryDirectory() as d:
            remote=Remote(data)
            with m.RemoteHDF('https://test/x',d,m.Budget(),opener=remote) as f:
                f.seek(32760);self.assertEqual(f.read(50),data[32760:32810])
                f.seek(-10,2);self.assertEqual(f.read(10),data[-10:])
                self.assertTrue(all(c.get_header('If-match')=='"fixed"' for c in remote.calls[1:]))
            with m.RemoteHDF('https://test/x',d,m.Budget(),opener=lambda *a,**k:self.fail('Network not expected')) as f:
                f.seek(32760);self.assertEqual(f.read(50),data[32760:32810])
    def test_unbounded_read_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with m.RemoteHDF('https://test/x',d,m.Budget(),opener=Remote(b'x'*(m.RANGE_CAP+1))) as f:
                with self.assertRaises(ValueError):f.read()
    def test_server_ignoring_range_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with m.RemoteHDF('https://test/x',d,m.Budget(),opener=Remote(b'x'*200,mode='full')) as f:
                with self.assertRaisesRegex(ValueError,'Range'):f.read(8)
    def test_changed_remote_etag_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with m.RemoteHDF('https://test/x',d,m.Budget(),opener=Remote(b'x'*200,mode='changed')) as f:
                with self.assertRaisesRegex(ValueError,'ETag'):f.read(8)
    def test_truncated_range_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with m.RemoteHDF('https://test/x',d,m.Budget(),opener=Remote(b'x'*200,mode='short')) as f:
                with self.assertRaisesRegex(ValueError,'range response'):f.read(8)
    def test_real_hdf_attributes_without_pixels(self):
        # The file contains very large logical arrays, but no pixel data chunks are allocated/read.
        b=io.BytesIO()
        with h5py.File(b,'w') as h:
            h.attrs['data_time']='20130411_2036'
            for w in m.CHANNELS:
                ds=h.create_dataset('aia'+str(w),shape=(4096,4096),chunks=(64,64),dtype='f4')
                ds.attrs['t_obs']='2013-04-11T20:35:24Z'
                ds.attrs['meta_0']=json.dumps({'T_OBS':'2013-04-11T20:35:24Z','EXPTIME':2.0})
        payload=b.getvalue()
        with tempfile.TemporaryDirectory() as d:
            with m.RemoteHDF('https://test/x',d,m.Budget(),opener=Remote(payload)) as f:
                r=m.read_hdf_attributes(f)
                self.assertEqual(len(r['channels']),6)
                self.assertEqual(r['channels']['aia94']['attributes']['t_obs'],'2013-04-11T20:35:24Z')
                self.assertLess(f.bytes_read,200000)
    def test_external_links_not_followed(self):
        b=io.BytesIO()
        with h5py.File(b,'w') as h:h['aia94']=h5py.ExternalLink('/does/not/exist','/image')
        b.seek(0);r=m.read_hdf_attributes(b)
        self.assertEqual(r['channels']['aia94']['status'],'MISSING_OR_NONLOCAL_LINK')
    def test_failed_source_stays_unresolved(self):
        def fail():raise TimeoutError('synthetic')
        r=m.source_job('test failure is expected',fail,{})
        self.assertEqual(r['status'],'UNRESOLVED_SOURCE')
    def test_csv_cache_sha_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            rel='manifests/2013/manifest_2013.csv';uri=f'gs://{m.BUCKET}/{rel}'
            sd=Path(d)/hashlib.sha256(uri.encode()).hexdigest()[:24];sd.mkdir()
            data=b'sample_id,y\n';(sd/'source.csv').write_bytes(data)
            m.save(sd/'object.json',{'size':len(data),'generation':'123','name':rel,'bucket':m.BUCKET})
            m.save(sd/'receipt.json',{'uri':uri,'generation':'123','sha256':m.digest(sd/'source.csv')})
            with patch.object(m.subprocess,'run',side_effect=AssertionError('No network')):
                c=m.CloudCSVs(d,m.Budget());p,_=c.get(rel);self.assertEqual(p.read_bytes(),data)
                p.write_bytes(b'changed')
                with self.assertRaises(ValueError):m.CloudCSVs(d,m.Budget()).get(rel)
    def test_budget_does_not_clear_after_expiry(self):
        b=m.Budget();b.end=0
        with self.assertRaises(TimeoutError):b.left()
    def test_notebook_scan_never_executes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'notebooks/training/16B_aia_sharp_intermediate_fusion_training.ipynb';p.parent.mkdir(parents=True)
            m.save(p,{'cells':[{'cell_type':'code','source':['raise RuntimeError("never execute")\n','self.labels = self.df[label_col].to_numpy()\n'],'execution_count':8}]})
            r=m.notebook_lineage(Path(d));self.assertEqual(len(r[0]['snippets']),1)
    def test_binary_does_not_fill_unknown_with_zero(self):
        self.assertIsNone(m.binary(''));self.assertIsNone(m.binary('NaN'))
    def test_no_cloud_write_commands(self):
        source=Path(m.__file__).read_text()
        self.assertNotIn("'git','push'",source)
        self.assertNotIn("'storage','rm'",source)
        self.assertNotIn("'compute','instances','create'",source)

if __name__=='__main__':unittest.main(verbosity=2)
