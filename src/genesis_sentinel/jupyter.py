"""Owned, loopback-only Jupyter lifecycle. Secrets never enter public snapshots."""
import argparse, fcntl, html, json, os, secrets, signal, socket, subprocess, sys, time, urllib.request, urllib.error
from .config import state_dir
from pathlib import Path
from datetime import datetime, timezone
B=state_dir();P=B/'private';NOTEBOOKS=B/'notebooks'
def configure(root):
 global B,P,NOTEBOOKS
 B=Path(root);P=B/'private';NOTEBOOKS=B/'notebooks'
def storage():
 B.mkdir(parents=True,exist_ok=True,mode=0o700);P.mkdir(exist_ok=True,mode=0o700);P.chmod(0o700)
def interpreter(explicit=None):
 cfg=read(B/'config.json');value=explicit or cfg.get('jupyter_interpreter')
 if not value:
  inventory=read(B/'SOFTWARE-INVENTORY.json')
  value=next((e.get('interpreter') for e in inventory.get('environments',[]) if e.get('state')=='INSTALLED' and any(p.get('name','').lower()=='jupyterlab' for p in e.get('packages',[]))),None)
 if not isinstance(value,str) or not Path(value).is_absolute() or not Path(value).is_file():
  raise SystemExit('No registered JupyterLab interpreter. Register a Python environment that already has JupyterLab or pass --interpreter /absolute/python. Nothing was installed.')
 return value
def now():return datetime.now(timezone.utc).isoformat()
def write(p,obj,mode=0o600):
 p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 t=p.with_name(p.name+'.tmp-'+str(os.getpid()))
 with t.open('w',encoding='utf-8') as f:
  f.write(json.dumps(obj,indent=2)+'\n');f.flush();os.fsync(f.fileno())
 t.chmod(mode);os.replace(t,p)
 try:
  fd=os.open(p.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 except OSError:pass
def read(p):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return {}
def identity(pid):
 try:
  a=Path('/proc/%s/stat'%pid).read_text().rsplit(')',1)[1].split();cmd=Path('/proc/%s/cmdline'%pid).read_bytes().split(b'\0');return {'start':a[19],'cmd':[c.decode(errors='replace') for c in cmd if c]}
 except (OSError,IndexError):return {}
def owned(r):
 i=identity(r.get('pid',0));return bool(i and i==r.get('identity') and str(P/'jupyter_server_config.json') in i['cmd'])
def request(r,path='/api/status',auth=True):
 req=urllib.request.Request(r['url'].removesuffix('/lab').rstrip('/')+path,headers={'Authorization':'token '+read(P/'jupyter-secret.json').get('token','')} if auth else {})
 with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=3) as f:return f.status,json.load(f)
def status():
 r=read(P/'jupyter-process.json');alive=owned(r);ok=False;kernels=[]
 if alive:
  try:
   code,_=request(r);ok=code==200
   _,k=request(r,'/api/kernelspecs');kernels=[{'id':n,'display_name':v['spec']['display_name'],'interpreter':v['spec']['argv'][0],'source_environment':v['spec'].get('metadata',{}).get('source_environment')} for n,v in k['kernelspecs'].items()]
  except (OSError,ValueError):pass
 # Kernel registration and live HTTP are not scientific operation verification.
 verified={}
 all_verified=False
 out={'observed_at':now(),'service_state':'RUNNING' if ok else ('UNKNOWN' if alive else 'STOPPED'),'verification_scope':'Authenticated HTTP API; kernel presence is not proof of notebook cell execution.','kernel_verification':{k['id']:verified.get(k['id'],{'status':'UNKNOWN'}) for k in kernels},'last_functional_verification_at':max((x.get('started_at','') for x in verified.values()),default=None),'state':('FUNCTIONALLY_VERIFIED' if all_verified else 'INSTALLED') if ok else ('UNKNOWN' if alive else 'STOPPED'),'url':r.get('url','http://127.0.0.1:8888/lab'),'authenticated':ok,'interpreter':r.get('interpreter'),'root_dir':str(NOTEBOOKS),'kernels':kernels,'access_helper':'genesis-sentinel-jupyter access','limitations':['Android may stop processes; status is a fresh local authenticated HTTP observation.','Notebook code executes with the operator account; one-thread kernels, bounded demonstrations.']}
 write(B/'JUPYTER-STATUS.json',out)
 if NOTEBOOKS.exists():
  parts=[(B/n).read_text() for n in ['CURRENT-STATUS.md','SESSION-BRIEF.md'] if (B/n).exists()]
  if parts:(NOTEBOOKS/'Sentinel-Report.html').write_text('<!doctype html><meta charset="utf-8"><title>Arch Sentinel</title><style>body{font:16px system-ui;max-width:900px;margin:30px auto;padding:15px}pre{white-space:pre-wrap}</style><h1>Arch Sentinel software report</h1><pre>'+html.escape('\n\n'.join(parts))+'</pre>')
 return out

def start(explicit=None):
 storage()
 s=status()
 if s['authenticated']:return s
 r=read(P/'jupyter-process.json')
 if owned(r):raise SystemExit('Owned Jupyter process is not ready; inspect private/jupyter.log. No duplicate started.')
 PYTHON=interpreter(explicit)
 NOTEBOOKS.mkdir(exist_ok=True)
 port=None
 for candidate in range(8888,8908):
  with socket.socket() as so:
   so.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
   try:so.bind(('127.0.0.1',candidate));port=candidate;break
   except OSError:continue
 if port is None:raise SystemExit('No available local Jupyter port in 8888..8907; no process stopped.')
 secret=read(P/'jupyter-secret.json') or {'token':secrets.token_urlsafe(32)};write(P/'jupyter-secret.json',secret,0o600)
 cfg={'ServerApp':{'ip':'127.0.0.1','port':port,'port_retries':0,'open_browser':False,'root_dir':str(NOTEBOOKS),'allow_root':os.geteuid()==0,'allow_remote_access':False,'disable_check_xsrf':False,'shutdown_no_activity_timeout':0},'IdentityProvider':{'token':secret['token']},'MappingKernelManager':{'cull_idle_timeout':1800,'cull_interval':120,'cull_connected':False,'cull_busy':False}}
 conf=P/'jupyter_server_config.json';write(conf,cfg,0o600)
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',JUPYTER_RUNTIME_DIR=str(P/'jupyter-runtime'))
 (P/'jupyter-runtime').mkdir(mode=0o700,exist_ok=True)
 with (P/'jupyter.log').open('ab') as log:
  (P/'jupyter.log').chmod(0o600)
  child=subprocess.Popen([PYTHON,'-I','-m','jupyterlab','--config',str(conf)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env,cwd=NOTEBOOKS)
 record_identity={}
 for _ in range(30):
  record_identity=identity(child.pid)
  if str(conf) in record_identity.get('cmd',[]):break
  if child.poll() is not None:break
  time.sleep(.1)
 r={'pid':child.pid,'identity':record_identity,'interpreter':PYTHON,'url':'http://127.0.0.1:%s/lab'%port,'started_at':now()};write(P/'jupyter-process.json',r,0o600)
 for _ in range(50):
  try:
   s=status()
   if s['authenticated']:return s
  except OSError:pass
  if child.poll() is not None:break
  time.sleep(1)
 raise SystemExit('Jupyter did not become ready; inspect private/jupyter.log (contains private access information).')
def stop():
 r=read(P/'jupyter-process.json')
 if owned(r):
  try:
   _,kernels=request(r,'/api/kernels')
   if any(k.get('execution_state')=='busy' for k in kernels):raise SystemExit('A notebook kernel is busy. Wait and save work before stopping.')
  except OSError:raise SystemExit('Jupyter readiness is uncertain; no process stopped.')
  os.killpg(r['pid'],signal.SIGTERM)
  for _ in range(30):
   if not owned(r):break
   time.sleep(.2)
  if owned(r):raise SystemExit('Jupyter still stopping; no SIGKILL sent.')
 elif identity(r.get('pid',0)):raise SystemExit('PID belongs to another process; refusing to stop it.')
 return status()
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state-dir');p.add_argument('--interpreter');p.add_argument('command',choices=['start','stop','status','access']);a=p.parse_args(argv)
 configure(state_dir(a.state_dir));storage()
 with (P/'jupyter.lock').open('a') as lock:
  deadline=time.monotonic()+15
  while True:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
   except BlockingIOError:
    if time.monotonic()>deadline:raise SystemExit('Jupyter lifecycle busy; retry status shortly.')
    time.sleep(.1)
  if a.command=='access':
   s=status()
   if not s['authenticated']:raise SystemExit('Jupyter stopped; run genesis-sentinel-jupyter start first.')
   if not sys.stdout.isatty():raise SystemExit('Access helper requires an operator terminal to avoid recording tokens in logs.')
   print(s['url']+'?token='+read(P/'jupyter-secret.json')['token']);return
  s=start(a.interpreter) if a.command=='start' else globals()[a.command]();print(s['state']+': '+s['url']);print('Kernels: '+', '.join(k['display_name'] for k in s['kernels']))
if __name__=='__main__':main()
