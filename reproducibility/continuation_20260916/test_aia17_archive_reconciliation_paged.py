"""Local tests only: HTTP, credentials and cloud listings are simulated."""
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse

ROOT = Path(__file__).parent
s = importlib.util.spec_from_file_location('paged_archive', ROOT/'aia17_archive_reconciliation_paged.py')
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)


def obj(n=1, year=2010):
    return {'name': f'samples_npz/{year}/{n:07d}.npz', 'bucket':'suryabench-sharp-pipeline-bamidele',
            'size':'100', 'generation':'123'}


def page(items=None, token=None):
    data = {'kind':'storage#objects'}
    if items is not None: data['items'] = items
    if token is not None: data['nextPageToken'] = token
    return json.dumps(data).encode()


class Token:
    value = 'TEST_ONLY_NEVER_A_REAL_CREDENTIAL'
    def get(self): return self.value


class Response(io.BytesIO):
    status = 200
    def __init__(self, raw):
        super().__init__(raw); self.headers = {'Content-Length':str(len(raw))}


class Opener:
    def __init__(self, values): self.values = iter(values); self.calls = []
    def open(self, request, timeout):
        self.calls.append((request, timeout))
        value = next(self.values)
        if isinstance(value, Exception): raise value
        return Response(value)


class PagedTests(unittest.TestCase):
    def setUp(self):
        self.a = m.load_base(ROOT/'aia17_archive_reconciliation.py')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)

    def backend(self, values):
        self.opener = Opener(values)
        return m.StoragePages(self.a, token=Token(), opener=self.opener, sleep=lambda _: None)

    def quiet_fetch(self, backend, year=2010):
        with contextlib.redirect_stdout(io.StringIO()):
            return backend.fetch_listing(year, self.cache)

    def test_original_script_hash_guard(self):
        wrong = self.cache/'wrong.py'; wrong.write_text('raise RuntimeError("do not execute")')
        with self.assertRaises(ValueError): m.load_base(wrong)

    def test_authenticated_get_prefix_only_fields_and_no_acl(self):
        b = self.backend([page([obj()])]); self.quiet_fetch(b)
        request, timeout = self.opener.calls[0]
        parts = urllib.parse.urlparse(request.full_url)
        query = urllib.parse.parse_qs(parts.query)
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(parts.netloc, 'storage.googleapis.com')
        self.assertTrue(parts.path.endswith('/o'))
        self.assertEqual(query['prefix'], ['samples_npz/2010/'])
        self.assertEqual(query['maxResults'], ['500'])
        self.assertEqual(query['projection'], ['noAcl'])
        self.assertIn('nextPageToken', query['fields'][0])
        self.assertNotIn('alt', query)
        self.assertNotIn(Token.value, request.full_url)
        for p in self.cache.rglob('*.json'): self.assertNotIn(Token.value, p.read_text())

    def test_empty_page_with_token_is_not_completion(self):
        b = self.backend([page([], 'next'), page([obj()])])
        items, receipt = self.quiet_fetch(b)
        self.assertEqual(len(self.opener.calls), 2)
        self.assertEqual(len(items), 1)
        self.assertEqual(receipt['completion_basis'], 'TERMINAL_PAGE_WITHOUT_NEXT_PAGE_TOKEN')

    def test_fewer_than_page_size_still_follows_token(self):
        b = self.backend([page([obj(1)], 'next'), page([obj(2)])])
        items, _ = self.quiet_fetch(b)
        self.assertEqual(len(items), 2)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.opener.calls[1][0].full_url).query)
        self.assertEqual(query['pageToken'], ['next'])

    def test_completed_cache_reuse_makes_no_requests(self):
        b = self.backend([page([obj()])]); self.quiet_fetch(b)
        b2 = self.backend([]); items, receipt = self.quiet_fetch(b2)
        self.assertEqual(len(items), 1)
        self.assertTrue(receipt['reused']); self.assertEqual(self.opener.calls, [])

    def test_partial_pages_resume_without_relisting_first_page(self):
        denied = urllib.error.HTTPError('https://storage.googleapis.com/',403,'Forbidden',{},io.BytesIO(b'{"error":{"message":"Forbidden"}}'))
        b = self.backend([page([obj(1)], 'next'), denied])
        with self.assertRaisesRegex(RuntimeError,'HTTP_403'): self.quiet_fetch(b)
        self.assertFalse((self.cache/'objects_2010.receipt.json').exists())
        self.assertFalse((self.cache/'objects_2010.json').exists())
        b2 = self.backend([page([obj(2)])]); items, _ = self.quiet_fetch(b2)
        self.assertEqual(len(items),2); self.assertEqual(len(self.opener.calls),1)
        self.assertIn('pageToken=next', self.opener.calls[0][0].full_url)

    def test_network_timeout_retries_are_bounded(self):
        b = self.backend([TimeoutError('slow')]*3)
        with self.assertRaisesRegex(RuntimeError,'after 3 attempt'): self.quiet_fetch(b)
        self.assertEqual(len(self.opener.calls), 3)
        self.assertFalse((self.cache/'objects_2010.receipt.json').exists())

    def test_http_403_stops_without_retry_and_redacts_secret(self):
        error = urllib.error.HTTPError('https://storage.googleapis.com/',403,'Forbidden',{},
                    io.BytesIO(json.dumps({'error':{'message':'Bearer '+Token.value}}).encode()))
        b = self.backend([error])
        with self.assertRaises(RuntimeError) as caught: self.quiet_fetch(b)
        self.assertEqual(len(self.opener.calls),1)
        self.assertNotIn(Token.value,str(caught.exception))
        for p in self.cache.rglob('*.json'): self.assertNotIn(Token.value,p.read_text())

    def test_invalid_json_object_not_empty_listing(self):
        b = self.backend([b'{}'])
        with self.assertRaises(ValueError): self.quiet_fetch(b)
        self.assertFalse((self.cache/'objects_2010.receipt.json').exists())

    def test_wrong_prefix_not_accepted(self):
        o = obj(); o['name'] = 'other/' + o['name']
        with self.assertRaises(ValueError): self.quiet_fetch(self.backend([page([o])]))

    def test_repeated_token_not_accepted(self):
        with self.assertRaisesRegex(ValueError, 'Repeated continuation'):
            self.quiet_fetch(self.backend([page([obj(1)],'next'),page([obj(2)],'next')]))
        self.assertFalse((self.cache/'objects_2010.receipt.json').exists())

    def test_duplicate_name_across_pages_not_accepted(self):
        with self.assertRaisesRegex(ValueError,'Repeated/out-of-order'):
            self.quiet_fetch(self.backend([page([obj()],'next'),page([obj()])]))

    def test_changed_cached_page_rejected(self):
        denied = urllib.error.HTTPError('https://storage.googleapis.com/',403,'Forbidden',{},io.BytesIO(b'{}'))
        with self.assertRaises(RuntimeError): self.quiet_fetch(self.backend([page([obj()],'next'),denied]))
        p = self.cache/'pages_2010/page_00001.json'; saved = json.loads(p.read_text())
        saved['response_text'] = page([obj(2)],'next').decode(); p.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError,'checksum'): self.quiet_fetch(self.backend([]))

    def test_page_limit_not_completed(self):
        with patch.object(m,'MAX_PAGES',1):
            with self.assertRaisesRegex(ValueError, 'Page-count'):
                self.quiet_fetch(self.backend([page([obj()],'next')]))
        self.assertFalse((self.cache/'objects_2010.receipt.json').exists())

    def test_object_count_limit_not_completed(self):
        with patch.object(self.a,'LIMIT',2):
            with self.assertRaises(ValueError):
                self.quiet_fetch(self.backend([page([obj(1)],'next'),page([obj(2)])]))
        self.assertFalse((self.cache/'objects_2010.receipt.json').exists())

    def test_original_year_cache_compatible_and_not_modified(self):
        self.a.save_json(self.cache/'objects_2010.json',[obj()])
        record = {'bucket':self.a.BUCKET,'prefix':self.a.prefix(2010),'year':2010,'complete':True,
                  'sha256':self.a.sha256(self.cache/'objects_2010.json'),'object_count':1,
                  'finished_utc':'2026-09-16T07:00:00+00:00'}
        self.a.save_json(self.cache/'objects_2010.receipt.json',record)
        before = {p:p.read_bytes() for p in self.cache.iterdir()}
        items,_ = self.quiet_fetch(self.backend([]))
        self.assertEqual(len(items),1); self.assertEqual(self.opener.calls,[])
        for p,v in before.items(): self.assertEqual(p.read_bytes(),v)

    def test_no_overwrite_conflicting_orphan(self):
        original=self.cache/'objects_2010.json'; original.write_text('[]')
        with self.assertRaisesRegex(ValueError,'Unverified yearly'): self.quiet_fetch(self.backend([]))
        self.assertEqual(original.read_text(),'[]')

    def test_gcloud_token_never_printed_or_put_in_argv(self):
        captured=io.StringIO()
        def proc(cmd, **kwargs):
            self.assertEqual(cmd[:3], ['gcloud','auth','print-access-token'])
            self.assertNotIn(Token.value, str(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout=Token.value.encode(), stderr=b'')
        with patch.object(m.subprocess,'run',side_effect=proc) as called, contextlib.redirect_stdout(captured):
            t=m.SessionToken(self.a.PROJECT)
            self.assertEqual(t.get(),Token.value); self.assertEqual(t.get(),Token.value)
        self.assertEqual(called.call_count,1); self.assertNotIn(Token.value,captured.getvalue())

    def test_auth_timeout_does_not_expose_subprocess_output(self):
        with patch.object(m.subprocess,'run',side_effect=subprocess.TimeoutExpired('gcloud',60,output=Token.value.encode())):
            with self.assertRaisesRegex(RuntimeError,'AUTH_TIMEOUT') as caught:
                with contextlib.redirect_stdout(io.StringIO()): m.SessionToken(self.a.PROJECT).get()
        self.assertNotIn(Token.value,str(caught.exception))

    def test_no_redirect_credentials(self):
        self.assertIsNone(m.NoRedirect().redirect_request(None,None,302,'',{},'https://untrusted.example/'))

    def test_integrated_existing_contract_and_all_year_reports(self):
        root=self.cache; repo=root/'repo'; repo.mkdir(); snap=repo/self.a.SNAPSHOT/'stage1'; snap.mkdir(parents=True)
        master=root/'curated.csv'; baseline=root/'baseline.csv'
        data=[('20130720_1824_HARP2968_NOAA11793','2968','11793','2013-07-20 18:24:00','0'),
              ('20240714_0724_HARP11520_NOAA13753','11520','13753','2024-07-14 07:24:00','1')]
        for path, rows in [(master,data),(baseline,data[:1])]:
            with path.open('w',newline='') as f:
                w=csv.writer(f); w.writerow(['sample_id','HARPNUM','NOAA_AR_clean','T_REC_dt','label_48h_final']); w.writerows(rows)
        lock={'project':self.a.PROJECT,'sources':[{'id':n,'local_path':str(p),'size_bytes':p.stat().st_size,'sha256':self.a.sha256(p)}
                             for n,p in [('curated_master',master),('baseline_manifest',baseline)]]}
        profile={'source_profiles':[{'source':'curated_master','rows':2},{'source':'baseline_manifest','rows':1}]}
        self.a.save_json(snap/'source_lock_snapshot.json',lock); self.a.save_json(snap/'stage1_report.json',profile)
        self.a.save_json(repo/self.a.SNAPSHOT/'checkpoint_file_manifest.json',{'files':[
            {'path':str(p.relative_to(repo)),'sha256':self.a.sha256(p)} for p in snap.iterdir()]})
        sources, profiles, hashes=self.a.load_inputs(repo)
        work=root/'work'; work.mkdir()
        # This is the exact pre-existing v1 contract left by a failed original run.
        contract={'version':self.a.VERSION,'project':self.a.PROJECT,'bucket':self.a.BUCKET,'years':self.a.YEARS,
                  'source_sha256':hashes,'listing_limit':self.a.LIMIT,'label_column_unchanged':'label_48h_final'}
        self.a.save_json(work/'input_contract.json',contract)
        before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
        responses=[]
        for y in self.a.YEARS:
            items=[{'name':self.a.prefix(y)+r[0]+'.npz','size':'100','generation':'123','bucket':self.a.BUCKET}
                   for r in data if int(r[0][:4])==y]
            responses.append(page(items))
        backend=self.backend(responses); self.a.fetch_listing=backend.fetch_listing
        with patch.object(sys,'argv',['tool','--repo',str(repo),'--work',str(work)]), patch.object(self.a.shutil,'which',return_value='/mock/gcloud'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.a.main(),0); self.assertEqual(self.a.main(),0)
        self.assertEqual(len(self.opener.calls),17)
        for p,content in before.items(): self.assertEqual(p.read_bytes(),content)
        reports=list((work/'reports').glob('*/archive_reconciliation_report.json'))
        self.assertEqual(len(reports),2)
        result=json.loads(reports[0].read_text())
        self.assertEqual(result['master_targets'],2)
        self.assertEqual(result['status_counts'],{'EXACT_NONEMPTY_OBJECT':2})
        self.assertFalse(result['training_authorised']); self.assertEqual(result['canary_images_downloaded'],0)
        self.assertFalse((work/'.running.lock').exists())


if __name__ == '__main__': unittest.main(verbosity=2)
