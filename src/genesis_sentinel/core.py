"""Arch Sentinel: metadata first, immutable generations, explicit bounded verification."""
import argparse, contextlib, datetime as dt, fcntl, hashlib, json, os, platform, re, errno, socket
import shutil, signal, subprocess, sys, time, uuid, tempfile, resource, ctypes, pwd
from .config import state_dir, default_config, validate_config
from pathlib import Path
from urllib.request import build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
ROOT=state_dir()
NAMES=['SOFTWARE-INVENTORY.json','ENVIRONMENTS.json','PROJECT-MAP.json','CAPABILITY-GRAPH.json','CURRENT-STATUS.md','SESSION-BRIEF.md']
THREADS={k:'1' for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']}
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def load(p,default=None):
 try:return json.loads(Path(p).read_text())
 except (OSError,ValueError):return default

def fsync_directory(path):
 fd=os.open(str(path),os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
 try:os.fsync(fd)
 finally:os.close(fd)

def atomic(p,value,mode=0o600):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_name('.'+p.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
  with os.fdopen(fd,'w',encoding='utf-8') as f:
   f.write(value if isinstance(value,str) else json.dumps(value,indent=2,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
  os.replace(tmp,p);fsync_directory(p.parent)
 finally:
  if tmp.exists():tmp.unlink()

@contextlib.contextmanager
def marker_lock(root):
 path=Path(root)/'runtime';path.mkdir(parents=True,exist_ok=True)
 with (path/'dirty.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  try:yield
  finally:fcntl.flock(lock,fcntl.LOCK_UN)

def mark_dirty(root,reason):
 root=Path(root)
 with marker_lock(root):
  record={'at':now(),'reason':str(reason)[:500],'id':uuid.uuid4().hex}
  atomic(root/'runtime/dirty.json',record)
  append_event(root/'runtime/events.jsonl',record)
 return record

def clear_dirty(root,observed):
 with marker_lock(root):
  path=Path(root)/'runtime/dirty.json'
  if load(path)==observed:path.unlink(missing_ok=True);fsync_directory(path.parent)

def append_event(path,record):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 fd=os.open(str(path),os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
 try:os.write(fd,(json.dumps(record,ensure_ascii=False)+'\n').encode());os.fsync(fd)
 finally:os.close(fd)

def stat(p):
 p=Path(p)
 try:
  s=p.stat();return [str(p),s.st_size,s.st_mtime_ns,s.st_ino]
 except OSError:return [str(p),'MISSING']

@contextlib.contextmanager
def writer(root=ROOT,seconds=3):
 (root/'runtime').mkdir(parents=True,exist_ok=True)
 with (root/'runtime/writer.lock').open('a') as f:
  end=time.monotonic()+seconds
  while True:
   try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);break
   except BlockingIOError:
    if time.monotonic()>=end:raise RuntimeError('another Sentinel writer is active; last valid generation retained')
    time.sleep(.05)
  try:yield
  finally:fcntl.flock(f,fcntl.LOCK_UN)

def run(argv,timeout=15):
 env=os.environ.copy();env.update(THREADS);env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
 parent_pid=os.getpid();libc=ctypes.CDLL(None) if sys.platform=='linux' else None
 def limits():
  # A wrapper interrupted during refresh must not leave its detached probe running.
  if libc is not None and hasattr(libc,'prctl'):
   if libc.prctl(1,int(signal.SIGKILL),0,0,0)==0 and os.getppid()!=parent_pid:os.kill(os.getpid(),signal.SIGKILL)
  resource.setrlimit(resource.RLIMIT_FSIZE,(8_000_000,8_000_000))
  resource.setrlimit(resource.RLIMIT_CPU,(max(2,int(timeout)+1),max(3,int(timeout)+2)))
  resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
 with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
  p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,env=env,start_new_session=True,preexec_fn=limits)
  try:p.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGKILL);p.wait();raise RuntimeError('bounded probe timed out')
  stdout.seek(0);out=stdout.read(8_000_001).decode(errors='replace');stderr.seek(0);err=stderr.read(8_000_001).decode(errors='replace')
 if p.returncode:raise RuntimeError('probe exit '+str(p.returncode)+': '+err[-1200:])
 if len(out)>8_000_000:raise RuntimeError('probe exceeded output cap')
 return out

METADATA=r'''
import sys,json,importlib.metadata as m,sysconfig,platform
rows=[]
for d in m.distributions():
 name=d.metadata.get('Name')
 if name: rows.append({'name':name,'version':d.version,'location':str(d.locate_file('')),'metadata_path':str(d._path)})
print(json.dumps({'python_version':platform.python_version(),'prefix':sys.prefix,'base_prefix':sys.base_prefix,'sys_paths':sys.path,'packages':sorted(rows,key=lambda x:x['name'].lower())}))
'''
def env_id(prefix):return 'python-'+hashlib.sha256(str(prefix).encode()).hexdigest()[:12]
def norm(s):return re.sub('[-_.]+','-',s).lower()
def load_config(root=ROOT):
 path=Path(root)/'config.json'
 if path.exists():
  raw=load(path)
  if raw is None:raise ValueError('invalid config.json; previous generation retained')
  return validate_config(raw)
 return default_config()

def discover(config):
 candidates={str(Path(p).absolute()) for p in config.get('interpreters',[])}
 prefixes=set(config.get('conda_roots',[]))
 for base in list(prefixes):
  envs=Path(base)/'envs'
  if envs.is_dir():prefixes.update(str(p) for p in envs.iterdir() if p.is_dir())
 for registry in config.get('conda_registry_files',[]):
  p=Path(registry)
  if p.is_file() and p.stat().st_size<=1_000_000:
   prefixes.update(x.strip() for x in p.read_text().splitlines() if Path(x.strip()).is_absolute())
 for prefix in prefixes:candidates.add(str(Path(prefix)/'bin/python'))
 for entry in config.get('projects',[])+config.get('extra_roots',[]):
  p=Path(entry['path'])
  for suffix in ['.venv/bin/python','venv/bin/python','env/bin/python']:
   if (p/suffix).exists():candidates.add(str(p/suffix))
 canonical={}
 for candidate in sorted(candidates):
  prefix=str(Path(candidate).parent.parent.resolve())
  canonical.setdefault(prefix,candidate)
 return sorted(canonical.values())

def conda_metadata(prefix):
 records=[];errors=[]
 for path in sorted((Path(prefix)/'conda-meta').glob('*.json')):
  if path.stat().st_size>8_000_000:
   errors.append({'path':str(path),'error':'metadata record exceeds 8MB cap'});continue
  data=load(path)
  if not isinstance(data,dict) or not data.get('name'):
   errors.append({'path':str(path),'error':'invalid conda metadata'});continue
  channel=str(data.get('channel',''))
  channel=re.sub(r'(https?://)[^/@]+:[^/@]+@',r'\1[REDACTED]@',channel)
  channel=re.sub(r'/t/[^/]+/',r'/t/[REDACTED]/',channel)
  records.append({'name':data['name'],'version':data.get('version'),'build':data.get('build'),'build_number':data.get('build_number'),'subdir':data.get('subdir'),'channel':channel,'sha256':data.get('sha256'),'metadata_path':str(path),'location':str(prefix)})
 return records,errors

def signature(interpreter,sys_paths=None):
 p=Path(interpreter);prefix=p.parent.parent
 records=[stat(p),stat(prefix/'pyvenv.cfg'),['runtime_environment',digest({k:os.environ.get(k) for k in ['LD_LIBRARY_PATH','LD_PRELOAD','CONDA_PREFIX','VIRTUAL_ENV']})]]
 prefixes={prefix}
 cfg=prefix/'pyvenv.cfg'
 if cfg.is_file():
  content=cfg.read_text()
  # Inherited metadata must invalidate a system-site-packages venv too.
  if 'include-system-site-packages = true' in content.lower():
   for line in content.splitlines():
    if line.startswith('home = '):prefixes.add(Path(line.split(' = ',1)[1]).parent)
 sites=set()
 for base in sorted(prefixes):
  for layout in ['lib/python*/site-packages','lib/python*/dist-packages','lib64/python*/site-packages']:
   sites.update(base.glob(layout))
 for path in sys_paths or []:
  candidate=Path(path)
  if candidate.is_absolute() and candidate.is_dir():sites.add(candidate)
 for site in sorted(sites):
  records.append(stat(site))
  for item in sorted(site.iterdir()):
   if item.name.endswith(('.dist-info','.egg-info','.pth','.egg-link')):
    records.append(stat(item))
    if item.is_dir():records.append(stat(item/('METADATA' if item.name.endswith('.dist-info') else 'PKG-INFO')))
 for base in sorted(prefixes):
  records.extend([stat(base/'conda-meta'),stat(base/'conda-meta/history')])
  records.extend(stat(q) for q in sorted((base/'conda-meta').glob('*.json')))
 return digest(records)

def inspect_env(interpreter,old,full):
 sig=signature(interpreter,(old or {}).get('sys_paths',[]));prefix=str(Path(interpreter).parent.parent.resolve());eid=env_id(prefix)
 if not Path(interpreter).exists():return {'id':eid,'interpreter':interpreter,'prefix':prefix,'state':'UNAVAILABLE','signature':sig,'observed_at':now(),'packages':[],'error':'missing interpreter'}
 if old and old.get('signature')==sig and not full and old.get('state')=='INSTALLED' and 'conda_packages' in old:return {**old,'observed_at':now(),'cached':True}
 try:
  data=json.loads(run([interpreter,'-I','-c',METADATA],25))
  data['conda_packages'],data['metadata_errors']=conda_metadata(prefix)
  return dict(data,id=env_id(data['prefix']),interpreter=interpreter,real_executable=str(Path(interpreter).resolve()),owner_context=pwd.getpwuid(Path(interpreter).stat().st_uid).pw_name,kind='conda' if (Path(prefix)/'conda-meta').is_dir() else 'venv' if (Path(prefix)/'pyvenv.cfg').exists() else 'system',state='INSTALLED',signature=signature(interpreter,data.get('sys_paths',[])),observed_at=now(),cached=False)
 except Exception as e:return dict(old or {},id=eid,interpreter=interpreter,prefix=prefix,state='FAILED_CHECK',signature=sig,observed_at=now(),error=str(e))

OPERATIONS={'numpy':'matrix multiplication','scipy':'numerical quadrature','sympy':'symbolic differentiation','mpmath':'arbitrary precision arithmetic','pandas':'tabular data','matplotlib':'scientific plotting','networkx':'graph operations','rdkit':'SMILES descriptors and molecular rendering','torch':'CPU tensor; CUDA availability must be independently checked','jupyterlab':'authenticated notebook UI','ipykernel':'Jupyter Python kernel','ipython':'interactive Python','openbabel':'molecular conversion','tensorflow':'AI framework presence only','transformers':'model tooling presence only','jax':'AI array framework presence only','scikit-learn':'machine learning','sqlite':'SQL database','sqlite3':'standard-library SQLite bounded query'}
PROBES={
 'sqlite3':"import sqlite3; c=sqlite3.connect(':memory:'); assert c.execute('select 2+3').fetchone()[0]==5; print(sqlite3.sqlite_version)",
 'numpy':"import numpy as n; assert (n.array([[1,2],[3,4]])@n.array([1,1])).tolist()==[3,7]; print(n.__version__)",
 'scipy':"import scipy; from scipy.integrate import quad; assert abs(quad(lambda x:x*x,0,1)[0]-1/3)<1e-12; print(scipy.__version__)",
 'sympy':"import sympy as s; x=s.Symbol('x'); assert s.diff(x**3,x)==3*x**2; print(s.__version__)",
 'mpmath':"import mpmath as m; m.mp.dps=40; assert abs(m.sqrt(2)**2-2)<m.mpf('1e-38'); print(m.__version__)",
 'pandas':"import pandas as p; assert p.Series([1,2,3]).sum()==6; print(p.__version__)",
 'networkx':"import networkx as n; assert n.is_connected(n.path_graph(3)); print(n.__version__)",
 'rdkit':"from rdkit import Chem,rdBase; from rdkit.Chem import Descriptors,Draw; m=Chem.MolFromSmiles('CCO'); assert abs(Descriptors.MolWt(m)-46.069)<.001; assert '<svg' in Draw.MolsToGridImage([m],useSVG=True); print(rdBase.rdkitVersion)",
 'matplotlib':"import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as p,io; b=io.BytesIO(); p.plot([0,1],[0,1]); p.savefig(b,format='png'); assert b.getvalue().startswith(bytes([137,80,78,71])); print(matplotlib.__version__)",
 'torch':"import torch,json; torch.set_num_threads(1); a=torch.tensor([[1.,2.],[3.,4.]]); assert (a@torch.ones(2)).tolist()==[3.,7.]; cuda=torch.cuda.is_available(); r={'version':torch.__version__,'cpu_tensor':'FUNCTIONALLY_VERIFIED','cuda_build':torch.version.cuda,'cuda_available':cuda,'gpu_operation':'UNAVAILABLE'};\nif cuda:\n b=torch.ones(2,device='cuda'); assert b.sum().item()==2; r['gpu_operation']='FUNCTIONALLY_VERIFIED'\nprint(json.dumps(r))",
 'ipykernel':"import ipykernel; print(ipykernel.__version__)",
 'jupyterlab':"import jupyterlab; print(jupyterlab.__version__)"}

def http(port):
 observed=now();url=f'http://127.0.0.1:{port}/'
 try:
  with build_opener(ProxyHandler({})).open(url,timeout=2) as r:code=r.status
 except HTTPError as e:code=e.code
 except (URLError,OSError) as e:
  reason=getattr(e,'reason',e)
  refused=isinstance(reason,OSError) and reason.errno==errno.ECONNREFUSED
  return {'state':'STOPPED' if refused else 'UNKNOWN','observed_at':observed,'url':url,'http':None,'limitation':'connection refused' if refused else 'HTTP probe inconclusive: '+type(reason).__name__}
 return {'state':'DISCOVERED','observed_at':observed,'url':url,'http':code,'limitation':'HTTP response alone does not establish process identity or functional health'+('; rate limited' if code==429 else '')}

def flatten(data):
 rows={}
 for e in data.get('environments',[]):
  rows[e['id']]={k:e.get(k) for k in ['interpreter','real_executable','python_version','state','signature']}
  for p in e.get('packages',[]):rows[e['id']+':'+norm(p['name'])]={'version':p['version'],'location':p['location'],'metadata_path':p['metadata_path']}
  for p in e.get('conda_packages',[]):rows[e['id']+':conda:'+norm(p['name'])]={k:p.get(k) for k in ['version','build','channel','metadata_path','location']}
 for p in data.get('arch_packages',{}).get('packages',[]):rows['arch:'+p['name']]={'version':p['version']}
 for t in data.get('tools',[]):rows[t['id']]={k:t.get(k) for k in ['path','real_path','version','state','signature']}
 for port,s in data.get('services',{}).items():rows['service:'+port]={'state':s['state'],'http':s['http']}
 return rows

def changes(before,after):
 a,b=flatten(before),flatten(after);out=[]
 for k in sorted(a.keys()|b.keys()):
  if a.get(k)!=b.get(k):out.append({'id':k,'kind':'ADDED' if k not in a else 'REMOVED' if k not in b else 'CHANGED','before':a.get(k),'after':b.get(k)})
 return out

def validate_generation(root,generation):
 root=Path(root)
 if not isinstance(generation,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,100}',generation):
  raise ValueError('invalid generation identifier')
 dest=root/'generations'/generation
 if dest.is_symlink() or dest.resolve().parent!=(root/'generations').resolve():raise ValueError('generation must be an owned direct directory')
 manifest=load(dest/'GENERATION-MANIFEST.json',{})
 if manifest.get('generation')!=generation or set(manifest.get('sha256',{}))!=set(NAMES):raise ValueError('generation manifest is missing or incomplete')
 for name in NAMES:
  path=dest/name
  if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256'][name]:raise ValueError('generation file is missing or has changed: '+name)
  if name.endswith('.json') and load(path,{}).get('generation')!=generation:raise ValueError('generation identity mismatch: '+name)
 return dest

def publish_pointer(root,generation):
 root=Path(root)
 for name in NAMES:
  target=root/name
  if target.is_symlink():
   if os.readlink(target)!='current/'+name:raise RuntimeError('refusing unmanaged report symlink '+str(target))
  elif target.exists():raise RuntimeError('refusing to replace unmanaged report '+str(target))
 for name in NAMES:
  target=root/name
  if not target.is_symlink():target.symlink_to('current/'+name)
 link=root/('.current-'+uuid.uuid4().hex)
 try:
  link.symlink_to('generations/'+generation);os.replace(link,root/'current');fsync_directory(root)
 finally:link.unlink(missing_ok=True)

def commit(root,files,generation):
 root=Path(root)
 if not isinstance(generation,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,100}',generation):raise ValueError('invalid generation identifier')
 if set(files)!=set(NAMES):raise ValueError('complete six-file generation required')
 dest=root/'generations'/generation;dest.mkdir(parents=True)
 for name,value in files.items():atomic(dest/name,value)
 manifest={'generation':generation,'sha256':{name:hashlib.sha256((dest/name).read_bytes()).hexdigest() for name in NAMES}}
 atomic(dest/'GENERATION-MANIFEST.json',manifest);fsync_directory(dest.parent)
 validate_generation(root,generation);publish_pointer(root,generation)

def recover(root,generation):
 root=Path(root)
 with writer(root):
  validate_generation(root,generation);previous=(root/'current').resolve().name if (root/'current').exists() else None
  publish_pointer(root,generation)
  mark_dirty(root,'recovered generation '+generation+'; refresh to reconcile current software')
  append_event(root/'CHANGES.jsonl',{'type':'recovery','generation':generation,'previous_generation':previous,'observed_at':now(),'changes':[]})
 return generation

def read_snapshot(root=ROOT):return load(root/'SOFTWARE-INVENTORY.json',{})
def verify_records(root):return load(root/'runtime/verifications.json',{})
def capabilities(envs,tools,verification,ttl,arch_packages=None,registries=None):
 caps=[]
 for env in envs:
  packages=list(env.get('packages',[]))
  if env.get('state')=='INSTALLED':
   packages.append({'name':'sqlite3','version':'stdlib / Python '+env.get('python_version','unknown'),'location':env['prefix'],'metadata_source':'Python standard library; explicit probe required'})
  for p in packages:
   name=norm(p['name'])
   if name not in OPERATIONS:continue
   cid=env['id']+':'+name;v=verification.get(cid,{})
   state='INSTALLED';when=None;evidence=None
   limitations=['Only the named bounded operation is verified, not the entire package.']
   external=[]
   for source in registries or []:
    if str(Path(source['interpreter']).absolute())!=str(Path(env['interpreter']).absolute()):continue
    history=load(source['path'],{})
    for entry in history.get('engines',[]) if isinstance(history,dict) else []:
     if norm(str(entry.get('name','')))==name and entry.get('version')==p['version']:
      external.append({'path':source['path'],'state':entry.get('state','UNKNOWN'),'verified_at':entry.get('last_verified_at_utc')})
   if external:limitations.append('External registry evidence is historical context; it does not establish a current Sentinel functional pass.')
   if v:
    when=v.get('checked_at');evidence=v.get('evidence');state=v.get('state','UNKNOWN') if v.get('signature')==env['signature'] else 'STALE'
   if when:
    try:
     age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(when)).total_seconds()
     if age<0 or age>ttl*3600:state='STALE'
    except (TypeError,ValueError):state='STALE'
   if env['state']!='INSTALLED':state=env['state']
   caps.append(dict(id=cid,environment_id=env['id'],interpreter=env['interpreter'],package=name,version=p['version'],location=p['location'],supported_operation=OPERATIONS[name],state=state,last_observation_at=env['observed_at'],last_functional_verification_at=when,evidence=evidence,external_evidence=external,known_limitations=limitations))
 for t in tools:caps.append(dict(t,environment_id='native-system',supported_operation='command line tool; explicit verify required',last_observation_at=now(),last_functional_verification_at=None,evidence=None,known_limitations=['Presence is not functional verification.']))
 return caps

def refresh(root=ROOT,full=False):
 started=time.monotonic()
 root=Path(root);root.mkdir(parents=True,exist_ok=True,mode=0o700);root.chmod(0o700)
 with writer(root):
  dirty_before=load(root/'runtime/dirty.json')
  config=load_config(root)
  if not (root/'config.json').exists():atomic(root/'config.json',config)
  previous=read_snapshot(root);old={e['interpreter']:e for e in previous.get('environments',[])}
  envs=[inspect_env(p,old.get(p),full) for p in discover(config)]
  toolnames=config['tool_names']
  tools=[];seen=set()
  for name in toolnames:
   path=shutil.which(name)
   if not path:continue
   real=str(Path(path).resolve())
   if real in seen:continue
   seen.add(real);tools.append({'id':'cli:'+name,'name':name,'path':path,'real_path':real,'state':'INSTALLED','signature':digest(stat(path))})
  # pacman reads its own installed package DB, no imports/transactions/network.
  pacman=shutil.which('pacman') if config['collect_arch_packages'] else None
  pacsig=digest([stat(config['arch_package_db'])])
  pac=previous.get('arch_packages',{})
  if not pacman:pac={'signature':pacsig,'packages':[],'state':'UNAVAILABLE','limitation':'pacman not configured or not found; Python/Conda discovery is independent.'}
  elif full or pac.get('signature')!=pacsig:
   try:pac={'signature':pacsig,'packages':[dict(zip(['name','version'],x.split(' ',1))) for x in run([pacman,'-Q'],10).splitlines()],'state':'INSTALLED'}
   except Exception as e:pac={**pac,'state':'FAILED_CHECK','error':str(e)}
  package_versions={p['name']:p['version'] for p in pac.get('packages',[])}
  old_tools={t['id']:t for t in previous.get('tools',[])}
  for tool in tools:
   cached=old_tools.get(tool['id'],{})
   if cached.get('signature')==tool['signature'] and cached.get('package_db_signature')==pacsig:
    tool.update({k:cached[k] for k in ['package','version','version_evidence','package_db_signature'] if k in cached});continue
   tool['package_db_signature']=pacsig
   try:
    if not pacman:raise RuntimeError('No pacman mapping')
    owner=run([pacman,'-Qoq',tool['real_path']],3).strip().splitlines()[0]
    if owner in package_versions:tool.update(package=owner,version=package_versions[owner],version_evidence='pacman installed package owning '+tool['real_path'])
   except Exception:pass
   if not tool.get('version'):
    tool.update(version=None,version_evidence='UNKNOWN: executable has no verified installed package mapping; no arbitrary tool was executed')
  services={}
  for port in [item['port'] for item in config['services']]:
   prior=previous.get('services',{}).get(str(port),{})
   recent=prior.get('observed_at') and (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(prior['observed_at'])).total_seconds()<60
   services[str(port)]=prior if recent and not full else http(port)
  gen=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8];at=now()
  errors=[{'interpreter':e['interpreter'],'error':e['error']} for e in envs if e.get('error')]
  errors += [{'interpreter':e['interpreter'],'metadata_error':err} for e in envs for err in e.get('metadata_errors',[])]
  if pac.get('error'):errors.append({'source':'pacman','error':pac['error']})
  data={'schema_version':1,'generation':gen,'observed_at':at,'mode':'full' if full else 'quick','device_scope':platform.system()+' '+platform.machine()+' / registered roots only','user_context':{'uid':os.geteuid(),'home':str(Path.home()),'codex_home':os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))},'hardware':{'machine':platform.machine(),'system':platform.system(),'cpu_count':os.cpu_count(),'nvidia_device_nodes':[str(p) for p in Path('/dev').glob('nvidia*')],'limitation':'Android/proot may hide hardware; CUDA package metadata is not acceleration proof.'},'environments':envs,'tools':tools,'arch_packages':pac,'services':services,'errors':errors}
  delta=changes(previous,data);data['changes_count']=len(delta);data['duration_seconds']=round(time.monotonic()-started,3)
  caps=capabilities(envs,tools,verify_records(root),config.get('verification_ttl_hours',24),pac.get('packages',[]),config.get('scientific_registries',[]))
  projects=[]
  for p in config['projects']+config.get('extra_roots',[]):
   path=Path(p['path']);manifests=[]
   for name in ['pyproject.toml','requirements.txt','package.json','environment.yml','AGENTS.md']:
    f=path/name
    if f.is_file():manifests.append({'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
   projects.append(dict(p,state='DISCOVERED' if path.is_dir() else 'UNAVAILABLE',observed_at=at,manifests=manifests))
  roots=[]
  for p in config.get('tool_roots',[]):
   path=Path(p);roots.append({'path':p,'entries':[stat(x) for x in sorted(path.iterdir())][:1000] if path.is_dir() else [],'cap':1000})
  project_map={'generation':gen,'observed_at':at,'projects':projects,'registered_tool_roots':roots,'reused_discovery':'Explicit configuration and bounded conventional environment paths','limitation':'Targeted manifests and immediate tool entries; no recursive whole-device scan, no automatic project setup execution.'}
  prior_projects=load(root/'PROJECT-MAP.json',{})
  if prior_projects and [{k:p.get(k) for k in ['path','state','manifests']} for p in prior_projects.get('projects',[])]!=[{k:p.get(k) for k in ['path','state','manifests']} for p in projects]:delta.append({'id':'project-manifests','kind':'CHANGED'})
  if prior_projects and prior_projects.get('registered_tool_roots')!=roots:delta.append({'id':'manual-tool-roots','kind':'CHANGED'})
  data['changes_count']=len(delta)
  brief=f"""# GENESIS Sentinel session brief
Generation: {gen}
Observed: {at}; metadata and functional verification have separate clocks.
Refresh: {data['mode']}; errors: {len(errors)}; changes: {len(delta)}.
State directory: {root}
Before trusting freshness, check runtime/dirty.json, runtime/last-error.json and runtime/launcher-last-error.json, then run genesis-sentinel --state-dir {root} status.
Read SOFTWARE-INVENTORY.json, ENVIRONMENTS.json, PROJECT-MAP.json and CAPABILITY-GRAPH.json from one resolved current generation for consistency.
Find an existing capability before adding dependencies; use its recorded absolute interpreter. INSTALLED is not a functional pass. Recheck STALE operations with genesis-sentinel verify <capability-id>.
Each environment stays separate. CPU verification does not establish usable CUDA/GPU computation. Local HTTP is an availability observation, not application identity or scientific correctness.
After runtime/configuration changes mark dirty and refresh explicitly. Register new roots rather than scanning the device. Unknown project setup scripts are never run by inventory.
Read the project's own AGENTS.md and SESSION-HANDOFF.md before changing it. Preserve prior generations, failed checks and saved research. Existing conversations do not silently reload updated evidence.
"""
  status=f"# Arch Sentinel current status\n\nGeneration: {gen}\nObserved: {at}\nMode: {data['mode']}; changes: {len(delta)}; refresh errors: {len(errors)}\nEnvironments: {len(envs)}; Python distributions: {sum(len(e.get('packages',[])) for e in envs)}; capabilities: {len(caps)}\n\n"+'\n'.join(f"- {p}: {s['state']} HTTP {s['http']} ({s['url']})" for p,s in services.items())+'\n\nRun `sentinel status` for age, dirty/error markers and live HTTP. Package presence is not a functional pass. Last-known-good generations are retained in generations/.\n'
  if errors:status+='\nRefresh errors:\n'+json.dumps(errors,indent=2)+'\n'
  files={'SOFTWARE-INVENTORY.json':data,'ENVIRONMENTS.json':{'generation':gen,'observed_at':at,'environments':envs},'PROJECT-MAP.json':project_map,'CAPABILITY-GRAPH.json':{'generation':gen,'observed_at':at,'capabilities':caps,'edges':[{'environment':c['environment_id'],'provides':c['id']} for c in caps]},'CURRENT-STATUS.md':status,'SESSION-BRIEF.md':brief}
  commit(root,files,gen)
  append_event(root/'CHANGES.jsonl',{'generation':gen,'observed_at':at,'type':'refresh','changes':delta,'errors':errors})
  for name in ['last-error.json','launcher-last-error.json']:
   (root/'runtime'/name).unlink(missing_ok=True)
  clear_dirty(root,dirty_before)
  print(f"Sentinel {gen}: {len(delta)} changes, {len(errors)} errors, {data['duration_seconds']}s; {sum(e.get('cached',False) for e in envs)}/{len(envs)} cached interpreters.")
  return data

def verify(cid,root=ROOT):
 with writer(root):
  graph=load(root/'CAPABILITY-GRAPH.json',{});cap=next((c for c in graph.get('capabilities',[]) if c['id']==cid),None)
  if not cap:raise ValueError('unknown capability; inspect CAPABILITY-GRAPH.json')
  name=cap.get('package');code=PROBES.get(name)
  if not code:raise ValueError('No automatic probe for this capability; presence remains INSTALLED')
  env=next((e for e in read_snapshot(root).get('environments',[]) if e.get('id')==cap['environment_id']),{})
  checked=now();record={'capability':cid,'checked_at':checked,'state':'FAILED_CHECK','signature':signature(cap['interpreter'],env.get('sys_paths',[]))}
  try:
   output=run([cap['interpreter'],'-I','-c',code],45);record.update(state='IMPORTABLE' if name in ['ipykernel','jupyterlab'] else 'FUNCTIONALLY_VERIFIED',output=output.strip())
  except Exception as e:record['error']=str(e)
  path=root/'evidence'/('verify-'+uuid.uuid4().hex+'.json');atomic(path,record);record['evidence']=str(path)
  records=verify_records(root);records[cid]=record;atomic(root/'runtime/verifications.json',records)
  mark_dirty(root,'verification updated')
 print(json.dumps(record,indent=2));refresh(root)
 return record['state']!='FAILED_CHECK'

def get_status(root=ROOT):
 root=Path(root);data=read_snapshot(root)
 if not data:return {'state':'UNKNOWN','generation':None,'markers':{},'last_refresh_errors':[],'services':{}}
 age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(data['observed_at'])).total_seconds()
 markers={p.name:load(p) for p in [root/'runtime'/n for n in ['dirty.json','last-error.json','launcher-last-error.json']] if p.exists()}
 config=load_config(root)
 return {'generation':data['generation'],'metadata_age_seconds':round(age,1),'state':'STALE' if markers or age<0 or age>86400 or data.get('errors') else 'CURRENT','markers':markers,'last_refresh_errors':data.get('errors',[]),'services':{str(item['port']):http(item['port']) for item in config['services']}}

def status(root=ROOT):
 value=get_status(root);print(json.dumps(value,indent=2));return value
