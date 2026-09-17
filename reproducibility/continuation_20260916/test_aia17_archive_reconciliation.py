"""Local, no-network tests for the read-only archive reconciliation tool."""
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('archive', Path(__file__).with_name('aia17_archive_reconciliation.py'))
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
SID = '20240714_0724_HARP11520_NOAA13753'

def obj(sid=SID, size=100, directory=None):
    y=int(sid[:4]); p=directory or a.prefix(y)
    return {'name':p+sid+'.npz','bucket':a.BUCKET,'generation':'123','size':size,'crc32c':'test'}

def target(sid=SID):
    return {'sample_id':sid,'stored_year':int(sid[:4]), 'expected_uri':a.expected_uri(sid),
            'original_label':1,'in_baseline':0, 'source_gcp_path':''}

class Tests(unittest.TestCase):
    def test_two_archive_roots(self):
        self.assertEqual(a.prefix(2024),'samples_npz/2024/')
        self.assertEqual(a.prefix(2025),'jsoc_2025_2026_production_v1/samples_npz/2025/')
        with self.assertRaises(ValueError): a.prefix(2027)

    def test_exact_match_is_metadata_only(self):
        r=a.classify(target(),[obj()])
        self.assertEqual(r['object_status'],'EXACT_NONEMPTY_OBJECT')
        self.assertFalse(r['image_contents_checked'])
        self.assertFalse(r['image_observation_times_checked'])
        self.assertEqual(r['original_label'],1)

    def test_missing_not_negative_label(self):
        r=a.classify(target(),[])
        self.assertEqual(r['object_status'],'NOT_FOUND_IN_AUDITED_PREFIX')
        self.assertEqual(r['original_label'],1)

    def test_zero_byte(self):
        self.assertEqual(a.classify(target(),[obj(size=0)])['object_status'],'ZERO_BYTE_OBJECT')

    def test_alternative_path_not_auto_approved(self):
        self.assertEqual(a.classify(target(),[obj(directory='samples_npz/2024/sub/')])['object_status'],'ALTERNATE_PATH_REVIEW')

    def test_multiple_no_arbitrary_selection(self):
        r=a.classify(target(),[obj(),obj(directory='samples_npz/2024/sub/')])
        self.assertEqual(r['object_status'],'MULTIPLE_OBJECTS_FOR_ID')
        self.assertEqual(r['same_id_object_count'],2)

    def test_cap_not_complete(self):
        with patch.object(a,'LIMIT',2):
            with self.assertRaisesRegex(ValueError,'completeness is unknown'):
                a.validate_listing([obj(),obj()],2024)

    def test_wrong_prefix_and_duplicate_list_response(self):
        with self.assertRaises(ValueError): a.validate_listing([obj(directory='outside/')],2024)
        with self.assertRaises(ValueError): a.validate_listing([obj(),obj()],2024)
        with self.assertRaises(ValueError): a.validate_listing({'items':[]},2024)

    def test_missing_generation_rejected(self):
        r=obj(); r.pop('generation')
        with self.assertRaises(ValueError): a.validate_listing([r],2024)

    def test_missing_year_cannot_be_zero(self):
        with self.assertRaises(KeyError): a.reconcile({SID:target()}, {})

    def test_no_modifications_on_failed_listing(self):
        with tempfile.TemporaryDirectory() as d:
            def fail(cmd, stdout, stderr, **kwargs):
                stdout.write(b'[]'); stderr.write(b'billing not enabled')
                return subprocess.CompletedProcess(cmd,1)
            with patch.object(a.subprocess,'run',side_effect=fail):
                with self.assertRaises(RuntimeError): a.fetch_listing(2024,Path(d))
            self.assertEqual(list(Path(d).iterdir()),[])

    def test_duplicate_source_ids_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.csv'
            p.write_text('sample_id,HARPNUM,NOAA_AR_clean,T_REC_dt,label_48h_final\n'+
                         (f'{SID},11520,13753,2024-07-14 07:24:00,1\n')*2)
            with self.assertRaisesRegex(ValueError,'duplicate target ID'): a.read_targets(p,2)

    def test_reconcile_retains_extras_and_canary_no_pixels(self):
        data={y:[] for y in a.YEARS}; data[2024]=[obj(),obj(sid='20240715_0724_HARP11520_NOAA13753')]
        rows,extras,summary,canaries=a.reconcile({SID:target()},data)
        self.assertEqual(len(extras),1)
        self.assertFalse(extras[0]['delete_authorised'])
        self.assertEqual(len(canaries),1)
        self.assertEqual(rows[0]['original_label'],1)

    def test_end_to_end_and_cache_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); repo=root/'repo'; repo.mkdir(); snapshot=repo/a.SNAPSHOT/'stage1'; snapshot.mkdir(parents=True)
            master=root/'curated.csv'; baseline=root/'baseline.csv'
            data=[('20130720_1824_HARP2968_NOAA11793','2968','11793','2013-07-20 18:24:00','0'),
                  ('20240714_0724_HARP11520_NOAA13753','11520','13753','2024-07-14 07:24:00','1'),
                  ('20250101_0100_HARP12345_NOAA13999','12345','13999','2025-01-01 01:00:00','0')]
            for p, rows in [(master,data),(baseline,data[:1])]:
                with p.open('w',newline='') as f:
                    w=csv.writer(f); w.writerow(['sample_id','HARPNUM','NOAA_AR_clean','T_REC_dt','label_48h_final']); w.writerows(rows)
            lock={'project':a.PROJECT,'sources':[{'id':name,'local_path':str(path),'size_bytes':path.stat().st_size,'sha256':a.sha256(path)} for name,path in [('curated_master',master),('baseline_manifest',baseline)]]}
            prof={'source_profiles':[{'source':'curated_master','rows':3},{'source':'baseline_manifest','rows':1}]}
            a.save_json(snapshot/'source_lock_snapshot.json',lock)
            a.save_json(snapshot/'stage1_report.json',prof)
            manifest={'files':[{'path':str(p.relative_to(repo)),'sha256':a.sha256(p)} for p in snapshot.iterdir()]}
            a.save_json(repo/a.SNAPSHOT/'checkpoint_file_manifest.json',manifest)
            before={str(p):a.sha256(p) for p in root.rglob('*') if p.is_file()}
            calls=[]
            def fake(cmd, stdout, stderr, **kwargs):
                self.assertEqual(cmd[:4],['gcloud','storage','objects','list'])
                self.assertFalse(any(x in cmd for x in ['cp','rm','mv','compute']))
                calls.append(cmd)
                items=[obj(sid=r[0]) for r in data if cmd[4]==f'gs://{a.BUCKET}/{a.prefix(int(r[0][:4]))}**']
                stdout.write(json.dumps(items).encode())
                return subprocess.CompletedProcess(cmd,0)
            args=['tool','--repo',str(repo),'--work',str(root/'work')]
            with patch.object(sys,'argv',args), patch.object(a.shutil,'which',return_value='/mock/gcloud'), patch.object(a.subprocess,'run',side_effect=fake), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(a.main(),0)
                self.assertEqual(a.main(),0)
            self.assertEqual(len(calls),17,'second invocation must reuse all verified yearly listings')
            for p,h in before.items(): self.assertEqual(a.sha256(Path(p)),h)
            reports=list((root/'work/reports').glob('*/archive_reconciliation_report.json'))
            self.assertEqual(len(reports),2)
            r=json.loads(reports[0].read_text())
            self.assertEqual(r['status'],a.FINAL_OK)
            self.assertEqual(r['status_counts'],{'EXACT_NONEMPTY_OBJECT':3})
            self.assertFalse(r['training_authorised'])
            self.assertEqual(r['canary_images_downloaded'],0)
            self.assertFalse((root/'work/.running.lock').exists())

if __name__=='__main__': unittest.main(verbosity=2)
