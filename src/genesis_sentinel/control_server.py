"""Authenticated localhost interface over existing Sentinel records and launchers."""
from __future__ import annotations
import argparse, base64, datetime, fcntl, hashlib, hmac, html, json, os, secrets, signal, threading, time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote
from . import control_services as services
from .config import state_dir
CODE=Path(__file__).resolve().parent;B=state_dir();P=B/'private/control';R=B/'runtime';STORE_LOCK=threading.RLock();ACTION_LOCK=threading.Lock();AUTH_FAILURES={'count':0,'until':0};ACTIVE=None
STATIC={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
def configure(root):
 global B,P,R
 B=Path(root);P=B/'private/control';R=B/'runtime';services.configure(B)

def setup_storage():
 B.mkdir(parents=True,exist_ok=True,mode=0o700);P.mkdir(parents=True,exist_ok=True,mode=0o700);P.chmod(0o700);R.mkdir(exist_ok=True,mode=0o700)

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p,default=None):
 try:return json.loads(Path(p).read_text())
 except (OSError,ValueError):return {} if default is None else default

def atomic(p,obj,mode=0o600):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);tmp=p.with_name('.'+p.name+'-'+secrets.token_hex(8)+'.tmp')
 with tmp.open('x',encoding='utf-8') as f:f.write(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');f.flush();os.fsync(f.fileno())
 tmp.chmod(mode);os.replace(tmp,p)
def access():
 setup_storage()
 with STORE_LOCK:
  p=P/'access.json'
  if not p.exists():
   pw=secrets.token_urlsafe(24);salt=secrets.token_hex(16);atomic(p,{'username':'genesis','password':pw,'salt':salt,'hash':hashlib.scrypt(pw.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex(),'csrf':secrets.token_urlsafe(32)})
  p.chmod(0o600);return read(p)
def valid_credentials(user,password):
 c=access()
 try:return isinstance(user,str) and isinstance(password,str) and len(password)<=256 and hmac.compare_digest(user.encode(),c['username'].encode()) and hmac.compare_digest(hashlib.scrypt(password.encode(),salt=c['salt'].encode(),n=16384,r=8,p=1).hex(),c['hash'])
 except (ValueError,KeyError):return False

def log_action(record):
 # Safe public audit: fixed service/action IDs and generic result, never subprocess stdout.
 with STORE_LOCK:
  with (R/'control-actions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())

def action_worker(job):
 global ACTIVE
 try:
  job.update(status='running',started_at=now(),message='Using the existing application launcher.');atomic(R/('control-action-'+job['id']+'.json'),job,0o644);log_action(dict(job))
  try:message=services.perform(job['service'],job['action']);job.update(status='succeeded',message=message)
  except (Exception,SystemExit) as e:job.update(status='failed',message=str(e)[:400])
  job.update(finished_at=now());atomic(R/('control-action-'+job['id']+'.json'),job,0o644);log_action(dict(job))
 finally:ACTIVE=None;ACTION_LOCK.release()

def start_action(service,action):
 global ACTIVE
 # Reject unknown dispatch before starting a worker; actual ownership/busy guard rechecks inside worker.
 if not services.allowed(service,action):raise ValueError('Unsupported application or action')
 if not ACTION_LOCK.acquire(blocking=False):raise RuntimeError('Another management action is running. Wait for it to finish.')
 job={'id':secrets.token_hex(12),'service':service,'action':action,'status':'queued','created_at':now(),'message':'Action queued.'}
 try:
  ACTIVE=job['id'];atomic(R/('control-action-'+job['id']+'.json'),job,0o644);log_action(dict(job));threading.Thread(target=action_worker,args=(job,),daemon=True).start();return dict(job)
 except BaseException:
  ACTIVE=None;ACTION_LOCK.release();raise


class Handler(BaseHTTPRequestHandler):
 server_version='GenesisSentinelLocal'
 def setup(self):super().setup();self.connection.settimeout(10)
 def log_message(self,*args):pass
 @property
 def url(self):return self.server.control_url
 def send(self,code,body,kind='application/json; charset=utf-8',extra=None):
  if not isinstance(body,bytes):body=(body if isinstance(body,str) else json.dumps(body,ensure_ascii=False,allow_nan=False)).encode()
  self.send_response(code)
  headers={'Content-Type':kind,'Content-Length':str(len(body)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"}
  headers.update(extra or {})
  for k,v in headers.items():self.send_header(k,v)
  self.end_headers()
  try:self.wfile.write(body)
  except (BrokenPipeError,ConnectionResetError):pass
 def local(self):
  if self.client_address[0]!='127.0.0.1' or self.headers.get('Host') not in [urlsplit(self.url).netloc,'localhost:'+str(self.server.server_port)]:self.send(403,{'error':'Local dashboard access only.'});return False
  if '..' in unquote(urlsplit(self.path).path).split('/') or '\\' in unquote(urlsplit(self.path).path):self.send(404,{'error':'Page not found.'});return False
  return True
 def session(self):
  auth=self.headers.get('Authorization','')
  if auth.startswith('Basic '):
   try:
    user,pw=base64.b64decode(auth[6:],validate=True).decode().split(':',1)
    if valid_credentials(user,pw):return {'csrf':access()['csrf'],'basic':True}
   except (ValueError,UnicodeError):pass
  try:cookie=SimpleCookie(self.headers.get('Cookie',''));token=cookie.get('genesis_release_control');token=token.value if token else None
  except Exception:return None
  if not token or len(token)>128:return None
  with STORE_LOCK:
   sessions=read(P/'sessions.json');s=sessions.get(hashlib.sha256(token.encode()).hexdigest())
  return s if s and s.get('expires',0)>time.time() else None
 def require(self):
  s=self.session()
  if s:return s
  self.send(401,{'error':'Sign in to GENESIS Sentinel.'});return None
 def body(self):
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=4096 or not self.headers.get('Content-Type','').startswith('application/json'):raise ValueError()
   value=json.loads(self.rfile.read(n),parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
   if not isinstance(value,dict):raise ValueError()
   return value
  except (ValueError,TypeError,UnicodeError):self.send(400,{'error':'Send a JSON object of at most 4096 bytes.'});return None
 def same_origin(self):
  allowed=[self.url.rstrip('/'),'http://localhost:'+str(self.server.server_port)]
  if self.headers.get('Origin') not in allowed:self.send(403,{'error':'Origin rejected. Reload the local dashboard.'});return False
  return True
 def do_GET(self):
  if not self.local():return
  path=urlsplit(self.path).path
  if path in STATIC:
   name,kind=STATIC[path];p=CODE/'web-control'/name
   if not p.is_file():return self.send(503,'Dashboard assets are being prepared.','text/plain; charset=utf-8')
   return self.send(200,p.read_bytes(),kind)
  if path=='/api/session':
   s=self.session();return self.send(200,{'authenticated':bool(s),'csrf':s.get('csrf') if s else None,'url':self.url,'active_action':ACTIVE})
  s=self.require()
  if not s:return
  if path=='/api/data':
   try:
    from . import control_model
    control_model.ROOT=B
    data=control_model.get_data();data['services']=services.get_services();data['csrf']=s['csrf'];data['control_center']={'url':self.url,'active_action':ACTIVE,'observed_at':now()};return self.send(200,data)
   except Exception:return self.send(503,{'error':'The saved inventory could not be read. Existing records are preserved; retry or use sentinel status.'})
  if path.startswith('/api/actions/'):
   ident=path.removeprefix('/api/actions/')
   if len(ident)!=24 or any(x not in '0123456789abcdef' for x in ident):return self.send(404,{'error':'Action not found.'})
   job=read(R/('control-action-'+ident+'.json'))
   return self.send(200 if job else 404,job or {'error':'Action not found.'})
  if path.startswith('/reports/'):
   ident=path.removeprefix('/reports/')
   if len(ident)>100 or '/' in ident:return self.send(404,{'error':'Report not found.'})
   try:
    from . import control_model
    control_model.ROOT=B
    report=control_model.get_report(ident)
    if not report:return self.send(404,{'error':'Report not found.'})
    title=html.escape(str(report['title']));text=html.escape(str(report['text']));source=html.escape(str(report.get('path','')))
    doc='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+' · GENESIS</title><link rel="stylesheet" href="/style.css"><body class="report-page"><main><a href="/">← Control center</a><h1>'+title+'</h1><p class="report-source">Source: '+source+'</p><pre class="report-content">'+text+'</pre></main></body></html>'
    return self.send(200,doc,'text/html; charset=utf-8')
   except ImportError:return self.send(503,{'error':'Report catalog is being prepared. Retry shortly.'})
   except (OSError,KeyError,ValueError):return self.send(404,{'error':'Report not found.'})
  if path=='/open/jupyter':
   status=next((x for x in services.get_services(force=True) if x['id']=='jupyter'),{})
   if status.get('state') not in ['RUNNING','BUSY']:return self.send(409,{'error':'Start the owned Jupyter service first.'})
   token=read(B/'private/jupyter-secret.json').get('token')
   if not token:return self.send(409,{'error':'Jupyter authentication is unavailable.'})
   # Authenticated explicit-click handoff only. No access log, no token in inventory or HTML.
   from urllib.parse import quote
   return self.send(303,b'',extra={'Location':services.jupyter_url()+'?token='+quote(token,safe='')})
  self.send(404,{'error':'Page not found.'})
 def do_POST(self):
  if not self.local() or not self.same_origin():return
  path=urlsplit(self.path).path
  if path=='/api/login':
   if AUTH_FAILURES['until']>time.time():return self.send(429,{'error':'Too many sign-in attempts. Wait 30 seconds.'})
   body=self.body()
   if body is None:return
   if set(body)!= {'username','password'} or not valid_credentials(body.get('username'),body.get('password')):
    AUTH_FAILURES['count']+=1
    if AUTH_FAILURES['count']>=8:AUTH_FAILURES.update(count=0,until=time.time()+30)
    return self.send(401,{'error':'Username or password was not accepted.'})
   AUTH_FAILURES['count']=0;token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
   with STORE_LOCK:
    sessions={k:v for k,v in read(P/'sessions.json').items() if v.get('expires',0)>time.time()}
    sessions=dict(list(sessions.items())[-31:]);sessions[hashlib.sha256(token.encode()).hexdigest()]={'csrf':csrf,'expires':time.time()+43200,'created_at':now()};atomic(P/'sessions.json',sessions)
   return self.send(200,{'authenticated':True,'csrf':csrf,'url':self.url},extra={'Set-Cookie':'genesis_release_control='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'})
  s=self.require()
  if not s:return
  if not hmac.compare_digest(self.headers.get('X-CSRF-Token','').encode(),s['csrf'].encode()):return self.send(403,{'error':'Security token rejected. Reload the dashboard.'})
  body=self.body()
  if body is None:return
  if path=='/api/logout':
   try:
    c=SimpleCookie(self.headers.get('Cookie',''));token=c.get('genesis_release_control');key=hashlib.sha256(token.value.encode()).hexdigest() if token else ''
    with STORE_LOCK:
     sessions=read(P/'sessions.json');sessions.pop(key,None);atomic(P/'sessions.json',sessions)
   except Exception:pass
   return self.send(200,{'authenticated':False},extra={'Set-Cookie':'genesis_release_control=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
  if path=='/api/action':
   if set(body)!={'service','action'} or not all(isinstance(body[x],str) for x in body):return self.send(400,{'error':'Choose an existing application and action.'})
   try:return self.send(202,start_action(body['service'],body['action']))
   except ValueError as e:return self.send(400,{'error':str(e)})
   except RuntimeError as e:return self.send(409,{'error':str(e)})
  self.send(404,{'error':'Action not found.'})

class Server(ThreadingHTTPServer):
 daemon_threads=True;request_queue_size=8;allow_reuse_address=True
 slots=threading.BoundedSemaphore(12)
 def process_request(self,request,client_address):
  if not self.slots.acquire(blocking=False):request.close();return
  try:super().process_request(request,client_address)
  except BaseException:self.slots.release();raise
 def process_request_thread(self,request,client_address):
  try:super().process_request_thread(request,client_address)
  finally:self.slots.release()
 def get_request(self):
  sock,addr=super().get_request();sock.settimeout(10);return sock,addr

def main(argv=None):
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,required=True);args=parser.parse_args(argv)
 if not 1024<=args.port<=65535:raise SystemExit('Choose a nonprivileged local port (1024..65535).')
 setup_storage();access();lock=(R/'control-server.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 # Never leave an old action falsely running after a control-center interruption.
 for p in R.glob('control-action-*.json'):
  job=read(p)
  if job.get('status') in ['queued','running']:job.update(status='failed',message='Control center restarted before this action completed. Check live application status before retrying.',finished_at=now());atomic(p,job,0o644);log_action(dict(job))
 server=Server(('127.0.0.1',args.port),Handler);server.control_url='http://127.0.0.1:'+str(args.port)+'/'
 atomic(R/'control-public.json',{'url':server.control_url,'port':args.port,'state':'RUNNING','started_at':now()},0o644)
 def shutdown(signum,frame):
  if ACTIVE:raise SystemExit('Control center stopped while an action was running; check live status after restart.')
  raise SystemExit(0)
 signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
 try:server.serve_forever()
 finally:server.server_close()
if __name__=='__main__':main()
