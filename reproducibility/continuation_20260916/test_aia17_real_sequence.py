import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest import mock
import csv,gzip,sys
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import aia17_real_sequence_canary as m

def imp(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
base=imp('fixture_npz_base',ROOT/'dependencies/aia17_npz_timing_canary.py')
source=imp('fixture_source_base',ROOT/'dependencies/aia17_consolidated_resolution.py')
strict=imp('fixture_strict_index',ROOT/'dependencies/aia17_build_temporal_manifest.py')

class Clock:
 """Fixture only, restricted to 2011/2014 known offsets; not a production replacement."""
 def ticks(self,values,scale):
  out=[]
  for text in values:
   t=datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
   if t.year not in (2011,2014):raise ValueError('Outside fixture range')
   offset=34 if t.year==2011 else 35
   out.append(round(t.timestamp()*1e6)+(offset*1000000 if scale=='utc' else 0))
  return out
 def utc_text(self,values):
  out=[]
  for val in values:
   t=datetime.fromtimestamp(val/1e6,tz=timezone.utc);offset=34 if t.year==2011 else 35
   out.append((t-timedelta(seconds=offset)).strftime('%Y-%m-%dT%H:%M:%S.%fZ'))
  return out
clock=Clock()

def fixture_record(role='train',label=0,n=1):
 d=datetime(2011 if role=='train' else 2014,3,15,12,0,0)+timedelta(days=n)
 sid=d.strftime('%Y%m%d_%H%M')+f'_HARP{n}_NOAA{11000+n}'
 tick=clock.ticks([d.isoformat()],'tai')[0]
 r={'version':'17c-nominal-history-index-v1','target_sample_id':sid,'HARPNUM':n,'NOAA_AR_clean':11000+n,
  'issue_utc':clock.utc_text([tick])[0],'issue_raw_TAI':d.strftime('%Y.%m.%d_%H:%M:%S_TAI'),
  'issue_tai_us':tick,'forecast_end_utc_48_SI_hours':clock.utc_text([tick+172800000000])[0],
  'original_label_48h_final':label,'label_replaced':False,'label_boundary_review_required':False,
  'history_status':m.AVAILABLE,'training_authorised':False,'canary_role':role,'region_component_id':'C'+str(n),'frames':[]}
 for lag in m.LAGS:
  t=d-timedelta(minutes=lag);s=t.strftime('%Y%m%d_%H%M')+f'_HARP{n}_NOAA{11000+n}'
  r['frames'].append({'lag_minutes':lag,'requested_slot_tai_us':tick-lag*60000000,'history_sample_id':s,
   'raw_T_REC_TAI':t.strftime('%Y.%m.%d_%H:%M:%S_TAI'),'record_utc':clock.utc_text([tick-lag*60000000])[0],
   'object_uri':f'gs://{m.BUCKET}/samples_npz/{t.year}/{s}.npz','object_generation':'123',
   'object_status':'EXACT_NONEMPTY_OBJECT','object_bytes':1,'nominal_candidate':True})
 return r

def attrs_for(r,f,delay=5):
 mid=f['requested_slot_tai_us']+round(delay*1e6);start=mid-1000000
 data={}
 for w in m.CHANNELS:
  meta={'telescop':'SDO/AIA','instrume':'AIA_ATA1','t_obs':clock.utc_text([mid])[0][:-1],
    'date-obs':clock.utc_text([start])[0][:-1], 't_rec':f['record_utc'][:-1],
    'wavelnth':w,'quality':0,'exptime':2.0}
  data['aia'+str(w)]={'status':'ATTRIBUTES_READ_NO_PIXELS','attributes':{'meta_0':json.dumps(meta),
    'meta_1':json.dumps({**meta,'exptime':1.0})}}
 return {'source':{'url':'https://nasa-surya-bench.s3.amazonaws.com/fixture.nc','content':{'channels':data}}}

def side(r,keep=True):
 return {'target_sample_id':r['target_sample_id'],'issue_utc':r['issue_utc'],
 'original_label_48h_final':str(r['original_label_48h_final']),'proposed_role':r['canary_role'],
 'region_component_id':r['region_component_id'],'nominal_history_complete':'1',
 'role_constraints_pass':'1' if keep else '0','structural_exclusion_reasons':'' if keep else 'TEST',
 'training_authorised':'False'}

def csv_write(p,rows):
 with gzip.open(p,'wt',encoding='utf8',newline='') as h:
  w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

class Tests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def test_uploaded_summary_hashes(self):
  p=ROOT/'reviewed_split_summary';marker=m.js(p/'COMPLETE.json')
  checked=0
  for name,h in marker['output_sha256'].items():
   if (p/name).exists():m.verify(p/name,h);checked+=1
  self.assertEqual(checked,5)
 def test_selection_is_deterministic_and_development_only(self):
  rows=[side(fixture_record(role,l,i+1)) for i,(role,l) in enumerate(m.COMBINATIONS)]
  extra=copy.deepcopy(rows[0]);extra.update(target_sample_id='20220101_1200_HARP50_NOAA13001',proposed_role='independent_cycle25_test',issue_utc='2022-01-01T12:00:00Z')
  p=self.root/'s.csv.gz';csv_write(p,rows+[extra]);sel,_=m.select_examples(p,5)
  self.assertEqual([int(r['original_label_48h_final']) for r in sel],[0,1,0,1])
  csv_write(self.root/'s2.csv.gz',list(reversed(rows+[extra])))
  self.assertEqual(sel,m.select_examples(self.root/'s2.csv.gz',5)[0])
 def test_no_fallback_if_positive_stratum_missing(self):
  p=self.root/'s.csv.gz';csv_write(p,[side(fixture_record())])
  with self.assertRaisesRegex(ValueError,'No separate'):m.select_examples(p,1)
 def test_duplicate_role_ids_rejected(self):
  p=self.root/'s.csv.gz';r=side(fixture_record());csv_write(p,[r,r])
  with self.assertRaisesRegex(ValueError,'Duplicate'):m.select_examples(p,2)
 def test_retained_flag_conflict_rejected(self):
  p=self.root/'s.csv.gz';r=side(fixture_record());r['structural_exclusion_reasons']='X';csv_write(p,[r])
  with self.assertRaisesRegex(ValueError,'contradicts'):m.select_examples(p,1)
 def test_unknown_csv_time_not_silently_utc(self):
  with self.assertRaisesRegex(ValueError,'identified'):m.header_time('2014-03-01T12:00:00',{},clock)
 def test_conflicting_scales_rejected(self):
  with self.assertRaisesRegex(ValueError,'Conflicting'):m.header_time('2014-03-01T12:00:00Z',{'timesys':'TAI'},clock)
 def test_original_exposure_used_not_processed_one(self):
  r=fixture_record();f=r['frames'][0];result=m.source_time_screen(r,f,attrs_for(r,f),clock)
  self.assertTrue(result['all_recorded_time_screens_pass'])
  self.assertEqual(result['channels'][0]['original_mean_exposure_seconds'],2)
  self.assertFalse(result['strict_contributing_time_clearance'])
 def test_future_observation_not_admitted(self):
  r=fixture_record();f=r['frames'][2]
  self.assertFalse(m.source_time_screen(r,f,attrs_for(r,f,delay=96*60+5),clock)['all_recorded_time_screens_pass'])
 def test_stale_source_not_admitted(self):
  r=fixture_record();f=r['frames'][0]
  self.assertFalse(m.source_time_screen(r,f,attrs_for(r,f,delay=-1440),clock)['all_recorded_time_screens_pass'])
 def test_missing_original_header_rejected(self):
  r=fixture_record();f=r['frames'][0];ev=attrs_for(r,f);del ev['source']['content']['channels']['aia94']['attributes']['meta_0']
  with self.assertRaisesRegex(ValueError,'meta_0'):m.source_time_screen(r,f,ev,clock)
 def test_quality_not_silently_ignored(self):
  r=fixture_record();f=r['frames'][0];ev=attrs_for(r,f);a=ev['source']['content']['channels']['aia94']['attributes'];m0=json.loads(a['meta_0']);m0['quality']=1;a['meta_0']=json.dumps(m0)
  with self.assertRaisesRegex(ValueError,'quality'):m.source_time_screen(r,f,ev,clock)
 def test_source_header_start_conflicts_rejected(self):
  r=fixture_record();f=r['frames'][0];ev=attrs_for(r,f);a=ev['source']['content']['channels']['aia94']['attributes'];m0=json.loads(a['meta_0']);m0['date_obs']='2011-03-16T00:00:00';a['meta_0']=json.dumps(m0)
  with self.assertRaisesRegex(ValueError,'Conflicting start'):m.source_time_screen(r,f,ev,clock)
 def test_mean_end_estimate_does_not_pass_strict_gate(self):
  r=fixture_record();f=r['frames'][0];e={'history_sample_id':f['history_sample_id'],'object_uri':f['object_uri'],
   'object_generation':'123','HARPNUM':r['HARPNUM'],'NOAA_AR_clean':r['NOAA_AR_clean'],'npz_sha256':'a'*64,
   'channels':[{'wavelength':w,'midpoint_tai_us':f['requested_slot_tai_us']+1000000,
      'contributing_end_tai_us':f['requested_slot_tai_us']+2000000,'end_bound_verified':False,
      'source_record':'fixture','conversion_provenance':'fixture'} for w in m.CHANNELS]}
  with self.assertRaisesRegex(ValueError,'verified contributing'):strict.validate_frame_evidence(r,f,e)
 def test_bad_input_checksum_rejected(self):
  p=self.root/'a';p.write_text('bad')
  with self.assertRaisesRegex(ValueError,'checksum'):m.verify(p,'0'*64)
 def test_symlink_input_rejected(self):
  p=self.root/'a';p.write_text('a');s=self.root/'s';s.symlink_to(p)
  with self.assertRaises(ValueError):m.verify(s,m.sha(p))
 def test_safe_npz_rejects_pickle(self):
  p=self.root/'a.npz';np.savez(p,x=np.asarray([{}],dtype=object))
  with self.assertRaisesRegex(ValueError,'pickle'):base.safe_npz(p,np)
 def test_read_real_synthetic_hdf_attributes(self):
  import h5py
  f=fixture_record()['frames'][0];r=fixture_record();attrs=attrs_for(r,f)
  bio=io.BytesIO()
  with h5py.File(bio,'w') as h:
   for w in m.CHANNELS:
    ds=h.create_dataset('aia'+str(w),shape=(4096,4096),dtype='f4',chunks=(64,64))
    ds.attrs['meta_0']=attrs['source']['content']['channels']['aia'+str(w)]['attributes']['meta_0']
  bio.seek(0);read=source.read_hdf_attributes(bio)
  self.assertEqual(len(read['channels']),6);self.assertEqual(read['channels']['aia94']['shape'],[4096,4096])
 def test_full_four_sequence_real_npz_workflow(self):
  records=[fixture_record(role,label,i+1) for i,(role,label) in enumerate(m.COMBINATIONS)]
  originals={};cs={};files={};evidences={}
  # Create finite, nonconstant real arrays, compressed compactly; frame values differ.
  grid=np.linspace(0,1,512,dtype=np.float32)[None,:,None]
  x=np.broadcast_to(grid,(512,512,6)).copy()
  for r in records:
   for idx,f in enumerate(r['frames']):
    sid=f['history_sample_id'];p=self.root/(sid+'.npz');dt=f['raw_T_REC_TAI'].replace('_TAI','').replace('_',' ').replace('.', '-',2)
    used='s3://nasa-surya-bench/'+sid[:4]+'/'+sid[4:6]+'/'+sid[:13]+'.nc'
    np.savez_compressed(p,x=x*(1-idx*.1),sample_id=sid,HARPNUM=r['HARPNUM'],NOAA_AR_clean=r['NOAA_AR_clean'],T_REC_dt=dt,
       used_s3_path=used,channels=np.asarray(['aia'+str(w) for w in m.CHANNELS]),y=99)
    h=base.file_hashes(p);f['object_bytes']=h['bytes']
    c={'sample_id':sid,'HARPNUM':r['HARPNUM'],'NOAA_AR_clean':r['NOAA_AR_clean'],'raw_T_REC':f['raw_T_REC_TAI'],
       'expected_uri':f['object_uri'],'generation':'123','object_bytes':h['bytes'],'stored_issue_time':dt,'original_label':0,
       'md5Hash':h['md5Hash'],'crc32c':h['crc32c']}
    cs[sid]=c;files[sid]=p;evidences[sid]=attrs_for(r,f)
    hist=copy.deepcopy(r);hist['target_sample_id']=sid;hist['issue_tai_us']=f['requested_slot_tai_us'];hist['issue_raw_TAI']=f['raw_T_REC_TAI'];originals[sid]=hist
  class Client:
   def __init__(self):self.calls=0
   def download(self,c,p):self.calls+=1;Path(p).write_bytes(files[c['sample_id']].read_bytes())
  client=Client();work=self.root/'work';work.mkdir();out=work/'report';out.mkdir()
  read_calls=[]
  def reader(c):read_calls.append(c['sample_id']);return evidences[c['sample_id']]
  before={k:m.sha(v) for k,v in files.items()}
  result=m.batch_from_records(records,cs,base,client,clock,reader,work,out,np)
  self.assertEqual(result['batch_shape'],[4,3,6,512,512]);self.assertEqual(client.calls,12)
  self.assertEqual(np.load(out/'manifest_targets.npy').tolist(),[0,1,0,1])
  self.assertFalse(result['training_authorised']);self.assertFalse(result['strict_contributing_time_clearance']);self.assertEqual(result['test_samples_loaded'],0)
  self.assertEqual(before,{k:m.sha(v) for k,v in files.items()})
  out2=work/'report2';out2.mkdir();m.batch_from_records(records,cs,base,client,clock,reader,work,out2,np)
  self.assertEqual(client.calls,12) # verified cache reuse; no extra simulated transfer
  # Same fixture also exercises sidecar/index join without downloading anything.
  path=self.root/'index.jsonl.gz'
  with gzip.open(path,'wt',encoding='utf8') as h:
   for rr in [*records,*originals.values()]:h.write(json.dumps(rr)+'\n')
  selected=[side(r) for r in records];joined,got=m.join_records(path,selected)
  self.assertEqual(len(joined),4);self.assertEqual(set(got),set(files))
 def test_output_overwrite_rejected(self):
  p=self.root/'report.json';m.save(p,{'a':1})
  with self.assertRaises(FileExistsError):m.save(p,{'a':2})

if __name__=='__main__':unittest.main(verbosity=2)
