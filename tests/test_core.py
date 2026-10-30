"""Portable extraction tests: bounded isolated state, never the operator deployment."""
import base64
import contextlib
import datetime
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
from genesis_sentinel import core as s
from genesis_sentinel.config import default_config, state_dir,validate_config

def hold(root,ready):
    with s.writer(Path(root)):
        ready.set();time.sleep(.6)

def fixture_config(root,interpreters=()):
    value=default_config();value.update(interpreters=list(interpreters),conda_roots=[],conda_registry_files=[],projects=[],extra_roots=[],tool_roots=[],tool_names=[],services=[],collect_arch_packages=False)
    s.atomic(Path(root)/'config.json',value);return value

def quiet_refresh(root,full=False):
    with contextlib.redirect_stdout(io.StringIO()):return s.refresh(Path(root),full)

def files(generation):return {name:{'generation':generation} if name.endswith('.json') else 'Generation: '+generation+'\n' for name in s.NAMES}

class CoreTests(unittest.TestCase):
    def test_default_state_and_explicit_config(self):
        with patch.dict(os.environ,{'GENESIS_SENTINEL_HOME':'/fixture/state'}):self.assertEqual(state_dir(),Path('/fixture/state'))
        self.assertEqual(state_dir('/fixture/explicit'),Path('/fixture/explicit'))
        self.assertEqual(default_config()['interpreters'],[str(Path(sys.executable).absolute())])
        self.assertEqual(default_config()['projects'],[])
        with self.assertRaises(ValueError):validate_config({'interpreters':['relative/bin/python']})
        with self.assertRaises(ValueError):validate_config({'services':[{'port':True}]})

    def test_changes_add_upgrade_move_and_remove(self):
        def snap(version='1',interpreter='/fixture/env/bin/python',present=True):
            return {'environments':[{'id':'env','interpreter':interpreter,'state':'INSTALLED','signature':version,'packages':[{'name':'fixture','version':version,'location':'/fixture/lib','metadata_path':'/fixture/meta'}]}] if present else []}
        self.assertEqual(s.changes(snap(),snap()),[])
        self.assertEqual({d['kind'] for d in s.changes({},snap())},{'ADDED'})
        self.assertEqual({d['kind'] for d in s.changes(snap(),snap('2'))},{'CHANGED'})
        self.assertTrue(any(d['after'].get('interpreter')=='/moved/env/bin/python' for d in s.changes(snap(),snap(interpreter='/moved/env/bin/python'))))
        self.assertEqual({d['kind'] for d in s.changes(snap(),snap(present=False))},{'REMOVED'})

    def test_discovery_registered_roots_conda_and_aliases(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for name in ['env','other','conda/envs/analysis','project/.venv']:
                p=root/name/'bin';p.mkdir(parents=True);(p/'python').write_text('fixture')
            (root/'alias').symlink_to(root/'env',target_is_directory=True)
            cfg=fixture_config(root,[str(root/'env/bin/python'),str(root/'alias/bin/python'),str(root/'other/bin/python')])
            cfg['conda_roots']=[str(root/'conda')];cfg['projects']=[{'path':str(root/'project')}]
            found=s.discover(cfg);self.assertEqual(len(found),5);self.assertIn(str(root/'project/.venv/bin/python'),found)
            self.assertEqual(len([p for p in found if '/alias/' in p or p.endswith('/env/bin/python')]),1)

    def test_incremental_metadata_cache_and_removed_environment(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);fixture_config(root,[sys.executable])
            first=quiet_refresh(root);second=quiet_refresh(root)
            self.assertEqual(len(first['environments']),1);self.assertTrue(second['environments'][0]['cached']);self.assertFalse(second['errors'])
            self.assertEqual(second['changes_count'],0)
            env=s.inspect_env(str(root/'removed/bin/python'),None,True)
            self.assertEqual(env['state'],'UNAVAILABLE')
            self.assertEqual(s.get_status(root)['state'],'CURRENT')

    def test_capability_is_installed_before_explicit_verification(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);fixture_config(root,[sys.executable]);quiet_refresh(root)
            graph=s.load(root/'CAPABILITY-GRAPH.json');cap=next(c for c in graph['capabilities'] if c['package']=='sqlite3')
            self.assertEqual(cap['state'],'INSTALLED')
            with contextlib.redirect_stdout(io.StringIO()):self.assertTrue(s.verify(cap['id'],root))
            result=next(c for c in s.load(root/'CAPABILITY-GRAPH.json')['capabilities'] if c['id']==cap['id'])
            self.assertEqual(result['state'],'FUNCTIONALLY_VERIFIED');self.assertTrue(Path(result['evidence']).is_file())

    def test_failed_verification_evidence_is_retained(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);fixture_config(root,[sys.executable]);quiet_refresh(root)
            cap=next(c for c in s.load(root/'CAPABILITY-GRAPH.json')['capabilities'] if c['package']=='sqlite3')
            with patch.object(s,'run',side_effect=RuntimeError('SIMULATED bounded failure')),contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(s.verify(cap['id'],root))
            result=s.load(root/'runtime/verifications.json')[cap['id']]
            self.assertEqual(result['state'],'FAILED_CHECK');self.assertTrue(Path(result['evidence']).exists())

    def test_verification_metadata_change_and_age_expire(self):
        env={'id':'e','interpreter':'/fixture/bin/python','prefix':'/fixture','packages':[{'name':'numpy','version':'1','location':'/fixture/lib'}],'state':'INSTALLED','observed_at':s.now(),'signature':'current'}
        v={'e:numpy':{'checked_at':s.now(),'evidence':'/fixture/evidence','state':'FUNCTIONALLY_VERIFIED','signature':'old'}}
        self.assertEqual(s.capabilities([env],[],v,24)[0]['state'],'STALE')
        v['e:numpy']['signature']='current';v['e:numpy']['checked_at']=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=25)).isoformat()
        self.assertEqual(s.capabilities([env],[],v,24)[0]['state'],'STALE')

    def test_external_registry_never_fabricates_current_pass(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'registry.json';s.atomic(path,{'engines':[{'name':'numpy','version':'1','state':'FUNCTIONALLY_VERIFIED','last_verified_at_utc':s.now()}]})
            env={'id':'e','interpreter':'/fixture/bin/python','prefix':'/fixture','packages':[{'name':'numpy','version':'1','location':'/fixture/lib'}],'state':'INSTALLED','observed_at':s.now(),'signature':'current'}
            cap=s.capabilities([env],[],{},24,registries=[{'path':str(path),'interpreter':env['interpreter']}])[0]
            self.assertEqual(cap['state'],'INSTALLED');self.assertTrue(cap['external_evidence'])

    def test_atomic_generations_interruption_recovery_and_tamper(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);fixture_config(root);s.commit(root,files('good'),'good')
            original=s.atomic;calls=[]
            def interrupted(path,value,*args):
                calls.append(path)
                if len(calls)==3:raise OSError('SIMULATED interrupted write')
                return original(path,value,*args)
            with patch.object(s,'atomic',side_effect=interrupted):
                with self.assertRaises(OSError):s.commit(root,files('partial'),'partial')
            self.assertEqual((root/'current').resolve().name,'good')
            with self.assertRaises(ValueError):s.recover(root,'partial')
            s.commit(root,files('new'),'new');s.recover(root,'good')
            self.assertEqual((root/'current').resolve().name,'good');self.assertTrue(s.load(root/'runtime/dirty.json'))
            (root/'generations/new/ENVIRONMENTS.json').write_text('{}')
            with self.assertRaises(ValueError):s.recover(root,'new')
            with self.assertRaises(ValueError):s.recover(root,'../good')

    def test_unmanaged_reports_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/s.NAMES[0]).write_text('unmanaged')
            with self.assertRaises(RuntimeError):s.commit(root,files('one'),'one')
            self.assertEqual((root/s.NAMES[0]).read_text(),'unmanaged')
            self.assertFalse((root/'current').exists())

    def test_single_writer_process_lock(self):
        with tempfile.TemporaryDirectory() as t:
            ctx=multiprocessing.get_context('spawn');ready=ctx.Event();p=ctx.Process(target=hold,args=(t,ready));p.start()
            try:
                self.assertTrue(ready.wait(5))
                with self.assertRaises(RuntimeError):
                    with s.writer(Path(t),seconds=.1):pass
            finally:p.join(5)
            self.assertEqual(p.exitcode,0)
            with s.writer(Path(t),seconds=.1):pass

    def test_dirty_event_during_refresh_survives(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);fixture_config(root);s.mark_dirty(root,'same reason');before=s.load(root/'runtime/dirty.json');original=s.commit
            def notify(root,files,generation):
                s.mark_dirty(root,'same reason');return original(root,files,generation)
            with patch.object(s,'commit',side_effect=notify):quiet_refresh(root)
            after=s.load(root/'runtime/dirty.json');self.assertNotEqual(after['id'],before['id']);self.assertEqual(s.get_status(root)['state'],'STALE')

    def test_invalid_configuration_preserves_generation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);fixture_config(root);old=quiet_refresh(root);(root/'config.json').write_text('{ malformed fixture')
            with self.assertRaises(ValueError):quiet_refresh(root)
            self.assertEqual(s.read_snapshot(root)['generation'],old['generation'])

    def test_conda_native_changes_and_credential_redaction(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);meta=root/'conda-meta';meta.mkdir();p=meta/'fixture.json'
            s.atomic(p,{'name':'libfixture','version':'1','channel':'https://user:password@example.test/t/secret/channel'})
            before=s.signature(str(root/'bin/python'));records,errors=s.conda_metadata(root)
            self.assertFalse(errors);self.assertNotIn('password',records[0]['channel']);self.assertNotIn('/t/secret/',records[0]['channel'])
            s.atomic(p,{'name':'libfixture','version':'2'});self.assertNotEqual(s.signature(str(root/'bin/python')),before)
            changed,_=s.conda_metadata(root);delta=s.changes({'environments':[{'id':'e','conda_packages':records}]},{'environments':[{'id':'e','conda_packages':changed}]})
            self.assertEqual(delta[0]['kind'],'CHANGED')

    def test_inherited_environment_metadata_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base=root/'base';venv=root/'env';venv.mkdir();(base/'bin').mkdir(parents=True)
            (venv/'pyvenv.cfg').write_text('home = '+str(base/'bin')+'\ninclude-system-site-packages = true\n')
            m=base/'lib/python3.12/site-packages/demo.dist-info';m.mkdir(parents=True);(m/'METADATA').write_text('Name: demo\nVersion: 1\n')
            before=s.signature(str(venv/'bin/python'));(m/'METADATA').write_text('Name: demo\nVersion: 2\n')
            self.assertNotEqual(before,s.signature(str(venv/'bin/python')))

    def test_bounded_timeout_output_and_memory(self):
        with self.assertRaises(RuntimeError):s.run([sys.executable,'-c','import time;time.sleep(5)'],.2)
        with self.assertRaises(RuntimeError):s.run([sys.executable,'-c','import sys;sys.stdout.write("x"*9000000)'],3)
        output=s.run([sys.executable,'-c','try:\n a=bytearray(4*1024**3)\nexcept MemoryError:\n print("GUARD_OK")'],3)
        self.assertIn('GUARD_OK',output)

    def test_actual_disposable_local_wheel_install_upgrade_remove(self):
        # Requires the test runner's existing pip only; no downloads/build dependencies.
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);subprocess.run([sys.executable,'-m','venv','--without-pip',str(root/'env')],check=True,timeout=30,capture_output=True)
            py=str(root/'env/bin/python');before=s.inspect_env(py,None,True)
            for version in ['1.0','2.0']:
                wheel=root/('sentinel_fixture-'+version+'-py3-none-any.whl');meta='sentinel_fixture-'+version+'.dist-info/'
                entries={'sentinel_fixture.py':('VERSION='+repr(version)+'\n').encode(),meta+'METADATA':('Metadata-Version: 2.1\nName: sentinel-fixture\nVersion: '+version+'\n').encode(),meta+'WHEEL':b'Wheel-Version: 1.0\nGenerator: sentinel-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
                records=[f'{k},sha256={base64.urlsafe_b64encode(hashlib.sha256(v).digest()).decode().rstrip("=")},{len(v)}' for k,v in entries.items()];records.append(meta+'RECORD,,');entries[meta+'RECORD']='\n'.join(records).encode()
                with zipfile.ZipFile(wheel,'w') as z:
                    for name,content in entries.items():z.writestr(name,content)
                subprocess.run([sys.executable,'-m','pip','--python',py,'install','--no-index','--no-deps','--upgrade',str(wheel)],check=True,timeout=40,capture_output=True)
                after=s.inspect_env(py,before,False);self.assertTrue(any(p['name']=='sentinel-fixture' and p['version']==version for p in after['packages']))
                self.assertTrue(any(x['id'].endswith(':sentinel-fixture') and x['kind']==('ADDED' if version=='1.0' else 'CHANGED') for x in s.changes({'environments':[before]},{'environments':[after]})));before=after
            subprocess.run([sys.executable,'-m','pip','--python',py,'uninstall','-y','sentinel-fixture'],check=True,timeout=40,capture_output=True)
            after=s.inspect_env(py,before,False);self.assertTrue(any(x['id'].endswith(':sentinel-fixture') and x['kind']=='REMOVED' for x in s.changes({'environments':[before]},{'environments':[after]})))

if __name__=='__main__':unittest.main(verbosity=2)
