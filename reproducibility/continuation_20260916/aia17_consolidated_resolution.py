#!/usr/bin/env python3
"""One bounded 17B evidence batch; never rewrites data, labels, Git or cloud objects.

1. Reuse the completed canary and locked local master/baseline manifests.
2. Read 13 named original manifest/log CSVs for the four disputed years.
3. Read attributes (not pixel arrays) of the 16 named SuryaBench NetCDFs,
   using capped, ETag-conditional HTTP ranges.
4. Query twelve base-series JSOC records (metadata only, no export jobs).
5. Produce a single evidence/decision package. Unavailable evidence stays unresolved.

Requires the existing NumPy/Astropy environment plus h5py==3.14.0.
Defaults match the recorded Cloud Shell workspace. External reads are ON by default.
--local-only disables external reads; it cannot clear observation-time provenance.
"""
from __future__ import annotations
import argparse, base64, csv, hashlib, io, json, math, os, re, shutil
import signal, subprocess, sys, time, zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote, urlencode

VERSION = 'aia17-consolidated-evidence-v1'
PROJECT = 'sonorous-shore-450510-i4'
ACCOUNT = 'abmoses2000@gmail.com'
BUCKET = 'suryabench-sharp-pipeline-bamidele'
CANARY_RUN = '20260916T102919362266Z'
SNAPSHOT = 'docs/research_audit/2026-09-15'
CHANNELS = [94, 131, 171, 193, 211, 335]
BOUNDARY = '20240714_0724_HARP11520_NOAA13753'
SID = re.compile(r'\d{8}_\d{4}_HARP\d+_NOAA\d+')
MAX_CSV = 20 * 1024**2
MAX_GCS_TOTAL = 96 * 1024**2  # Logical selected CSV bytes, not a monetary cap.
MAX_JSON = 8 * 1024**2
BLOCK = 32 * 1024
RANGE_CAP = 2 * 1024**2      # Returned range bytes PER SOURCE, retries included.
REQUEST_CAP = 96             # Attempts PER SOURCE, including HEAD.
OBS_FIELDS = {'t_obs','date-obs','date_obs','date-beg','date-end','t_rec',
              'timesys','exptime','quality','wavelnth','wavelength','data_time'}

def now(): return datetime.now(timezone.utc).isoformat()
def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''): h.update(b)
    return h.hexdigest()
def read_json(p, cap=MAX_JSON):
    p = Path(p)
    if not p.is_file() or p.stat().st_size > cap: raise ValueError(f'Missing/oversized JSON: {p}')
    x = json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(x, dict): raise ValueError(f'Expected JSON object: {p}')
    return x

def save(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists(): raise ValueError(f'Refusing overwrite: {p}')
    with p.open('x', encoding='utf-8') as f: json.dump(obj, f, indent=2, allow_nan=False); f.write('\n')

def verify(p, expected):
    if not re.fullmatch('[0-9a-f]{64}', expected or '') or digest(p) != expected:
        raise ValueError(f'Checksum mismatch: {p}')

class Budget:
    def __init__(self, minutes=20): self.end = time.monotonic() + minutes*60
    def left(self, cap=60):
        remaining = self.end-time.monotonic()
        if remaining <= 0: raise TimeoutError('Batch time budget exhausted; outstanding sources remain unresolved.')
        return max(0.1, min(cap, remaining))

def clean(x):
    if isinstance(x, bytes): return x.decode('utf-8', errors='replace')
    if isinstance(x, dict): return {str(k): clean(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [clean(v) for v in x]
    if hasattr(x,'tolist'): return clean(x.tolist())
    if isinstance(x,float) and not math.isfinite(x): return str(x)
    if isinstance(x,(str,int,float,bool)) or x is None: return x
    return str(x)

def pick_csv(path, ids):
    """Keep ALL matching records; do not silently deduplicate or repair identifiers."""
    found = {s: [] for s in ids}; total = 0
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)): raise ValueError(f'Duplicate header: {path}')
        idcols = [c for c in ('sample_id','file','gcp_path','local_path') if c in fields]
        for n,r in enumerate(reader, 1):
            total += 1
            if None in r or any(v is None for v in r.values()): raise ValueError(f'Malformed CSV {path}:{n}')
            matches = set()
            for c in idcols:
                matches.update(s for s in SID.findall(r[c] or '') if s in found)
            for s in matches:
                if len(found[s]) >= 50: raise ValueError(f'Too many matching records for {s}: {path}')
                found[s].append({'record_number': n, 'raw': r})
    return {'path': str(path), 'rows':total, 'fields':fields, 'matches':found,
            'identity_columns':idcols, 'sha256':digest(path)}

def binary(x):
    return {'0':0,'0.0':0,'1':1,'1.0':1}.get(str(x).strip())

def label_findings(canary, scans):
    result=[]
    for c in canary['results']:
        mismatch = any(not z.get('matches_original_manifest_label',False)
                       for z in c.get('embedded_label_comparisons',{}).values())
        if not mismatch: continue
        sources=[]; old_confirmed=False; manifest_conflict=False
        for name,scan in scans.items():
            rs=scan.get('matches',{}).get(c['sample_id'],[])
            # Multiple matches need review; no first-row selection.
            if len(rs)>1: manifest_conflict=True
            for record in rs:
                r=record['raw']; vals={k:r.get(k) for k in (
                    'label_48h_global_old','label_48h_ar_specific','label_48h_final',
                    'manifest_label_before_repair','y','label_48h') if k in r}
                sources.append({'source':name,'record_number':record['record_number'],'values':vals})
                final=binary(r.get('label_48h_final'))
                old=binary(r.get('label_48h_global_old'))
                if final is not None and final!=c['original_label']: manifest_conflict=True
                if len(rs)==1 and old==binary(c['metadata'].get('y')) and final==c['original_label'] and old!=final:
                    old_confirmed=True
        status=('MANIFEST_CONFLICT_REVIEW' if manifest_conflict else
                'LEGACY_GLOBAL_LABEL_MATCH_CONFIRMED_FOR_THIS_SAMPLE' if old_confirmed else
                'LEGACY_LABEL_EXPLANATION_NOT_YET_CONFIRMED_FOR_THIS_SAMPLE')
        result.append({'sample_id':c['sample_id'],'embedded_y':c['metadata'].get('y'),
                       'original_manifest_label':c['original_label'],'status':status,'evidence':sources})
    return result

def gcloud_env():
    env=os.environ.copy(); env.update({
        'CLOUDSDK_CORE_ACCOUNT':ACCOUNT,'CLOUDSDK_CORE_PROJECT':PROJECT,
        'CLOUDSDK_CORE_DISABLE_PROMPTS':'true','CLOUDSDK_CORE_LOG_HTTP':'false',
        'CLOUDSDK_CORE_DISABLE_FILE_LOGGING':'true','CLOUDSDK_STORAGE_MAX_RETRIES':'2',
        'CLOUDSDK_STORAGE_PROCESS_COUNT':'1','CLOUDSDK_STORAGE_THREAD_COUNT':'1',
        'CLOUDSDK_STORAGE_CHECK_HASHES':'always','CLOUDSDK_STORAGE_SLICED_OBJECT_DOWNLOAD_THRESHOLD':'0',
        'CLOUDSDK_STORAGE_RESUMABLE_THRESHOLD':'1','CLOUDSDK_STORAGE_DOWNLOAD_CHUNK_SIZE':str(1024**2),
        'CLOUDSDK_COMPONENT_MANAGER_DISABLE_UPDATE_CHECK':'true'})
    return env

class CloudCSVs:
    def __init__(self, root, budget):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.budget=budget;self.selected_bytes=0
    def get(self, rel):
        if not re.fullmatch(r'manifests/(2013|2014|2015|2024)/[A-Za-z0-9_]+\.csv',rel):
            raise ValueError('CSV source outside exact allowlisted manifest locations.')
        uri=f'gs://{BUCKET}/{rel}'; d=self.root/hashlib.sha256(uri.encode()).hexdigest()[:24]
        d.mkdir(exist_ok=True); meta_path=d/'object.json'; dest=d/'source.csv'; rec=d/'receipt.json'
        if meta_path.exists(): meta=read_json(meta_path)
        else:
            p=subprocess.run(['gcloud','storage','objects','describe',uri,'--raw','--format=json',
                              f'--project={PROJECT}',f'--account={ACCOUNT}'],
                             capture_output=True,env=gcloud_env(),timeout=self.budget.left(40))
            if p.returncode: raise RuntimeError(p.stderr.decode(errors='replace')[-1500:])
            if len(p.stdout)>MAX_JSON: raise ValueError('Object metadata response too large.')
            meta=json.loads(p.stdout)
            if meta.get('bucket')!=BUCKET or meta.get('name')!=rel: raise ValueError('Object identity mismatch.')
            if meta.get('contentEncoding') not in (None,'','identity'): raise ValueError('Unexpected content encoding.')
            save(meta_path,meta)
        size=int(meta['size']); gen=str(meta['generation'])
        if size<=0 or size>MAX_CSV: raise ValueError(f'CSV size outside 1..20 MiB: {size}')
        if self.selected_bytes+size>MAX_GCS_TOTAL: raise ValueError('96 MiB selected-manifest budget reached.')
        self.selected_bytes+=size
        if rec.exists():
            receipt=read_json(rec)
            if receipt['uri']!=uri or receipt['generation']!=gen: raise ValueError('Cache identity mismatch.')
            verify(dest,receipt['sha256'])
            if dest.stat().st_size!=size: raise ValueError('Cached CSV size mismatch.')
            return dest,receipt
        # Incomplete native downloads are retained. No unverified file is accepted.
        log=d/('copy_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.log')
        if not dest.exists():
            print(f'    Downloading manifest/log only: {size/1024**2:.2f} MiB',flush=True)
            with log.open('xb') as fh:
                os.chmod(log,0o600)
                p=subprocess.Popen(['gcloud','storage','cp',uri+'#'+gen,str(dest),'--do-not-decompress','--quiet',
                                    f'--project={PROJECT}',f'--account={ACCOUNT}'],
                                   stdin=subprocess.DEVNULL,stdout=fh,stderr=subprocess.STDOUT,
                                   env=gcloud_env(),start_new_session=True)
                try:
                    p.wait(timeout=self.budget.left(240))
                except BaseException:
                    # Terminate only the transfer group started by this script.
                    try: os.killpg(p.pid,signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: p.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        try: os.killpg(p.pid,signal.SIGKILL)
                        except ProcessLookupError: pass
                        p.wait()
                    raise
            if p.returncode: raise RuntimeError(log.read_text(errors='replace')[-1500:])
        if dest.stat().st_size!=size: raise ValueError('Incomplete CSV remains in cache; size check failed.')
        if not meta.get('md5Hash'): raise ValueError('No MD5 supplied for whole CSV validation; no scan accepted.')
        h=hashlib.md5()
        with dest.open('rb') as f:
            for b in iter(lambda:f.read(1024**2),b''):h.update(b)
        if base64.b64encode(h.digest()).decode()!=meta['md5Hash']: raise ValueError('CSV MD5 mismatch; no scan accepted.')
        receipt={'uri':uri,'generation':gen,'bytes':size,'sha256':digest(dest),'retrieved_utc':now()}
        save(rec,receipt);return dest,receipt

class RemoteHDF(io.RawIOBase):
    """Read-only bounded HTTP-range file; HDF datasets are NEVER indexed by caller."""
    def __init__(self,url,root,budget,opener=urlopen):
        self.url=url;self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.budget=budget;self.opener=opener;self.pos=0;self.bytes_read=0;self.requests=0;self.blocks={}
        self.start=time.monotonic();self.receipts=[]
        p=self.root/'remote_identity.json'
        if p.exists():
            meta=read_json(p)
            if meta['url']!=url:raise ValueError('Remote cache URL changed.')
        else:
            self._request_limit()
            with opener(Request(url,method='HEAD',headers={'Accept-Encoding':'identity'}),timeout=budget.left(20)) as r:
                if r.status!=200:raise ValueError('Unexpected HEAD status.')
                meta={'url':url,'size':int(r.headers['Content-Length']), 'etag':r.headers.get('ETag'),
                      'last_modified':r.headers.get('Last-Modified'),'observed_utc':now()}
            if not meta['etag'] or str(meta['etag']).startswith('W/'):raise ValueError('Strong ETag required for range consistency.')
            save(p,meta)
        self.meta=meta;self.size=meta['size'];self.etag=meta['etag']
        if self.size<=0:raise ValueError('Empty remote file.')
    def _request_limit(self):
        if self.requests>=REQUEST_CAP or time.monotonic()-self.start>100:
            raise TimeoutError('Per-source range request/time cap reached.')
        self.requests+=1;self.budget.left()
    def readable(self):return True
    def writable(self):return False
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        new=offset+(self.pos if whence==1 else self.size if whence==2 else 0)
        if whence not in (0,1,2) or new<0:raise ValueError('Invalid read-only seek.')
        self.pos=new;return new
    def write(self,*a):raise io.UnsupportedOperation('Read only')
    def truncate(self,*a):raise io.UnsupportedOperation('Read only')
    def flush(self):return None
    def _block(self,start):
        if start in self.blocks:return self.blocks[start]
        end=min(start+BLOCK,self.size)-1; p=self.root/f'{start}_{end}.bin'; j=p.with_suffix('.json')
        if j.exists():
            receipt=read_json(j);verify(p,receipt['sha256'])
            if receipt['etag']!=self.etag or receipt['start']!=start or receipt['end']!=end:raise ValueError('Range-cache identity changed.')
            data=p.read_bytes()
            if len(data)!=end-start+1:raise ValueError('Cached range length mismatch.')
        else:
            if p.exists():raise ValueError('Unreceipted range block exists; not overwritten.')
            self._request_limit()
            needed=end-start+1
            if self.bytes_read+needed>RANGE_CAP:raise ValueError('2 MiB range-byte limit reached for source.')
            headers={'Range':f'bytes={start}-{end}','If-Match':self.etag,'Accept-Encoding':'identity'}
            with self.opener(Request(self.url,headers=headers),timeout=self.budget.left(20)) as r:
                if r.status!=206:raise ValueError('Server did not honor Range; refused full download.')
                if r.headers.get('Content-Range')!=f'bytes {start}-{end}/{self.size}':raise ValueError('Incorrect Content-Range.')
                if r.headers.get('ETag')!=self.etag:raise ValueError('Remote ETag changed.')
                data=r.read(needed+1);self.bytes_read+=len(data)
            if len(data)!=needed:raise ValueError('Short/oversized range response.')
            with p.open('xb') as f:f.write(data)
            receipt={'start':start,'end':end,'etag':self.etag,'sha256':digest(p),'read_utc':now()}
            save(j,receipt)
        self.blocks[start]=data;self.receipts.append(receipt);return data
    def read(self,size=-1):
        if size<0:size=self.size-self.pos
        size=min(size,max(0,self.size-self.pos))
        if size>RANGE_CAP:raise ValueError('Refused oversized HDF read.')
        out=[];remaining=size
        while remaining:
            start=(self.pos//BLOCK)*BLOCK;part=self._block(start);i=self.pos-start
            take=min(remaining,len(part)-i)
            if take<=0:raise ValueError('Invalid range read progress.')
            out.append(part[i:i+take]);self.pos+=take;remaining-=take
        return b''.join(out)
    def readinto(self,b):
        data=self.read(len(b));b[:len(data)]=data;return len(data)


def read_hdf_attributes(handle):
    import h5py
    result={'global_attributes':{},'channels':{}}
    with h5py.File(handle,'r') as h:
        for k in ('data_time','title','production_date','timesys','TIMESYS'):
            if k in h.attrs:result['global_attributes'][k]=clean(h.attrs[k])
        for w in CHANNELS:
            name=f'aia{w}';link=h.get(name,getlink=True)
            if not isinstance(link,h5py.HardLink):
                result['channels'][name]={'status':'MISSING_OR_NONLOCAL_LINK'};continue
            ds=h[name]
            if not isinstance(ds,h5py.Dataset):raise ValueError('Expected AIA dataset object.')
            vals={}
            for k in ds.attrs.keys():
                if k.lower() in OBS_FIELDS or k.lower() in {'meta_0','meta_1','qflag'}:
                    v=clean(ds.attrs[k]);txt=json.dumps(v)
                    if len(txt)>262144:raise ValueError('Oversized metadata attribute.')
                    vals[k]=v
            result['channels'][name]={'status':'ATTRIBUTES_READ_NO_PIXELS','shape':list(ds.shape),'attributes':vals}
    return result


def parse_explicit(value, timesys=None):
    """No implicit UTC default. Return Astropy Time only for explicitly declared scales."""
    from astropy.time import Time
    s=str(value).strip();scale=None
    for suffix,sc in (('_TAI','tai'),('_UTC','utc')):
        if s.endswith(suffix):s=s[:-len(suffix)];scale=sc;break
    if s.endswith('Z'):s=s[:-1];scale='utc'
    if s.endswith('+00:00'):s=s[:-6];scale='utc'
    if scale is None and str(timesys).upper() in ('UTC','TAI'):scale=str(timesys).lower()
    if scale is None:return None
    s=re.sub(r'^(\d{4})\.(\d{2})\.(\d{2})_',r'\1-\2-\3T',s).replace(' ','T')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?',s):return None
    try:return Time(s,format='isot',scale=scale,precision=6)
    except (ValueError,TypeError):return None

def time_evidence(attrs,issue_tai):
    issue=parse_explicit(issue_tai)
    output=[]
    domains=[('attributes',attrs)]
    for key in ('meta_0','meta_1'):
        if key in attrs:
            try:
                d=json.loads(attrs[key]) if isinstance(attrs[key],str) else attrs[key]
                if isinstance(d,dict):domains.append((key,d))
            except (ValueError,TypeError):pass
    for origin,d in domains:
        low={str(k).lower():v for k,v in d.items()};syscale=low.get('timesys')
        for k,v in low.items():
            if k not in OBS_FIELDS or k in {'timesys','exptime','quality','wavelnth','wavelength','data_time'}:continue
            t=parse_explicit(v,syscale)
            r={'origin':origin,'field':k,'raw':clean(v),'timesys':clean(syscale)}
            if t is None:r['status']='SCALE_OR_FORMAT_UNRESOLVED'
            else:
                delta=round(float((t.tai-issue.tai).to_value('sec')),6)
                r.update(status='DECLARED_TIME_CONVERTED_NOT_GLOBAL_CLEARANCE',utc=str(t.utc.isot)+'Z',
                         frame_minus_issue_seconds=delta,within_180_seconds=abs(delta)<=180,at_or_before_issue=delta<=0)
            # T_REC is a record reference; T_OBS/DATE-OBS semantics and exposure end need review.
            r['exposure_end_and_product_availability_verified']=False
            output.append(r)
    return output

def s3_attributes(candidate,root,budget):
    src=candidate['metadata'].get('used_s3_path','')
    m=re.fullmatch(r's3://nasa-surya-bench/(\d{4}/\d{2}/\d{8}_\d{4}\.nc)',src)
    if not m:raise ValueError('No exact allowed SuryaBench source path.')
    url='https://nasa-surya-bench.s3.amazonaws.com/'+m[1]
    d=Path(root)/hashlib.sha256(url.encode()).hexdigest()[:24];d.mkdir(parents=True,exist_ok=True)
    done=d/'attributes.json'
    if done.exists():
        result=read_json(done)
        if result['url']!=url:raise ValueError('Cached attributes URL mismatch.')
        verify(done,read_json(d/'attributes_receipt.json')['sha256'])
    else:
        with RemoteHDF(url,d/'ranges',budget) as remote:
            content=read_hdf_attributes(remote)
            result={'url':url,'read_utc':now(),'remote_identity':remote.meta,
                    'range_bytes_this_run':remote.bytes_read,'range_receipts':remote.receipts,
                    'content':content,'pixel_arrays_read':False,
                    'historical_source_object_unchanged_since_extraction_proven':False}
        save(done,result);save(d/'attributes_receipt.json',{'sha256':digest(done)})
    times={k:time_evidence(v.get('attributes',{}),candidate['raw_T_REC']) for k,v in result['content']['channels'].items()}
    return {'status':'SOURCE_ATTRIBUTES_READ_REVIEW_TIMING','source':result,'timing_evidence':times}


def jsoc_query(candidate,w,root,budget):
    meta=json.loads(candidate['metadata']['channel_metadata'])[str(w)]
    name=meta['source_file'];m=re.fullmatch(r'aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})(\d{2})Z\.(\d+)\.image\.fits',name)
    if not m or int(m[5])!=w:raise ValueError('Unexpected JSOC source filename.')
    dt=f'{m[1]}T{m[2]}:{m[3]}:{m[4]}Z'
    ds=f'aia.lev1_euv_12s[{dt}][{w}]'
    query={'op':'rs_list','ds':ds,'key':'T_REC,T_OBS,EXPTIME,WAVELNTH,QUALITY','n':4}
    url='https://jsoc.stanford.edu/cgi-bin/ajax/jsoc_info?'+urlencode(query)
    p=Path(root)/ (hashlib.sha256(url.encode()).hexdigest()[:24]+'.json');p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():
        obj=read_json(p);verify(p,read_json(p.with_suffix('.receipt.json'))['sha256'])
        if obj['url']!=url:raise ValueError('JSOC cache identity mismatch.')
    else:
        with urlopen(Request(url,headers={'Accept-Encoding':'identity'}),timeout=budget.left(20)) as r:
            b=r.read(1024**2+1)
        if len(b)>1024**2:raise ValueError('JSOC reply exceeded 1 MiB.')
        data=json.loads(b)
        if data.get('status')!=0:raise ValueError(f'JSOC rs_list returned: {data.get("error",data.get("status"))}')
        obj={'url':url,'query':query,'read_utc':now(),'response':data,'original_export_request_id':meta['request_id']}
        save(p,obj);save(p.with_suffix('.receipt.json'),{'sha256':digest(p)})
    data=obj['response'];count=int(data.get('count',0));rows=[]
    if count>4:raise ValueError('More than four JSOC records returned.')
    for i in range(count):rows.append({k['name']:k['values'][i] for k in data.get('keywords',[]) if len(k.get('values',[]))>i})
    status='JSOC_RECORD_COUNT_NOT_ONE'
    if len(rows)==1:
        rec=parse_explicit(rows[0].get('T_REC'));ft=parse_explicit(dt)
        status='BASE_RECORD_IDENTITY_UNRESOLVED'
        if rec is not None and abs(float((rec-ft).to_value('sec')))<0.001 and str(rows[0].get('WAVELNTH'))==str(w):
            status='MATCHED_BASE_RECORD_NOT_ORIGINAL_EXPORTED_HEADER'
    return {'status':status,'evidence':obj,'rows':rows,'filename_utc':dt,
            'timing_evidence':[time_evidence(r,candidate['raw_T_REC']) for r in rows],
            'archived_processed_pixel_lineage_independently_verified':False}


def selected_manifests():
    paths=[]
    for y in (2013,2014,2015,2024):
        paths += [f'manifests/{y}/manifest_{y}.csv',f'manifests/{y}/manifest_{y}_AR_SPECIFIC.csv',f'manifests/{y}/extraction_log_{y}.csv']
    paths.append('manifests/2024/manifest_2024_GLOBAL_BACKUP.csv')
    return paths

def source_job(title,fn,out):
    print(title,flush=True)
    try:out.update(fn())
    except (Exception,) as e:out.update(status='UNRESOLVED_SOURCE',error=f'{type(e).__name__}: {e}')
    print('  '+out.get('status','READ'),flush=True)
    return out

def local_sources(repo,base,canary):
    p=repo/SNAPSHOT/'stage1/source_lock_snapshot.json'
    mf=read_json(repo/SNAPSHOT/'checkpoint_file_manifest.json')
    entries={x['path']:x for x in mf['files']};verify(p,entries[str(Path(SNAPSHOT)/'stage1/source_lock_snapshot.json')]['sha256'])
    lock=read_json(p);ids={c['sample_id'] for c in canary['results']};scans={};receipts={}
    for spec in lock['sources']:
        if spec['id'] not in ('curated_master','baseline_manifest'):continue
        f=Path(spec['local_path']).expanduser();verify(f,spec['sha256'])
        if f.stat().st_size!=spec['size_bytes']:raise ValueError('Locked source size mismatch.')
        print('Reading existing manifest once:',spec['id'],flush=True)
        scans[spec['id']]=pick_csv(f,ids);receipts[spec['id']]=spec
    if set(scans)!={'curated_master','baseline_manifest'}:raise ValueError('Locked sources unavailable.')
    return scans,receipts

def notebook_lineage(repo):
    """Read code cells only; never execute a notebook or infer execution from its name."""
    paths=[repo/'notebooks/training/16B_aia_sharp_intermediate_fusion_training.ipynb',
           repo/'notebooks/executed/16B_aia_sharp_intermediate_fusion_training_EXECUTED_fullnatural_allfold.ipynb']
    output=[]
    for p in paths:
        if not p.is_file():
            output.append({'path':str(p),'status':'NOT_IN_LOCAL_CHECKOUT'});continue
        nb=read_json(p)
        snippets=[]
        for i,c in enumerate(nb.get('cells',[])):
            if c.get('cell_type')!='code':continue
            source=c.get('source',[]);text=''.join(source) if isinstance(source,list) else source
            lines=text.splitlines()
            for j,line in enumerate(lines):
                if 'label_col =' in line or 'self.labels =' in line or 'y = torch.tensor(self.labels' in line:
                    snippets.append({'cell_index':i,'line':j+1,'code':'\n'.join(lines[max(0,j-1):j+3]),
                                     'saved_execution_count':c.get('execution_count')})
        output.append({'path':str(p),'sha256':digest(p),'status':'SAVED_CODE_READ_NOT_RERUN','snippets':snippets})
    return output

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=Path,default=Path.home()/'solar_flare_aia')
    ap.add_argument('--base',type=Path,default=Path.home()/'aia17_metadata_stage1')
    ap.add_argument('--local-only',action='store_true')
    ap.add_argument('--minutes',type=int,default=20)
    args=ap.parse_args()
    if not 1<=args.minutes<=30:raise ValueError('Use a 1--30 minute evidence budget.')
    from astropy.utils import iers
    iers.conf.auto_download=False
    import h5py,numpy,astropy
    if numpy.__version__!='2.2.6' or astropy.__version__!='7.1.0':
        raise RuntimeError('Use the recorded NumPy 2.2.6 / Astropy 7.1.0 environment; no auto-install performed.')
    # Independent anchor: avoid confusing a scale label with physical conversion.
    t=parse_explicit('2024.07.14_07:24:00_TAI')
    if str(t.utc.isot)!='2024-07-14T07:23:23.000000':raise ValueError('Time conversion anchor failed.')
    base=args.base.expanduser();repo=args.repo.expanduser();budget=Budget(args.minutes)
    if shutil.disk_usage(base).free<1024**3:raise ValueError('Keep 1 GiB free before this batch.')
    report_path=base/'npz_timing_canary_v1/reports'/CANARY_RUN/'npz_canary_report.json'
    canary=read_json(report_path)
    if canary.get('candidate_count')!=18 or len(canary.get('results',[]))!=18:raise ValueError('Unexpected canary scope.')
    ids=[c['sample_id'] for c in canary['results']]
    if len(set(ids))!=18 or any(not SID.fullmatch(s) for s in ids):raise ValueError('Unexpected candidate identities.')
    root=base/'consolidated_resolution_v1';root.mkdir(exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');out=root/'reports'/stamp;out.mkdir(parents=True)
    report={'version':VERSION,'created_utc':now(),'status':'EVIDENCE_BATCH_RUNNING',
        'input_canary':str(report_path),'input_canary_sha256':digest(report_path),
        'versions':{'numpy':numpy.__version__,'astropy':astropy.__version__,'h5py':h5py.__version__},
        'local_only':args.local_only,'original_labels_replaced':False,'training_authorised':False,
        'original_manifests':{},'suryabench_attributes':{},'jsoc_records':{}}
    print('===== CONSOLIDATED MANIFEST / SOURCE-TIME RESOLUTION =====',flush=True)
    scans,receipts=local_sources(repo,base,canary);report['local_manifest_scans']=dict(scans);report['local_source_locks']=receipts
    report['fusion_loader_code_evidence']=notebook_lineage(repo)
    # Save exact copied existing availability report, avoiding another extraction.
    avail=report_path.parent/'object_availability_by_year_and_original_label.csv'
    if avail.is_file():
        if avail.stat().st_size>1024**2:raise ValueError('Unexpected availability-summary size.')
        shutil.copyfile(avail,out/avail.name);report['availability_summary_sha256']=digest(avail)
    else:report['availability_summary']='NOT_FOUND_LOCALLY_NO_ABSENCE_INFERENCE'
    cloud=CloudCSVs(root/'gcs_manifest_cache',budget)
    for rel in selected_manifests():
        y=Path(rel).parts[1];target_ids={s for s in ids if s.startswith(y)}
        if args.local_only:report['original_manifests'][rel]={'status':'NOT_REQUESTED_LOCAL_ONLY'};continue
        def job(rel=rel,target_ids=target_ids):
            p,receipt=cloud.get(rel);scan=pick_csv(p,target_ids)
            scans[rel]=scan
            return {'status':'ORIGINAL_MANIFEST_OR_LOG_READ','receipt':receipt,'scan':scan}
        report['original_manifests'][rel]=source_job('Original record: '+rel,job,{})
    report['label_decisions']=label_findings(canary,scans)
    # Evidence-only local exclusion recommendation for the already known boundary case.
    report['boundary_disposition']={'sample_id':BOUNDARY,'recommendation':'PENDING_ALIGNMENT_REVIEW',
       'reason':'Recorded source key differs by 24 minutes; no tolerance or issue-time change adopted.',
       'source_records':[{'source':n,'rows':s.get('matches',{}).get(BOUNDARY,[])} for n,s in scans.items()
                        if s.get('matches',{}).get(BOUNDARY)]}
    for c in canary['results']:
        sid=c['sample_id']
        if c['format']=='SHARED_USED_TIMESTAMP':
            if args.local_only:r={'status':'NOT_REQUESTED_LOCAL_ONLY'}
            else:r=source_job('Source NetCDF attributes: '+sid,lambda c=c:s3_attributes(c,root/'s3_metadata_cache',budget),{})
            report['suryabench_attributes'][sid]=r
        elif c['format']=='PER_CHANNEL_METADATA':
            for w in CHANNELS:
                key=f'{sid}/{w}'
                if args.local_only:r={'status':'NOT_REQUESTED_LOCAL_ONLY'}
                else:r=source_job('JSOC record metadata: '+key,lambda c=c,w=w:jsoc_query(c,w,root/'jsoc_metadata_cache',budget),{})
                report['jsoc_records'][key]=r
    # This batch gathers specific evidence; it never certifies the full archive or event catalogue.
    report['unresolved_shared_gates']=[
        'Full catalogue completeness, region associations, event UTC provenance and 48h follow-up.',
        'Observation/exposure-end interpretation and archive-wide timing policy, not only nominal keys.',
        'Confirmed temporal violations must be corrected/excluded in relevant versions, not waived.',
        'Qualified AIA/SHARP histories, chronological/group-safe development and calibration split.',
        'Cross-cycle performance remains unevaluated; no new model result is claimed.']
    report['source_status_counts']={k:dict(Counter(v['status'] for v in report[k].values())) for k in
        ('original_manifests','suryabench_attributes','jsoc_records')}
    report['status']='EVIDENCE_BATCH_COMPLETE_DECISIONS_REQUIRED_NO_REPAIRS'
    report['finished_utc']=now();report['metadata_selected_bytes']=cloud.selected_bytes
    save(out/'resolution_report.json',report)
    lines=['# Consolidated source-evidence batch','',f'Created: {report["created_utc"]}',
        '', 'This is not a training clearance or a relabelled dataset. Original sources were not rewritten.',
        '', '## Label decisions']
    for r in report['label_decisions']:lines += [f'- {r["sample_id"]}: {r["status"]}']
    lines+=['','## Source collection', '```json',json.dumps(report['source_status_counts'],indent=2),'```',
            '', '## Boundary sample',BOUNDARY+': pending alignment review; original label retained.',
            '', '## Remaining shared gates']+['- '+s for s in report['unresolved_shared_gates']]
    (out/'resolution_summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save(out/'artifact_hashes.json',{p.name:digest(p) for p in out.iterdir() if p.is_file()})
    archive=out/'resolution_evidence.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.iterdir()):
            if p.is_file() and p!=archive:z.write(p,p.name)
    print('\n===== CONSOLIDATED RESOLUTION RESULTS =====')
    for r in report['label_decisions']:print(r['sample_id'],r['status'])
    print(json.dumps(report['source_status_counts'],indent=2))
    print('REPORT:',out/'resolution_report.json');print('SEND THIS ONE FILE:',archive)
    print('STATUS:',report['status'])
    print('No image tensors loaded, extraction jobs, cloud writes, labels changed, Git operations or model training.')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (Exception,) as e:
        print(f'STOP: {type(e).__name__}: {e}',file=sys.stderr);raise SystemExit(1)
