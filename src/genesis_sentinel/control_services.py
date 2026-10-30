"""Read-only configured local services and fixed Sentinel refresh dispatch.

Optional deployment-specific adapters are explicit, disabled by default, and use
fixed known launchers. Browser requests never supply a path, command, or argv.
"""
from __future__ import annotations
import datetime
import errno
import json
import os
import threading
import time
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from .config import state_dir

B = state_dir()
CACHE = {}
CACHE_LOCK = threading.Lock()
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None
OPENER = build_opener(ProxyHandler({}), NoRedirect())
def configure(root):
    global B
    B = Path(root)
    invalidate()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(path):
    try: return json.loads(Path(path).read_text())
    except (OSError,ValueError): return {}
def identity(pid):
    try:
        p = Path('/proc')/str(int(pid)); fields = (p/'stat').read_text().rsplit(')',1)[1].split()
        args = [x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x]
        return {'pid':int(pid),'start':fields[19],'args':args,'cwd':str((p/'cwd').resolve())} if args else {}
    except (OSError,ValueError,IndexError): return {}
def local_url(url):
    try:
        u = urlsplit(url)
        return isinstance(url,str) and u.scheme == 'http' and u.hostname in {'127.0.0.1','localhost'} and u.port is not None and not u.username and not u.password and not u.query and not u.fragment
    except (ValueError,TypeError): return False

def http(url, headers=None, json_body=False):
    try:
        with OPENER.open(Request(url,headers=headers or {}),timeout=3) as r:
            raw = r.read(2_000_000) if json_body else b''
            return r.status, json.loads(raw) if json_body else None, None
    except HTTPError as e:
        code=e.code;e.close();return code,None,None
    except (URLError,OSError,ValueError) as e:
        reason = getattr(e,'reason',e)
        return None,None,'refused' if getattr(reason,'errno',None)==errno.ECONNREFUSED else 'inconclusive'

def _configured_services():
    rows = []
    for item in read(B/'config.json').get('services',[]):
        if not isinstance(item,dict): continue
        item = dict(item)
        if not item.get('url') and isinstance(item.get('port'),int): item['url']='http://127.0.0.1:'+str(item['port'])+'/'
        if not local_url(item.get('url')): continue
        ident = item.get('id')
        if not isinstance(ident,str) or not ident or ident in {'sentinel','control_center','jupyter'}: continue
        code,_,err = http(item['url'])
        state = 'RUNNING' if code is not None and 200 <= code < 400 else 'STOPPED' if err=='refused' else 'UNKNOWN'
        rows.append({'id':ident,'name':str(item.get('name',ident)),'url':item['url'],'state':state,'label':'Endpoint responded' if state=='RUNNING' else 'Stopped' if state=='STOPPED' else 'Needs a check','detail':'Operator-configured local endpoint. HTTP alone does not verify process identity or scientific correctness. External service controls are disabled.','http':code,'owned':False,'identified':state=='RUNNING','actions':[],'observed_at':now(),'verification_note':'Configured endpoint HTTP observation only.'})
    return rows

def jupyter_url():
    url = read(B/'private/jupyter-process.json').get('url','http://127.0.0.1:8888/lab')
    return url if local_url(url) and urlsplit(url).path == '/lab' else 'http://127.0.0.1:8888/lab'
def jupyter_headers():
    token = read(B/'private/jupyter-secret.json').get('token')
    return {'Authorization':'token '+token} if token else {}
def jupyter_owned():
    r = read(B/'private/jupyter-process.json'); i = identity(r.get('pid',0)); old = r.get('identity',{})
    return bool(i and i.get('start')==old.get('start') and i.get('args')==old.get('cmd') and str(B/'private/jupyter_server_config.json') in i['args'])
def get_services(force=False):
    with CACHE_LOCK:
        if not force and CACHE.get('at',0)>time.monotonic()-15: return json.loads(json.dumps(CACHE['data']))
        data = _configured_services()
        cfg = read(B/'config.json')
        if cfg.get('enable_deployment_adapters') is True:
            from . import adapters
            adapters.configure(B)
            specialized = adapters.get_services(force=True)
            ids = {r['id'] for r in specialized}
            data = [r for r in data if r['id'] not in ids] + specialized
        if (B/'private/jupyter-process.json').exists():
            owned = jupyter_owned()
            code,_,err = http(jupyter_url().removesuffix('/lab')+'/api/status',jupyter_headers(),True) if owned else (None,None,'inconclusive')
            okay = owned and code == 200
            data.append({'id':'jupyter','name':'JupyterLab','url':jupyter_url(),'state':'RUNNING' if okay else 'UNKNOWN' if owned else 'STOPPED','label':'Running' if okay else 'Needs a check' if owned else 'Stopped','detail':'Optional owned Jupyter workbench. Use the terminal Jupyter helper for lifecycle; save notebook work before stopping.','http':code,'owned':owned,'actions':[],'observed_at':now()})
        pub = read(B/'runtime/control-public.json')
        if pub.get('url'): data.append({'id':'control_center','name':'GENESIS Sentinel','url':pub['url'],'state':'RUNNING','label':'Running','detail':'Authenticated local control center. Terminal lifecycle commands manage this process.','http':200,'owned':True,'actions':[],'observed_at':now()})
        data.append({'id':'sentinel','name':'Software inventory','url':None,'state':'RUNNING','label':'Available','detail':'Refresh existing Sentinel records. No software is installed or upgraded.','http':None,'owned':True,'actions':['refresh'],'observed_at':now()})
        CACHE.update(at=time.monotonic(),data=data)
        return json.loads(json.dumps(data))
def invalidate():
    with CACHE_LOCK: CACHE.clear()
def allowed(service,action):
    if (service,action)==('sentinel','refresh'): return True
    if read(B/'config.json').get('enable_deployment_adapters') is True:
        from . import adapters
        adapters.configure(B)
        return adapters.allowed(service,action)
    return False
def perform(service,action):
    if not allowed(service,action): raise ValueError('Unsupported application or action')
    if service=='sentinel':
        from . import core
        core.refresh(B,full=False)
        invalidate()
        return 'Software records refreshed.'
    from . import adapters
    adapters.configure(B)
    result = adapters.perform(service,action); invalidate(); return result
