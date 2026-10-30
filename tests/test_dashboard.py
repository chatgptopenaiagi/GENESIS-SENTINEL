"""Real loopback HTTP and owned lifecycle in disposable synthetic state only."""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from genesis_sentinel import control_model as model
from genesis_sentinel import control_server as server
from genesis_sentinel import control_services as services
from genesis_sentinel import adapters
from genesis_sentinel import jupyter


def synthetic(root):
    generation='synthetic-generation'
    dest=root/'generations'/generation;dest.mkdir(parents=True)
    at='2020-01-01T00:00:00+00:00'
    env={'id':'python-synthetic','interpreter':'/example/env/bin/python','prefix':'/example/env','python_version':'3.10','state':'INSTALLED','observed_at':at,'packages':[{'name':'numpy','version':'1.0','location':'/example/env/lib','metadata_path':'/example/env/metadata'}],'conda_packages':[]}
    inventory={'generation':generation,'observed_at':at,'environments':[env],'tools':[],'errors':[],'arch_packages':{'packages':[]}}
    graph={'generation':generation,'capabilities':[{'id':'python-synthetic:numpy','environment_id':env['id'],'interpreter':env['interpreter'],'package':'numpy','version':'1.0','state':'FUNCTIONALLY_VERIFIED','last_functional_verification_at':at,'last_observation_at':at,'supported_operation':'matrix multiplication','known_limitations':['Named operation only.']}]}
    for name,data in [('SOFTWARE-INVENTORY.json',inventory),('CAPABILITY-GRAPH.json',graph),('PROJECT-MAP.json',{'generation':generation,'projects':[]}),('ENVIRONMENTS.json',{'generation':generation,'environments':[env]})]:
        (dest/name).write_text(json.dumps(data))
    for name in ['SESSION-BRIEF.md','CURRENT-STATUS.md']:(dest/name).write_text('# Synthetic record\n')
    (root/'current').symlink_to('generations/'+generation)
    for name in ['SOFTWARE-INVENTORY.json','CAPABILITY-GRAPH.json','PROJECT-MAP.json','ENVIRONMENTS.json','SESSION-BRIEF.md','CURRENT-STATUS.md']:(root/name).symlink_to('current/'+name)
    config={'schema_version':1,'interpreters':[],'conda_roots':[],'conda_registry_files':[],'projects':[],'extra_roots':[],'tool_roots':[],'tool_names':[],'services':[],'scientific_registries':[],'verification_ttl_hours':24,'collect_arch_packages':False}
    (root/'config.json').write_text(json.dumps(config));return config


def request(op,base,path,body=None,headers=None):
    hdr=dict(headers or {})
    if body is not None:hdr['Content-Type']='application/json'
    req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=hdr)
    try:
        with op.open(req,timeout=15) as response:return response.status,response.read(),dict(response.headers)
    except urllib.error.HTTPError as e:
        try:return e.code,e.read(),dict(e.headers)
        finally:e.close()


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.cfg=synthetic(self.root)
        self.oldroot=model.ROOT;model.ROOT=self.root;model.CACHE.clear()
    def tearDown(self):model.ROOT=self.oldroot;model.CACHE.clear();self.tmp.cleanup()
    def test_snapshot_status_and_unknown_acceleration(self):
        data=model.get_data();self.assertEqual(data['meta']['counts']['software'],1)
        self.assertEqual(data['capabilities'][0]['status'],'STALE')
        self.assertEqual(data['software'][0]['status'],'STALE')
        self.assertFalse(data['meta']['ai']['cpu_verified']);self.assertIsNone(data['meta']['ai']['cuda_available'])
    def test_explicit_reports_and_private_boundary(self):
        report=self.root/'qualification.json';report.write_text(json.dumps({'checked_at':'2026-01-01T00:00:00+00:00','passed':2,'failed':1}))
        private=self.root/'private';private.mkdir();(private/'auth.json').write_text('{"password":"SYNTHETIC-SECRET"}')
        self.cfg['dashboard_reports']=[{'path':str(report),'title':'Synthetic qualification'},{'path':str(private/'auth.json'),'title':'Private file'}]
        (self.root/'config.json').write_text(json.dumps(self.cfg))
        data=model.get_data();self.assertEqual(len(data['history']),1)
        self.assertEqual(data['history'][0]['status'],'FAILED')
        rid=data['history'][0]['report_id'];self.assertIn('passed',model.get_report(rid)['text'])
        report.unlink();report.symlink_to(private/'auth.json')
        self.assertIsNone(model.get_report(rid));self.assertNotIn('SYNTHETIC-SECRET',json.dumps(data))
    def test_inconsistent_generation_rejected(self):
        (self.root/'current/CAPABILITY-GRAPH.json').write_text('{"generation":"other"}')
        with self.assertRaisesRegex(ValueError,'Inconsistent'):model.get_data()
    def test_tail_history_and_relocation(self):
        rows=[{'generation':'baseline','changes':[]},{'generation':'next','observed_at':'2026-01-01T00:00:00+00:00','changes':[{'id':'cli:synthetic','kind':'CHANGED','before':{'real_path':'/example/old','version':'1'},'after':{'real_path':'/example/new','version':'1'}}]}]
        (self.root/'CHANGES.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
        self.assertEqual(model.json_lines(self.root/'CHANGES.jsonl',limit=1,tail=True)[0]['generation'],'next')
        self.assertEqual(model.change_rows()[0]['kind'],'MOVED')


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);synthetic(cls.root)
        cls.oldroot=server.B;server.configure(cls.root);server.setup_storage();cls.credentials=server.access()
        cls.http=server.Server(('127.0.0.1',0),server.Handler);cls.base='http://127.0.0.1:'+str(cls.http.server_port)
        cls.http.control_url=cls.base+'/'
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.anon=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cls.jar=http.cookiejar.CookieJar();cls.op=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(cls.jar))
        code,body,cls.loginheaders=request(cls.op,cls.base,'/api/login',{k:cls.credentials[k] for k in ['username','password']},{'Origin':cls.base})
        assert code==200
        cls.csrf=json.loads(body)['csrf'];cls.headers={'Origin':cls.base,'X-CSRF-Token':cls.csrf}
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join(3);server.configure(cls.oldroot);model.CACHE.clear();cls.tmp.cleanup()
    def test_public_assets_and_nine_pages(self):
        self.assertEqual(request(self.anon,self.base,'/')[0],200)
        code,js,_=request(self.anon,self.base,'/app.js');self.assertEqual(code,200)
        for page in ['software','projects','science','ai','anaconda','history','changes','status']:self.assertIn(page.encode(),js)
        self.assertNotIn(b'/root/',js)
    def test_authentication_cookie_and_inventory(self):
        self.assertEqual(request(self.anon,self.base,'/api/data')[0],401)
        code,body,_=request(self.op,self.base,'/api/data');self.assertEqual(code,200)
        data=json.loads(body);self.assertEqual(len(data['software']),1)
        self.assertNotIn(self.credentials['password'].encode(),body)
        cookie=self.loginheaders['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
    def test_origin_csrf_host_and_arbitrary_action_rejected(self):
        body={'service':'sentinel','action':'refresh'}
        for headers in [{'Origin':self.base},{'Origin':'http://example.invalid','X-CSRF-Token':self.csrf}]:self.assertEqual(request(self.op,self.base,'/api/action',body,headers)[0],403)
        self.assertEqual(request(self.op,self.base,'/api/session',headers={'Host':'example.invalid'})[0],403)
        self.assertEqual(request(self.op,self.base,'/api/action',{'service':'shell','action':'id'},self.headers)[0],400)
    def test_private_paths_and_security_headers(self):
        for path in ['/private/control/access.json','/control_server.py','/%2e%2e/private/control/access.json','/reports/../../private/control/access.json']:
            self.assertEqual(request(self.op,self.base,path)[0],404)
        _,_,headers=request(self.op,self.base,'/api/session');self.assertEqual(headers['Cache-Control'],'no-store');self.assertEqual(headers['Referrer-Policy'],'no-referrer')
        self.assertEqual((self.root/'private/control').stat().st_mode&0o777,0o700)
        self.assertEqual((self.root/'private/control/access.json').stat().st_mode&0o777,0o600)
    def test_refresh_action_commits_and_retains_audit(self):
        old=(self.root/'current').resolve()
        code,body,_=request(self.op,self.base,'/api/action',{'service':'sentinel','action':'refresh'},self.headers)
        self.assertEqual(code,202);job=json.loads(body)
        for _ in range(100):
            code,body,_=request(self.op,self.base,'/api/actions/'+job['id']);result=json.loads(body)
            if result['status'] not in ['queued','running']:break
            time.sleep(.05)
        self.assertEqual(result['status'],'succeeded',result)
        self.assertNotEqual((self.root/'current').resolve(),old)
        self.assertTrue(old.is_dir());self.assertTrue((self.root/'runtime/control-actions.jsonl').exists())


class AdapterTests(unittest.TestCase):
    def test_disabled_by_default_and_busy_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'config.json').write_text('{}');adapters.configure(root)
            self.assertFalse(adapters.allowed('science','start'))
            with patch.object(adapters,'SCRIPTS',{'science':{'stop':'/synthetic/STOP-LAB.sh'}}),patch.object(adapters,'_service',return_value={'state':'BUSY','owned':True}):
                with self.assertRaisesRegex(RuntimeError,'active calculation'):adapters._guard('science','stop')
    def test_jupyter_requires_existing_interpreter_and_identity(self):
        with tempfile.TemporaryDirectory() as d:
            jupyter.configure(Path(d))
            with self.assertRaises(SystemExit):jupyter.interpreter('/synthetic/missing-python')
            self.assertFalse(jupyter.owned({'pid':os.getpid(),'identity':{}}))
    def test_configured_url_and_redirects_do_not_leak_authentication(self):
        for url in ['https://remote.invalid:443/','http://127.0.0.1:8888@remote.invalid/lab','http://127.0.0.1:8888/lab?token=synthetic']:
            self.assertFalse(services.local_url(url))
        self.assertTrue(services.local_url('http://127.0.0.1:9000/'))


class LifecycleTests(unittest.TestCase):
    def test_real_owned_restart_preserves_session_credentials_and_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);synthetic(root);before=hashlib.sha256((root/'SOFTWARE-INVENTORY.json').read_bytes()).hexdigest()
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env=os.environ.copy();env['GENESIS_SENTINEL_HOME']=str(root)
            def invoke(command):
                proc=subprocess.run([sys.executable,'-m','genesis_sentinel.control_lifecycle','--port',str(port),command],env=env,capture_output=True,text=True,timeout=35)
                self.assertEqual(proc.returncode,0,proc.stderr);return proc
            try:
                invoke('start');pub=json.loads((root/'runtime/control-public.json').read_text());base=pub['url'].rstrip('/')
                credentials=json.loads((root/'private/control/access.json').read_text());secret=(root/'private/control/access.json').read_bytes();pid=json.loads((root/'private/control/process.json').read_text())['pid']
                op=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                code,body,_=request(op,base,'/api/login',{k:credentials[k] for k in ['username','password']},{'Origin':base});self.assertEqual(code,200);csrf=json.loads(body)['csrf']
                invoke('restart');newpid=json.loads((root/'private/control/process.json').read_text())['pid'];self.assertNotEqual(pid,newpid)
                code,body,_=request(op,base,'/api/session');self.assertEqual(code,200);self.assertEqual(json.loads(body)['csrf'],csrf)
                self.assertEqual((root/'private/control/access.json').read_bytes(),secret)
                self.assertEqual(hashlib.sha256((root/'SOFTWARE-INVENTORY.json').read_bytes()).hexdigest(),before)
                self.assertTrue(json.loads(body)['authenticated'])
            finally:invoke('stop')

if __name__=='__main__':unittest.main(verbosity=2)
