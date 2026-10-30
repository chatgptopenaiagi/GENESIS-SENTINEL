"""Optional MOBILE-4 Science/Joomla adapters with explicitly configured roots.

Disabled by default. Fixed original loopback ports and launcher names are retained;
these adapters require a compatible deployment and are not portable application installers.
"""
from __future__ import annotations
import base64, datetime, errno, json, os, signal, subprocess, threading, time, sys
from .config import state_dir
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
B=state_dir();LAB=B/'disabled-science';JOOMLA=B/'disabled-joomla'
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
PY=sys.executable;OPENER=build_opener(ProxyHandler({}),NoRedirect());CACHE={};CACHE_LOCK=threading.Lock()
THREADS={k:'1' for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']}
SCRIPTS={}
def configure(root):
 global B,LAB,JOOMLA,SCRIPTS
 B=Path(root);cfg=read(B/'config.json');SCRIPTS={}
 science_value=cfg.get('science_root');joomla_value=cfg.get('joomla_root')
 LAB=Path(science_value) if isinstance(science_value,str) and Path(science_value).is_absolute() else B/'disabled-science'
 JOOMLA=Path(joomla_value) if isinstance(joomla_value,str) and Path(joomla_value).is_absolute() else B/'disabled-joomla'
 if cfg.get('enable_deployment_adapters') is not True:return
 if LAB.is_absolute() and LAB.is_dir() and cfg.get('science_root'):
  SCRIPTS['science']={'start':str(LAB/'START-LAB.sh'),'stop':str(LAB/'STOP-LAB.sh')}
 if JOOMLA.is_absolute() and JOOMLA.is_dir() and cfg.get('joomla_root'):
  SCRIPTS['joomla']={'start':str(JOOMLA/'START-SERVICES.sh'),'stop':str(JOOMLA/'STOP-SERVICES.sh')}
  SCRIPTS['panel']={'start':str(JOOMLA/'CONTROL-PANEL.sh')}
 invalidate()
def allowed(service,action):
 return service in SCRIPTS and (action in SCRIPTS[service] or action=='restart' and service in ['science','joomla'])

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(path):
 try:return json.loads(Path(path).read_text())
 except (OSError,ValueError):return {}
def identity(pid):
 try:
  p=Path('/proc')/str(int(pid));a=(p/'stat').read_text().rsplit(')',1)[1].split();args=[x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x]
  if not args:return {}
  return {'pid':int(pid),'start':a[19],'args':args,'cwd':str((p/'cwd').resolve())}
 except (OSError,ValueError,IndexError):return {}
def pid_identity(path):
 try:return identity(int(Path(path).read_text().strip()))
 except (OSError,ValueError):return {}
def science_identity():
 i=pid_identity(LAB/'runtime/lab.pid');args=i.get('args',[])
 return i if str(LAB/'server.py') in args or ('server.py' in args and i.get('cwd')==str(LAB)) else {}
def jupyter_identity():
 r=read(B/'private/jupyter-process.json');i=identity(r.get('pid',0));old=r.get('identity',{})
 return i if i and i.get('start')==old.get('start') and i.get('args')==old.get('cmd') and str(B/'private/jupyter_server_config.json') in i['args'] else {}
def joomla_identity():
 i=pid_identity(JOOMLA/'runtime/httpd.pid');return i if str(JOOMLA/'config/httpd.conf') in i.get('args',[]) else {}
def database_identity():
 i=pid_identity(JOOMLA/'runtime/mysql.pid');return i if '--datadir='+str(JOOMLA/'private/mysql') in i.get('args',[]) and '--socket='+str(JOOMLA/'runtime/mysql.sock') in i.get('args',[]) else {}
def panel_identity():
 i=pid_identity(JOOMLA/'runtime/panel.pid');args=i.get('args',[])
 return i if (str(JOOMLA/'dashboard/server.py') in args or ('dashboard/server.py' in args and i.get('cwd')==str(JOOMLA))) else {}
def basic(path):
 c=read(path)
 if not c.get('username') or not c.get('password'):return {}
 return {'Authorization':'Basic '+base64.b64encode((c['username']+':'+c['password']).encode()).decode()}
def http(url,headers=None,json_body=False):
 try:
  with OPENER.open(Request(url,headers=headers or {}),timeout=3) as r:
   data=r.read(2_000_000) if json_body else b''
   return r.status,json.loads(data) if json_body else None,None
 except HTTPError as e:
  code=e.code;e.close();return code,None,None
 except (URLError,OSError,ValueError) as e:
  reason=getattr(e,'reason',e);return None,None,'refused' if getattr(reason,'errno',None)==errno.ECONNREFUSED else 'inconclusive'
def jupyter_url():
 r=read(B/'private/jupyter-process.json');url=r.get('url','http://127.0.0.1:8888/lab')
 try:
  parts=urlsplit(url)
  valid=parts.scheme=='http' and parts.hostname=='127.0.0.1' and parts.port in range(8888,8908) and not parts.username and not parts.password and parts.path=='/lab' and not parts.query and not parts.fragment
 except (TypeError,ValueError):valid=False
 return url if valid else 'http://127.0.0.1:8888/lab'
def jupyter_headers():
 token=read(B/'private/jupyter-secret.json').get('token');return {'Authorization':'token '+token} if token else {}
def _service(service):
 url={'science':'http://127.0.0.1:8090/','joomla':'http://127.0.0.1:8080/','panel':'http://127.0.0.1:8081/','jupyter':jupyter_url()}[service]
 funcs={'science':science_identity,'jupyter':jupyter_identity,'joomla':joomla_identity,'panel':panel_identity}
 owned=bool(funcs[service]());busy=False;checked=url
 if service=='science' and owned:headers=basic(LAB/'private/access.json');checked=url+'api/jobs';code,data,err=http(checked,headers,True);busy=bool(data and data.get('active'))
 elif service=='jupyter' and owned:checked=url.removesuffix('/lab')+'/api/kernels';code,data,err=http(checked,jupyter_headers(),True);busy=isinstance(data,list) and any(k.get('execution_state')=='busy' for k in data)
 elif service=='panel' and owned:code,data,err=http(url,basic(JOOMLA/'private/mobile-panel.json'))
 else:code,data,err=http(url)
 if owned and code==200:state='BUSY' if busy else 'RUNNING'
 elif code is None and err=='refused' and not owned:state='STOPPED'
 else:state='UNKNOWN'
 names={'science':'GENESIS Science Lab','jupyter':'JupyterLab','joomla':'Joomla website','panel':'Joomla Control Panel'}
 details={'science':'Existing bounded scientific dashboard; stop/restart is blocked while a calculation runs.','jupyter':'Existing Anaconda workbench; stop/restart is blocked while a kernel is busy. Idle sessions close on stop.','joomla':'Controls the existing website and its database together. The control panel remains running.','panel':'The existing panel supports startup; no separate verified stop launcher is available.'}
 allowed=[]
 if state=='STOPPED':allowed=['start']
 elif owned and state in ['RUNNING','BUSY']:
  allowed=['start'] if service=='panel' else (['start'] if busy else ['start','stop','restart'])
 # Expose a running but unauthenticated service only as an observation, never assume ownership.
 if not owned and code is not None:details[service]+=' A listener exists without matching owned process identity; controls are disabled.'
 return {'id':service,'name':names[service],'url':url,'state':state,'label':{'RUNNING':'Running','BUSY':'Calculation active','STOPPED':'Stopped','UNKNOWN':'Needs a check'}[state],'detail':details[service],'http':code,'owned':owned,'actions':allowed,'observed_at':now(),'verification_note':'Live process identity and local HTTP check; scientific verification is recorded separately.'}
def get_services(force=False):
 # These legacy adapters are opt-in and retain fixed original localhost ports.
 return [_service(x) for x in SCRIPTS]
def invalidate():
 with CACHE_LOCK:CACHE.clear()
def _guard(service,action):
 if service not in SCRIPTS:raise ValueError('Unknown managed application')
 if action=='restart' and service not in ['science','joomla']:raise ValueError('Restart is unavailable for this application')
 if action!='restart' and action not in SCRIPTS[service]:raise ValueError('This action is unavailable')
 if service=='sentinel':return
 status=_service(service)
 if status['state']=='UNKNOWN':raise RuntimeError('Service identity or readiness is uncertain. No existing process was changed.')
 if action in ['stop','restart']:
  if status['state']=='STOPPED':
   if action=='stop':return
  elif not status['owned']:raise RuntimeError('Owned process identity does not match. Nothing was stopped.')
  if status['state']=='BUSY':raise RuntimeError('An active calculation is running. Wait until it finishes before stopping this application.')
 if service=='joomla':
  # Existing scripts use PID and socket controls; ensure both identify this project first.
  for path,owner in [(JOOMLA/'runtime/httpd.pid',joomla_identity()),(JOOMLA/'runtime/mysql.pid',database_identity())]:
   if pid_identity(path) and not owner:raise RuntimeError('A Joomla process identifier was reused. Nothing was changed.')
  panel=_service('panel')
  if action in ['start','restart'] and panel['state']=='UNKNOWN':raise RuntimeError('The existing panel listener has uncertain ownership; startup was not attempted.')
def bounded_script(argv,timeout=110):
 env=os.environ.copy();env.update(THREADS);env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
 p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,env=env,cwd=B)
 try:p.wait(timeout=timeout)
 except subprocess.TimeoutExpired:
  os.killpg(p.pid,signal.SIGTERM)
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  raise RuntimeError('The existing launcher exceeded its time limit. Check fresh service status before retrying.')
 if p.returncode:raise RuntimeError('The existing launcher reported a failure. Earlier evidence is preserved; check service status and its private log.')
def confirm_result(service,action,timeout=12):
 deadline=time.monotonic()+timeout
 while True:
  status=_service(service)
  ready=status['state']=='STOPPED' if action=='stop' else status['owned'] and status['state'] in ['RUNNING','BUSY']
  if service=='joomla':ready=ready and (bool(database_identity()) if action!='stop' else not pid_identity(JOOMLA/'runtime/mysql.pid'))
  if ready:return
  if time.monotonic()>=deadline:raise RuntimeError('The launcher returned, but the requested application state was not verified. Check fresh service status before retrying.')
  time.sleep(.3)
def perform(service,action):
 _guard(service,action)
 if service=='sentinel':bounded_script([SCRIPTS[service]['refresh'],'refresh','--quick'],60)
 elif action=='restart':
  bounded_script([SCRIPTS[service]['stop']]);confirm_result(service,'stop');_guard(service,'start');bounded_script([SCRIPTS[service]['start']]);confirm_result(service,'start')
 else:bounded_script([SCRIPTS[service][action]]);confirm_result(service,action)
 invalidate()
 return 'Software records refreshed.' if service=='sentinel' else {'start':'Application started or reused.','stop':'Application stopped.','restart':'Application restarted.'}[action]
