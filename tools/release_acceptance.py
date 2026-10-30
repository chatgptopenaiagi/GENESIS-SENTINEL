#!/usr/bin/env python3
"""Install the actual wheel into a disposable venv and test its public interfaces.

No host inventories, credentials or operational files are copied into results.
The mpmath package used here is an intentionally failing synthetic test fixture.
"""
import argparse,csv,datetime,hashlib,io,json,os,platform,subprocess,sys,tempfile,time,zipfile
from pathlib import Path

def fixture_wheel(folder,version):
 name='mpmath';info=f'{name}-{version}.dist-info';path=folder/f'{name}-{version}-py3-none-any.whl'
 files={f'{name}/__init__.py':b'raise RuntimeError("intentional synthetic probe failure")\n',f'{info}/METADATA':f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n'.encode(),f'{info}/WHEEL':b'Wheel-Version: 1.0\nGenerator: genesis-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
 with zipfile.ZipFile(path,'w') as z:
  for k,v in files.items():z.writestr(k,v)
  rows=io.StringIO();w=csv.writer(rows);w.writerows((k,'','') for k in files);w.writerow((f'{info}/RECORD','',''));z.writestr(f'{info}/RECORD',rows.getvalue())
 return path

def main():
 p=argparse.ArgumentParser();p.add_argument('--wheel',required=True);p.add_argument('--output',required=True);a=p.parse_args();wheel=Path(a.wheel).resolve()
 results={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'platform':{'system':platform.system(),'machine':platform.machine(),'python':platform.python_version()},'artifact':{'name':wheel.name,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest()},'passed':{},'failed':{},'skipped':{},'scope':'Actual wheel installed without dependencies into a clean temporary venv; synthetic configuration/project/distribution fixtures; no user data published.'}
 def check(name,fn):
  try:results['passed'][name]=fn() or True;print('PASS',name,flush=True)
  except Exception as e:results['failed'][name]=type(e).__name__+': '+str(e)[-1000:];print('FAIL',name,results['failed'][name],flush=True)
 with tempfile.TemporaryDirectory(prefix='genesis-release-') as tmp:
  root=Path(tmp);venv=root/'venv';state=root/'state';project=root/'project';project.mkdir();(project/'pyproject.toml').write_text('[project]\nname="synthetic-project"\nversion="0.0.0"\n')
  env=os.environ.copy()
  for k in ['PYTHONPATH','PYTHONHOME','GENESIS_SENTINEL_HOME','CONDA_PREFIX','CONDA_DEFAULT_ENV']:env.pop(k,None)
  env.update(PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONNOUSERSITE='1',XDG_STATE_HOME=str(root/'xdg'),GENESIS_SENTINEL_HOME=str(state))
  def run(args,okay=0,timeout=90):
   r=subprocess.run([str(x) for x in args],cwd=root,env=env,capture_output=True,text=True,timeout=timeout)
   if okay is not None and r.returncode!=okay:raise AssertionError(f'exit {r.returncode}: '+(r.stderr+r.stdout)[-1200:])
   return r
  run([sys.executable,'-m','venv',venv]);py=venv/'bin/python';cli=venv/'bin/genesis-sentinel'
  def install():
   run([py,'-m','pip','install','--no-deps','--no-index',wheel]);v=run([py,'-c','import genesis_sentinel; print(genesis_sentinel.__file__)']).stdout.strip();assert str(venv) in v and 'site-packages' in v;return {'installed_from_wheel':True,'isolated_site_packages':True}
  check('clean_wheel_installation',install)
  if not cli.exists():results['failed']['cli']='Installation did not create console script'
  else:
   check('cli_startup',lambda:run([cli,'--help']).returncode==0)
   run([cli,'init'])
   config=json.loads((state/'config.json').read_text());config.update(interpreters=[str(py)],conda_roots=[],conda_registry_files=[],projects=[{'name':'Synthetic project','path':str(project),'owner_context':'current-user'}],extra_roots=[],tool_roots=[],collect_arch_packages=False,services=[])
   (state/'config.json').write_text(json.dumps(config))
   def snapshot():return json.loads((state/'SOFTWARE-INVENTORY.json').read_text())
   def graph():return json.loads((state/'CAPABILITY-GRAPH.json').read_text())
   def discover():
    run([cli,'refresh','--full']);d=snapshot();assert not d['errors'],d['errors'];assert any(e['interpreter']==str(py) for e in d['environments']);assert json.loads((state/'PROJECT-MAP.json').read_text())['projects'];return {'errors':0,'registered_interpreter_detected':True,'registered_project_detected':True}
   check('software_and_environment_discovery',discover)
   def verified_query():
    cap=next(c for c in graph()['capabilities'] if c.get('package')=='sqlite3');run([cli,'verify',cap['id']]);cap=next(c for c in graph()['capabilities'] if c.get('package')=='sqlite3');assert cap['state']=='FUNCTIONALLY_VERIFIED';assert Path(cap['evidence']).is_file();return {'bounded_sqlite_query_verified':True,'evidence_retained':True}
   check('real_standard_library_capability_verification',verified_query)
   def incremental():
    run([cli,'refresh','--quick']);d=snapshot();assert all(e.get('cached') for e in d['environments']);assert d['changes_count']==0,d['changes_count'];return {'cached':True,'changes':0}
   check('incremental_unchanged_refresh',incremental)
   def installed():
    f=fixture_wheel(root,'0.0.1');run([py,'-m','pip','install','--no-deps','--no-index',f]);run([cli,'refresh','--quick']);cap=next(c for c in graph()['capabilities'] if c.get('package')=='mpmath');assert cap['state']=='INSTALLED';return {'fixture_detected':True,'capability_registered':True,'not_claimed_verified':True}
   check('installation_and_capability_registration',installed)
   def expected_failure():
    cap=next(c for c in graph()['capabilities'] if c.get('package')=='mpmath');r=run([cli,'verify',cap['id']],okay=None);assert r.returncode!=0;cap=next(c for c in graph()['capabilities'] if c.get('package')=='mpmath');assert cap['state']=='FAILED_CHECK';assert Path(cap['evidence']).is_file();return {'intentional_fixture_failure_retained':True}
   check('failed_verification_retains_evidence',expected_failure)
   def upgraded():
    run([py,'-m','pip','install','--no-deps','--no-index',fixture_wheel(root,'0.0.2')]);run([cli,'refresh','--quick']);d=snapshot();assert any(x['name']=='mpmath' and x['version']=='0.0.2' for e in d['environments'] for x in e['packages']);events=[json.loads(x) for x in (state/'CHANGES.jsonl').read_text().splitlines()];assert any(c.get('kind')=='CHANGED' and (c.get('before') or {}).get('version')=='0.0.1' and (c.get('after') or {}).get('version')=='0.0.2' for event in events for c in event['changes']);return {'new_version_detected':True,'before_after_audit_retained':True}
   check('version_change_detection',upgraded)
   def removed():
    run([py,'-m','pip','uninstall','-y','mpmath']);run([cli,'refresh','--quick']);assert not any(x['name']=='mpmath' for e in snapshot()['environments'] for x in e['packages']);changes=[json.loads(x) for x in (state/'CHANGES.jsonl').read_text().splitlines()];assert any(c.get('kind')=='REMOVED' and 'mpmath' in c['id'] for row in changes for c in row['changes']);return {'removal_detected':True}
   check('removal_detection',removed)
   def concurrency():
    ready=root/'writer-ready';script='from genesis_sentinel import core; from pathlib import Path; import time\nwith core.writer(Path('+repr(str(state))+')):\n Path('+repr(str(ready))+').touch()\n time.sleep(8)\n'
    owner=subprocess.Popen([str(py),'-c',script],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
     deadline=time.monotonic()+10
     while not ready.exists() and time.monotonic()<deadline:time.sleep(.05)
     assert ready.exists();before=(state/'current').resolve();r=run([cli,'refresh','--quick'],okay=None);assert r.returncode!=0;assert (state/'current').resolve()==before;assert (state/'runtime/last-error.json').exists();return {'second_writer_rejected':True,'committed_generation_preserved':True}
    finally:owner.terminate();owner.wait(timeout=10)
   check('concurrent_writer_protection',concurrency)
   def recovery():
    good=(state/'current').resolve().name;interrupted=state/'generations'/'synthetic-interrupted';interrupted.mkdir();(interrupted/'SOFTWARE-INVENTORY.json').write_text('{}');r=run([cli,'recover',interrupted.name],okay=None);assert r.returncode!=0;assert (state/'current').resolve().name==good
    run([cli,'recover',good]);run([cli,'refresh','--quick']);assert not snapshot()['errors'];return {'incomplete_generation_rejected':True,'valid_generation_recovered':True,'refresh_after_recovery':True}
   check('interrupted_update_recovery',recovery)
   def awareness():
    guidance=root/'AGENTS.md';guidance.write_text('Operator-owned text.\n');wrapper=root/'session-wrapper';original=root/'original-tool';original.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n');original.chmod(0o755)
    run([cli,'integrate','--guidance',guidance,'--launcher',wrapper,'--original',original]);text=guidance.read_text();assert 'SESSION-BRIEF.md' in text and str(state) in text
    result=run([wrapper,'--version','literal argument']);assert 'literal argument' in result.stdout
    prior=(state/'current').resolve();run([wrapper,'literal argument']);assert (state/'current').resolve()!=prior
    fresh=run([py,'-c','from pathlib import Path; import os,json; p=Path(os.environ["GENESIS_SENTINEL_HOME"]); text=(p/"SESSION-BRIEF.md").read_text(); graph=json.loads((p/"CAPABILITY-GRAPH.json").read_text()); assert graph["generation"] in text; assert graph["capabilities"]; print("aware")']);assert 'aware' in fresh.stdout
    run([cli,'unintegrate']);assert guidance.read_text()=='Operator-owned text.\n';assert not wrapper.exists();return {'guidance_created':True,'fresh_process_reads_brief_and_graph':True,'wrapper_refreshes_generation':True,'literal_arguments_preserved':True,'rollback_preserves_user_text':True,'actual_codex_not_launched':True}
   check('fresh_process_awareness_and_integration_rollback',awareness)
   def uninstall():
    saved=(state/'SOFTWARE-INVENTORY.json').read_bytes();run([py,'-m','pip','uninstall','-y','genesis-arch-sentinel']);assert not cli.exists();assert (state/'SOFTWARE-INVENTORY.json').read_bytes()==saved;return {'console_script_removed':True,'inventory_retained':True}
   check('package_uninstall_preserves_state',uninstall)
 results['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({'passed':len(results['passed']),'failed':len(results['failed']),'skipped':len(results['skipped'])}),flush=True);return bool(results['failed'])
if __name__=='__main__':raise SystemExit(main())
