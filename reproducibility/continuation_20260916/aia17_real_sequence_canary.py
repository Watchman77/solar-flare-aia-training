#!/usr/bin/env python3
"""17C engineering canary: four real three-frame sequences from a reviewed split.

Uses ONLY train and model_validation (one original-label 0 and 1 each).
Does not rerun earlier audits, change dates, fit a model, or clear full readiness.
Downloads <=12 version-pinned NPZ objects and reads original SuryaBench attributes.
The experimental strict loader is NOT weakened: a mean-exposure end estimate is
NOT a verified latest-contributing-time bound. That gate remains explicit.

Run: ~/aia17_time_venv/bin/python ~/aia17_real_sequence_canary.py
No additional flag; uses completed local run IDs below, no package installation.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import zipfile

VERSION = '17c-real-sequence-engineering-canary-v1'
ROLE_RUN = '20260916T151222233858Z'
INDEX_RUN = '20260916T143622218859Z'
INVENTORY_RUN = '20260916T073559880010Z'
ROLE_REPORT_SHA = '43c69fc3aaf759e32111ddd9fe5f24cf4e3db813c801daf2d4e1d5c7e552d5f6'
ROLE_MARKER_SHA = '35195135fec851072ea729cdafb82d7ddaa1adb161f4209d63f477daa64d998a'
INVENTORY_SHA = '241295bb6cbb3f69ef0e5b9b9d090ef4da7f9dda698361bdd2fdc1d223c238a1'
CHANNELS = (94,131,171,193,211,335)
LAGS = (288,192,96)
COMBINATIONS = (('train',0),('train',1),('model_validation',0),('model_validation',1))
EXPECTED_ROLES = {
 'train':('2010-01-01T00:00:00Z','2014-01-01T00:00:00Z'),
 'model_validation':('2014-01-01T00:00:00Z','2014-07-01T00:00:00Z')}
BUCKET = 'suryabench-sharp-pipeline-bamidele'
ACCOUNT = 'abmoses2000@gmail.com'
PROJECT = 'sonorous-shore-450510-i4'
AVAILABLE = 'NOMINAL_HISTORY_OBJECTS_AVAILABLE_TIMING_PENDING'
BAD_FRAME = '20240714_0724_HARP11520_NOAA13753'
MAX_METADATA = 250*1024**2
MAX_ROWS = 250000
MAX_PAYLOAD = 128*1024**2
RESERVE = 1024**3
BATCH_BYTES = 4*3*6*512*512*4
DEPS = {
 'npz':('aia17_npz_timing_canary.py','878424c0a74f453396bdba616cd1f1bebcc4667e6cff9c92e0f9419f676d3755'),
 'transport':('aia17_npz_timing_canary_gcloud.py','45a6b1a21412fa694c80ff6ab9ccd60f3e697e2560ab88dfb04702c892979e6e'),
 'source':('aia17_consolidated_resolution.py','191a74baa62d089f66d1db28ab2ce7368fc20846b6601ccbf684e8ed675c13a9'),
 'index':('aia17_build_temporal_manifest.py','7175c7361aa64643ae93ec8c645a4de96339bb6af6b3850563146fbd3cf2ce96')}
SID = re.compile(r'(\d{8})_(\d{4})_HARP(\d+)_NOAA(\d+)')

def now(): return datetime.now(timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def regular(p,cap=MAX_METADATA):
 p=Path(p)
 if not p.is_file() or p.is_symlink() or p.stat().st_size>cap:
  raise ValueError(f'Missing, symlinked or oversized input: {p}')
 return p

def verify(p,expected):
 regular(p)
 if not re.fullmatch('[0-9a-f]{64}',str(expected)) or sha(p)!=expected:
  raise ValueError(f'Input checksum mismatch: {p}')
 return expected

def js(p,cap=8*1024**2):
 regular(p,cap);r=json.loads(Path(p).read_text(encoding='utf-8'))
 if not isinstance(r,dict):raise ValueError(f'Expected JSON object: {p}')
 return r

def save(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')

def csv_rows(p):
 opener=gzip.open if str(p).endswith('.gz') else open
 with opener(p,'rt',encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f,strict=True)
  if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError('CSV schema invalid.')
  for i,r in enumerate(reader,1):
   if i>MAX_ROWS or None in r or any(v is None for v in r.values()):raise ValueError('CSV row/count invalid.')
   yield r

def jsonl(p):
 total=0
 with gzip.open(p,'rt',encoding='utf-8') as f:
  for i in range(MAX_ROWS+1):
   line=f.readline(131073)
   if not line:break
   total+=len(line)
   if i==MAX_ROWS or len(line)>131072 or total>1200*1024**2:raise ValueError('Index read limit exceeded.')
   r=json.loads(line)
   if not isinstance(r,dict):raise ValueError('Index record is not an object.')
   yield r

def utc(s):
 if not isinstance(s,str) or not s.endswith('Z'):raise ValueError('Canonical UTC with Z required.')
 return datetime.fromisoformat(s[:-1]+'+00:00')

def import_verified(home):
 out={}
 for key,(name,h) in DEPS.items():
  p=home/name;verify(p,h)
  spec=importlib.util.spec_from_file_location('aia17_sequence_dep_'+key,p)
  m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);out[key]=m
 return out

def review_contract(role_dir,index_dir):
 verify(role_dir/'COMPLETE.json',ROLE_MARKER_SHA)
 marker=js(role_dir/'COMPLETE.json');report=js(role_dir/'cross_cycle_assignment_report.json')
 verify(role_dir/'cross_cycle_assignment_report.json',ROLE_REPORT_SHA)
 if report.get('status')!='CROSS_CYCLE_ROLE_PROPOSAL_BUILT_NOT_FROZEN' or report.get('training_authorised') is not False:
  raise ValueError('Unexpected role proposal status; no implicit migration.')
 if report.get('development_structural_blockers') or report.get('retained_cross_role_pinned_aia_object_overlap')!=0:
  raise ValueError('Reported structural blocker or cross-role object overlap.')
 locks={}
 for name,h in marker['output_sha256'].items():
  if Path(name).name!=name:raise ValueError('Unexpected checkpoint filename.')
  locks[str(role_dir/name)]=verify(role_dir/name,h)
 for name,h in report['source_files_sha256'].items():
  if Path(name).name!=name:raise ValueError('Unexpected source filename.')
  locks[str(index_dir/name)]=verify(index_dir/name,h)
 for role,(lo,hi) in EXPECTED_ROLES.items():
  r=[r for r in report['proposed_roles'] if r['name']==role]
  if len(r)!=1 or (r[0]['start_utc_inclusive'],r[0]['end_utc_exclusive'])!=(lo,hi):
   raise ValueError('Reviewed development dates changed.')
 return report,locks

def select_examples(sidecar,expected_rows):
 """One of each class per debugging role, stable hash rank, four distinct components."""
 pool={k:[] for k in COMBINATIONS};seen=set();counts=Counter()
 for r in csv_rows(sidecar):
  sid=r['target_sample_id']
  if sid in seen or not SID.fullmatch(sid):raise ValueError('Duplicate/invalid role ID.')
  seen.add(sid);counts[r['proposed_role']]+=1
  if r['role_constraints_pass'] not in ('0','1') or r['original_label_48h_final'] not in ('0','1'):
   raise ValueError('Nonbinary preserved role/label.')
  key=(r['proposed_role'],int(r['original_label_48h_final']))
  if key not in pool or r['role_constraints_pass']!='1':continue
  if r['nominal_history_complete']!='1' or r['structural_exclusion_reasons']:
   raise ValueError('Retained role contradicts its structural flags.')
  if r['training_authorised'] not in ('False','false','0'):raise ValueError('Unexpected training flag.')
  lo,hi=EXPECTED_ROLES[key[0]]
  if not utc(lo)<=utc(r['issue_utc'])<utc(hi):raise ValueError('Role/date disagreement.')
  rank=hashlib.sha256((VERSION+'|'+sid).encode()).hexdigest()
  pool[key].append((rank,r))
 if len(seen)!=expected_rows:raise ValueError('Sidecar count differs from completed proposal.')
 selected=[];components=set()
 for key in COMBINATIONS:
  candidates=[r for _,r in sorted(pool[key],key=lambda item:item[0]) if r['region_component_id'] not in components]
  if not candidates:raise ValueError(f'No separate retained region component for {key}; no fallback to test.')
  r=candidates[0];components.add(r['region_component_id']);selected.append(r)
 return selected,dict(counts)

def join_records(index_path,selected):
 wanted={r['target_sample_id']:r for r in selected};found={}
 for r in jsonl(index_path):
  sid=r['target_sample_id']
  if sid in wanted:
   if sid in found:raise ValueError('Repeated selected target in index.')
   role=wanted[sid]
   if (r['issue_utc']!=role['issue_utc'] or r['original_label_48h_final']!=int(role['original_label_48h_final'])
       or r['history_status']!=AVAILABLE or r['label_boundary_review_required'] or r['training_authorised'] is not False):
    raise ValueError('Selected target differs from locked sidecar or has unresolved boundary flag.')
   if tuple(f['lag_minutes'] for f in r['frames'])!=LAGS:raise ValueError('Wrong sequence order.')
   if len({f['history_sample_id'] for f in r['frames']})!=3:raise ValueError('Repeated frame padding forbidden.')
   for f in r['frames']:
    m=SID.fullmatch(str(f['history_sample_id']))
    if (not m or (int(m[3]),int(m[4]))!=(r['HARPNUM'],r['NOAA_AR_clean']) or not f['nominal_candidate']
        or f['history_sample_id']==BAD_FRAME or f['object_status']!='EXACT_NONEMPTY_OBJECT'
        or f['requested_slot_tai_us']!=r['issue_tai_us']-f['lag_minutes']*60000000):
     raise ValueError('Historical slot, object or region mismatch.')
    if not utc(EXPECTED_ROLES[role['proposed_role']][0])<=utc(f['record_utc'])<utc(r['issue_utc']):
     raise ValueError('History crosses development-role boundary.')
   r=dict(r);r['canary_role']=role['proposed_role'];r['region_component_id']=role['region_component_id'];found[sid]=r
 if set(found)!=set(wanted):raise ValueError('Selected targets missing from index.')
 frames={f['history_sample_id']:f for r in found.values() for f in r['frames']}
 originals={}
 for r in jsonl(index_path):
  sid=r['target_sample_id']
  if sid in frames:
   if sid in originals:raise ValueError('Duplicate history source.')
   originals[sid]=r
 if set(originals)!=set(frames):raise ValueError('A historical source lacks manifest lineage.')
 output=[found[r['target_sample_id']] for r in selected]
 for record in output:
  for f in record['frames']:
   src=originals[f['history_sample_id']]
   if src['issue_raw_TAI']!=f['raw_T_REC_TAI'] or src['issue_tai_us']!=f['requested_slot_tai_us']:
    raise ValueError('Historical raw TAI lineage mismatch.')
 return output,originals

def inventory_candidates(records,originals,inventory_root,base):
 report_path=inventory_root/'reports'/INVENTORY_RUN/'archive_reconciliation_report.json'
 verify(report_path,INVENTORY_SHA);report=js(report_path)
 frame_map={f['history_sample_id']:f for r in records for f in r['frames']};objects={};locks={str(report_path):INVENTORY_SHA}
 receipts={int(x['year']):x for x in report['listing_receipts']}
 years=sorted({int(sid[:4]) for sid in frame_map})
 if any(y>=2015 for y in years):raise ValueError('Canary must not load calibration, threshold, or test image years.')
 for y in years:
  p=inventory_root/'listings'/f'objects_{y}.json';locks[str(p)]=verify(p,receipts[y]['sha256'])
  vals=json.loads(p.read_text());byname={v['name']:v for v in vals}
  if len(byname)!=len(vals):raise ValueError('Repeated object name.')
  for sid,f in frame_map.items():
   if int(sid[:4])!=y:continue
   uri=f'gs://{BUCKET}/samples_npz/{y}/{sid}.npz'
   if uri!=f['object_uri']:raise ValueError('Unexpected history URI.')
   name=uri.split(f'gs://{BUCKET}/',1)[1];o=byname[name];src=originals[sid]
   if str(o['generation'])!=f['object_generation'] or int(o['size'])!=f['object_bytes']:raise ValueError('Frame/listing version conflict.')
   raw=src['issue_raw_TAI'];m=re.fullmatch(r'(\d{4})\.(\d{2})\.(\d{2})_(\d{2}:\d{2}:\d{2}(?:\.\d+)?)_TAI',raw)
   if not m:raise ValueError('Explicit TAI lineage required.')
   c={'sample_id':sid,'stored_year':y,'original_label':src['original_label_48h_final'],
      'HARPNUM':src['HARPNUM'],'NOAA_AR_clean':src['NOAA_AR_clean'],
      'stored_issue_time':f'{m[1]}-{m[2]}-{m[3]} {m[4]}','raw_T_REC':raw,
      'expected_uri':uri,'name':name,'generation':str(o['generation']),
      'object_bytes':int(o['size']),'object_status':'EXACT_NONEMPTY_OBJECT',
      'crc32c':o.get('crc32c',''),'md5Hash':o.get('md5Hash','')}
   if not c['crc32c'] and not c['md5Hash']:raise ValueError('No locked checksum.')
   objects[sid]=c
 if not 1<=len(objects)<=12:raise ValueError('Canary object cap exceeded.')
 total=base.validate_candidates(list(objects.values()),len(objects))
 return objects,total,locks

def header_time(value,meta,clock):
 """FITS UTC default only within identified preserved AIA meta_0, not arbitrary CSV."""
 s=str(value).strip();declared=str(meta.get('timesys','')).upper().strip();scale=None;basis=''
 for suff,sc in (('_TAI','tai'),('_UTC','utc'),('Z','utc'),('+00:00','utc')):
  if s.endswith(suff):s=s[:-len(suff)];scale=sc;basis='explicit_suffix';break
 if declared and declared not in ('UTC','TAI'):raise ValueError('Unsupported original TIMESYS.')
 if scale and declared and scale!=declared.lower():raise ValueError('Conflicting explicit time scale.')
 if scale is None and declared:scale=declared.lower();basis='original_TIMESYS'
 if scale is None:
  if str(meta.get('telescop','')).upper()!='SDO/AIA' or not str(meta.get('instrume','')).upper().startswith('AIA'):
   raise ValueError('UTC default requires identified preserved AIA FITS metadata.')
  scale='utc';basis='FITS_4_default_UTC_for_preserved_AIA_meta0_no_TIMESYS'
 s=re.sub(r'^(\d{4})\.(\d{2})\.(\d{2})_',r'\1-\2-\3T',s).replace(' ','T')
 if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?',s):raise ValueError('Unsupported header timestamp.')
 return clock.ticks([s],scale)[0],basis

def source_time_screen(record,frame,evidence,clock):
 src=evidence['source'];channels=src['content']['channels'];out=[]
 for w in CHANNELS:
  channel=channels.get(f'aia{w}',{})
  if channel.get('status')!='ATTRIBUTES_READ_NO_PIXELS':raise ValueError(f'Missing source attributes for {w}.')
  raw=channel.get('attributes',{}).get('meta_0')
  m=json.loads(raw) if isinstance(raw,str) else raw
  if not isinstance(m,dict):raise ValueError('Original meta_0 required; no processed-exposure fallback.')
  m={str(k).lower():v for k,v in m.items()}
  if int(m.get('wavelnth',-1))!=w or int(m.get('quality',-1))!=0:raise ValueError('Source wavelength/quality check failed.')
  mid,basis=header_time(m['t_obs'],m,clock)
  rec_time,_=header_time(m['t_rec'],m,clock)
  starts=[k for k in ('date-obs','date_obs','date__obs') if k in m]
  if not starts:raise ValueError('Original observation start missing.')
  start_values=[header_time(m[k],m,clock)[0] for k in starts]
  if max(start_values)-min(start_values)>1000:raise ValueError('Conflicting start-time headers.')
  start=start_values[0];exposure=float(m['exptime'])
  if not math.isfinite(exposure) or not 0<exposure<120:raise ValueError('Unsupported original exposure duration.')
  half=int(round(exposure*500000));estimated_end=start+int(round(exposure*1000000))
  consistent=abs(mid-start-half)<=20000 # preserves documented 0.02-second metadata-consistency check
  passed=(consistent and abs(mid-frame['requested_slot_tai_us'])<=180000000
          and abs(rec_time-frame['requested_slot_tai_us'])<=180000000
          and start<=mid<=estimated_end and estimated_end<=record['issue_tai_us'])
  out.append({'wavelength':w,'source_nominal_utc':clock.utc_text([rec_time])[0],
    'midpoint_utc':clock.utc_text([mid])[0],'original_start_utc':clock.utc_text([start])[0],
    'original_mean_exposure_seconds':exposure,'estimated_mean_exposure_end_utc':clock.utc_text([estimated_end])[0],
    'midpoint_minus_historical_slot_seconds':(mid-frame['requested_slot_tai_us'])/1e6,
    'estimated_end_minus_forecast_issue_seconds':(estimated_end-record['issue_tai_us'])/1e6,
    'header_time_scale_basis':basis,'start_midpoint_exposure_consistent':consistent,
    'recorded_time_screen_pass':passed,'contributing_end_bound_verified':False,
    'historical_product_availability_verified':False,
    'note':'Mean exposure end is a diagnostic estimate, NOT a bound on latest contributing pixel/product time.'})
 return {'history_sample_id':frame['history_sample_id'],'source_url':src['url'],
   'all_recorded_time_screens_pass':all(x['recorded_time_screen_pass'] for x in out),'channels':out,
   'strict_contributing_time_clearance':False,'original_source_identity_tied_by_npz_path_not_pixel_reproduction':True}

def load_engineering_frame(path,c,base,np):
 arrays,desc=base.safe_npz(path,np)
 meta={k:base.scalar(arrays[k]) for k in ('sample_id','HARPNUM','NOAA_AR_clean','T_REC_dt','used_s3_path') if k in arrays}
 expected={'sample_id':c['sample_id'],'HARPNUM':c['HARPNUM'],'NOAA_AR_clean':c['NOAA_AR_clean'],'T_REC_dt':c['stored_issue_time']}
 if any(str(meta.get(k))!=str(v) for k,v in expected.items()):raise ValueError('NPZ sample/region/clock mismatch.')
 declarations=[base.parse_channels(arrays[k]) for k in ('channels','wavelengths') if k in arrays]
 if not declarations or any(v!=list(CHANNELS) for v in declarations):raise ValueError('Wrong channel set/order.')
 x=arrays.get('x')
 if x is None or x.shape!=(512,512,6) or x.dtype!=np.dtype('float32') or not np.isfinite(x).all():
  raise ValueError('Expected finite float32 512x512x6 tensor.')
 if any(float(x[:,:,i].std())==0 for i in range(6)):raise ValueError('Constant image channel requires review.')
 src=str(meta.get('used_s3_path',''));match=re.fullmatch(r's3://nasa-surya-bench/(\d{4})/(\d{2})/(\d{8})_(\d{4})\.nc',src)
 if not match or match[1]!=match[3][:4] or match[2]!=match[3][4:6]:raise ValueError('Unsupported original source URI.')
 embedded={k:base.scalar(arrays[k]) for k in ('y','label_48h_final') if k in arrays}
 # Embedded labels are diagnostic only. The target is supplied by the sequence target record, not a historical frame.
 return np.transpose(x,(2,0,1)).copy(),meta,{'members':desc,'historical_frame_embedded_labels':embedded,
           'historical_frame_manifest_label':c['original_label'],'embedded_labels_used_as_sequence_target':False}

def batch_from_records(records,objects,base,client,clock,source_reader,work,out,np):
 cache=work/'objects';cache.mkdir(parents=True,exist_ok=True)
 frame_arrays={};frame_reports={};sequence_reports=[];sample_arrays=[]
 for seq in records:
  print(f"Sequence {seq['canary_role']} / label {seq['original_label_48h_final']}: {seq['target_sample_id']}",flush=True)
  timings=[]
  for frame in seq['frames']:
   sid=frame['history_sample_id'];c=objects[sid]
   if sid not in frame_arrays:
    print(f"  Historical slot t-{frame['lag_minutes']} min: {sid}",flush=True)
    old_cache=work.parent/'npz_timing_canary_v1/objects'
    cache_key=hashlib.sha256((c['expected_uri']+'#'+c['generation']).encode()).hexdigest()
    chosen_cache=old_cache if (old_cache/(cache_key+'.receipt.json')).is_file() else cache
    path,receipt=base.obtain(c,chosen_cache,client)
    x,meta,content=load_engineering_frame(path,c,base,np)
    # Source attributes follow the exact path INSIDE the downloaded historical frame.
    evidence=source_reader({'metadata':meta,'raw_T_REC':c['raw_T_REC'],'sample_id':sid})
    frame_arrays[sid]=x;frame_reports[sid]={'object':c,'receipt':receipt,'content':content,'source_metadata':evidence}
    save(out/(sid+'_frame.json'),frame_reports[sid])
   ev=frame_reports[sid]['source_metadata']
   t=source_time_screen(seq,frame,ev,clock);timings.append(t)
   if not t['all_recorded_time_screens_pass']:
    save(out/(seq['target_sample_id']+'_timing_failure.json'),{'target':seq['target_sample_id'],'timing':timings})
    raise ValueError('Recorded source times fail this historical-slot/issue screen; no substitute sample chosen.')
  x=np.stack([frame_arrays[f['history_sample_id']] for f in seq['frames']])
  if x.shape!=(3,6,512,512):raise ValueError('Sequence tensor axes incorrect.')
  sample_arrays.append(x)
  sequence_reports.append({'target_sample_id':seq['target_sample_id'],'role':seq['canary_role'],
    'region_component_id':seq['region_component_id'],'target_from_manifest':seq['original_label_48h_final'],
    'issue_utc':seq['issue_utc'],'shape':list(x.shape),'lags_minutes':list(LAGS),'timing':timings,
    'training_authorised':False,'strict_contributing_time_clearance':False})
  print('  Real sequence loaded: (3, 6, 512, 512); recorded-time screen passed; strict bound remains unverified.',flush=True)
 batch=np.stack(sample_arrays)
 labels=np.asarray([r['original_label_48h_final'] for r in records],dtype=np.int64)
 if batch.shape!=(4,3,6,512,512) or labels.tolist()!=[0,1,0,1]:raise ValueError('Engineering batch order/shape mismatch.')
 # Serialize an explicitly named ENGINEERING artifact. It is not an approved training dataset.
 with (out/'engineering_batch.npy').open('xb') as f:np.save(f,batch,allow_pickle=False)
 with (out/'manifest_targets.npy').open('xb') as f:np.save(f,labels,allow_pickle=False)
 return {'sequence_results':sequence_reports,'unique_frames':len(frame_reports),'batch_shape':list(batch.shape),
    'batch_dtype':str(batch.dtype),'manifest_targets':labels.tolist(),
    'recorded_time_screens_pass':True,'strict_contributing_time_clearance':False,
    'historical_product_availability_verified':False,'label_validity_and_followup_certified':False,
    'model_training_performed':False,'training_authorised':False,'test_samples_loaded':0}

def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,default=Path.home()/'aia17_metadata_stage1')
 args=ap.parse_args(argv);base_dir=args.base.expanduser().resolve();home=Path.home();out=None
 print('===== 17C REAL THREE-FRAME ENGINEERING CANARY =====',flush=True)
 print('Four train/validation sequences only. No model fitting, date changes, test loading or full-readiness claim.',flush=True)
 try:
  import numpy as np
  import h5py
  deps=import_verified(home);base=deps['npz'];source=deps['source'];transport=deps['transport']
  clock,raw_tai,selftests=base.load_clock(home/'solar_flare_aia')
  print('Existing astronomy conversion self-tests passed.',flush=True)
  role_dir=base_dir/'cross_cycle_role_proposal_v1/reports'/ROLE_RUN
  index_dir=base_dir/'temporal_manifest_v1/reports'/INDEX_RUN
  report,locks=review_contract(role_dir,index_dir)
  selected,role_counts=select_examples(role_dir/'cross_cycle_role_assignments.csv.gz',report['target_rows_preserved'])
  if role_counts!={r['role']:r['targets'] for r in report['role_support']}:raise ValueError('Role row counts differ from report.')
  records,originals=join_records(index_dir/'temporal_sequence_candidates.jsonl.gz',selected)
  objects,total,extra=inventory_candidates(records,originals,base_dir/'archive_reconciliation_v1',base);locks.update(extra)
  work=base_dir/'real_sequence_canary_v1'
  repo=(home/'solar_flare_aia').resolve()
  if work==repo or repo in work.parents:raise ValueError('Canary artifacts must remain outside Git.')
  work.mkdir(parents=True,exist_ok=True)
  if shutil.disk_usage(work).free<RESERVE+total+BATCH_BYTES+32*1024**2:raise ValueError('Need payload/batch bytes plus 1 GiB reserve.')
  # OS advisory lock releases on process exit, including failed transfers. Never remove others' cache files.
  import fcntl
  with (work/'.run.lock').open('a') as lf:
   fcntl.flock(lf,fcntl.LOCK_EX|fcntl.LOCK_NB)
   stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');out=work/'reports'/stamp;out.mkdir(parents=True,exist_ok=False)
   plan={'version':VERSION,'role_proposal_used_without_freezing':True,'input_sha256':locks,
         'selected_targets':records,'object_count':len(objects),'planned_npz_bytes':total,
         'max_npz_bytes':MAX_PAYLOAD,'selection':'fixed hash rank, original-label strata, distinct region components',
         'calibration_threshold_diagnostic_and_test_targets_not_selected':True,'training_authorised':False}
   save(out/'canary_plan.json',plan)
   print(f'Selected four sequences / {len(objects)} unique history files; planned NPZ payload {total/1024**2:.2f} MiB.',flush=True)
   # Set credentials only for copy child processes; never display tokens or alter persistent gcloud config.
   original_env=transport.private_env
   def explicit_env(trackers):
    env=original_env(trackers);env['CLOUDSDK_CORE_ACCOUNT']=ACCOUNT;env['CLOUDSDK_CORE_PROJECT']=PROJECT;return env
   transport.private_env=explicit_env
   client=transport.GcloudDownloadClient(base,work/'transport')
   budget=source.Budget(minutes=30)
   def source_reader(candidate):
    # Reuse the already successful remote metadata transport and cache. No JSOC calls.
    return source.s3_attributes(candidate,base_dir/'consolidated_resolution_v1/s3_metadata_cache',budget)
   result=batch_from_records(records,objects,base,client,clock,source_reader,work,out,np)
   result.update(version=VERSION,status='REAL_SEQUENCE_ENGINEERING_CANARY_COMPLETE_FULL_CLEARANCE_PENDING',
        created_utc=now(),clock_selftests=selftests,split_dates_changed=False,split_dates_frozen=False,
        source_labels_changed=False,cloud_writes=False,git_operations=False,
        versions={'numpy':np.__version__,'h5py':h5py.__version__},dependencies=DEPS,
        distinction='Header-based exposure-end estimates are not verified latest-contributing-time or product-availability bounds. The strict loader is unchanged.')
   save(out/'real_sequence_canary_report.json',result)
   note=['# 17C real-sequence engineering canary','',
      'Four three-frame sequences from train/model_validation only. No independent-test image is selected.',
      'The role proposal is reused unchanged; this run neither freezes scientific readiness nor fits a model.',
      '',f"Batch shape: {result['batch_shape']}; dtype: {result['batch_dtype']}.",
      'Target labels: designated target manifest, never historical NPZ y.',
      'Source-time screening uses retained original AIA FITS meta_0; original mean exposure duration is used.',
      '**Mean-exposure end estimates are NOT certified latest-contributing-time bounds.**',
      'Strict contributing-time, product availability, SHARP, label lineage/follow-up and final readiness remain separate gates.',
      'Existing strict selection/loader functions are unmodified. No experimental results are generated here.',
      '', 'The engineering_batch.npy is local debugging data, not an approved training release.']
   (out/'research_log_real_sequence_canary.md').write_text('\n'.join(note)+'\n',encoding='utf-8')
   files=[p for p in out.iterdir() if p.is_file()]
   save(out/'COMPLETE.json',{'status':result['status'],'output_sha256':{p.name:sha(p) for p in files}})
   package=out/'real_sequence_canary_summary.zip'
   with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(out.iterdir()):
     if p.suffix in ('.json','.md'):z.write(p,p.name)
   print('\n===== REAL SEQUENCE LOADER RESULTS =====',flush=True)
   print('Sequences loaded: 4 | unique image files:',result['unique_frames'])
   print('Batch shape:',result['batch_shape'],'| manifest labels:',result['manifest_targets'])
   print('Train/validation only. Test samples loaded: 0.')
   print('Recorded source-time screens passed. Strict contributing-time bound: UNVERIFIED (not silently waived).')
   print('STATUS:',result['status']);print('REPORT:',out/'real_sequence_canary_report.json')
   print('SEND THIS SMALL FILE:',package)
   print('No full-archive rerun, original label changes, source writes, model fitting or Git operations.')
  return 0
 except Exception as exc:
  if out is not None:
   try:save(out/'FAILED.json',{'version':VERSION,'error':str(exc)[:3000],'training_authorised':False,
       'note':'No automatic replacement target or test-set fallback. Verified caches retained.'})
   except Exception:pass
  print('\nSTOP:',exc,flush=True)
  print('No source repairs or training. Completed downloads remain cached; do not rerun earlier audits.',flush=True)
  return 1

if __name__=='__main__':raise SystemExit(main())
