"""Human views over committed Sentinel records, adapted from MOBILE-4.

No recursive filesystem discovery, scientific execution, or browser-supplied paths.
"""
from __future__ import annotations
import copy
import datetime as dt
import hashlib
import json
import re
import threading
import time
from collections import deque
from pathlib import Path
from .config import state_dir

ROOT = state_dir()
LOCK = threading.RLock()
CACHE = {}
REPORTS = {}
LABELS = {'FUNCTIONALLY_VERIFIED': 'Verified operation', 'IMPORTABLE': 'Imports successfully',
          'INSTALLED': 'Installed; not function tested', 'DISCOVERED': 'Found in inventory',
          'STOPPED': 'Stopped', 'UNAVAILABLE': 'Unavailable', 'FAILED_CHECK': 'Check failed',
          'STALE': 'Needs a fresh check', 'UNKNOWN': 'Not verified', 'COMPLETED': 'Completed',
          'VERIFIED': 'Verified', 'IN_PROGRESS': 'In progress', 'FAILED': 'Failed'}
SCIENCE_NAMES = {'numpy','scipy','sympy','mpmath','pandas','matplotlib','networkx','rdkit',
                 'openbabel','open-babel','obabel','octave','octave-cli','gnuplot','openblas',
                 'blas-openblas','lapack','r','julia','sqlite','sqlite3','scikit-learn','pillow'}
AI_NAMES = {'torch','pytorch','tensorflow','transformers','jax','jaxlib','onnx','onnxruntime',
            'ollama','llama-cli','tokenizers','huggingface-hub','safetensors','accelerate',
            'triton','torchvision','torchaudio'}
DEVELOPMENT = {'gcc','g++','clang','cmake','make','git','node','npm','python','pip','setuptools',
               'wheel','gfortran','rust','rustup','cargo','go','binutils','base-devel'}
PRIVATE_PARTS = {'private', '.codex', '.ssh', '.gnupg', '.aws', '.azure', '.config'}

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def norm(name): return re.sub('[-_.]+', '-', str(name)).lower()
def ident(value): return hashlib.sha256(str(value).encode()).hexdigest()[:18]
def load(path, default=None, cap=12_000_000):
    try:
        p = Path(path)
        if p.stat().st_size > cap: return default
        return json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError): return default

def iso_mtime(path):
    try: return dt.datetime.fromtimestamp(Path(path).stat().st_mtime, dt.timezone.utc).isoformat()
    except OSError: return None

def timestamp(data, path):
    return next((data[k] for k in ['checked_at','checked_at_utc','completed_at_utc','started_at',
                'recorded_at','observed_at'] if isinstance(data.get(k), str)), iso_mtime(path))
def count(value):
    return len(value) if isinstance(value, (dict,list)) else value if isinstance(value,int) and not isinstance(value,bool) else 0
def tallies(data): return {k: count(data.get(k)) for k in ['passed','failed','skipped']}
def category(name):
    bare = norm(name).removeprefix('python-')
    if bare in AI_NAMES or any(x in bare for x in ['cuda','cudnn','libtorch']): return 'AI & machine learning'
    if bare in SCIENCE_NAMES: return 'Scientific computing'
    if any(x in bare for x in ['jupyter','ipykernel','ipython','notebook','nbconvert']): return 'Notebooks & environments'
    if bare in DEVELOPMENT: return 'Development tools'
    if any(x in bare for x in ['apache','php','mariadb','joomla','flask','fastapi','nginx']): return 'Web & databases'
    return 'Libraries & system software'

def verification_state(state, verified_at):
    if state != 'FUNCTIONALLY_VERIFIED': return state
    try:
        age = (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(verified_at)).total_seconds()
        ttl = float(load(ROOT/'config.json', {}).get('verification_ttl_hours', 24))*3600
        return state if 0 <= age <= ttl else 'STALE'
    except (TypeError, ValueError, OverflowError): return 'STALE'

def env_name(env):
    prefix = env.get('prefix', '')
    return env.get('name') or (Path(prefix).parent.name+' / '+Path(prefix).name if Path(prefix).name in {'.venv','venv','env'} else Path(prefix).name) or env.get('interpreter', 'Python')

def register_report(path, title=None):
    p = Path(path)
    if p.is_symlink() or any(x in PRIVATE_PARTS for x in p.parts) or not p.is_file() or p.suffix.lower() not in {'.md','.json','.jsonl'}: return None
    try:
        if p.stat().st_size > 3_000_000: return None
        resolved = p.resolve()
        if any(x in PRIVATE_PARTS for x in resolved.parts): return None
    except OSError: return None
    rid = ident(str(p.absolute()))
    REPORTS[rid] = {'id': rid, 'title': title or p.name, 'path': str(p.absolute()), 'resolved': str(resolved)}
    return rid

def get_report(rid):
    if not isinstance(rid,str) or not re.fullmatch('[a-f0-9]{18}',rid): return None
    get_data()
    with LOCK:
        item = REPORTS.get(rid)
        if not item: return None
        path = Path(item['path'])
        try:
            if path.is_symlink() or str(path.resolve()) != item['resolved'] or any(x in PRIVATE_PARTS for x in path.resolve().parts) or path.stat().st_size > 3_000_000: return None
            return dict(item, text=path.read_text(encoding='utf-8', errors='replace'))
        except OSError: return None

def json_lines(path, limit=8000, max_bytes=8_000_000, tail=False):
    rows = []
    try:
        p = Path(path)
        with p.open('rb') as f:
            if tail:
                offset = max(0, p.stat().st_size-max_bytes); f.seek(offset)
                if offset: f.readline()
                rows = deque(maxlen=limit)
            read = 0
            for n,line in enumerate(f):
                read += len(line)
                if read > max_bytes or not tail and n >= limit: break
                try: rows.append(json.loads(line))
                except (ValueError,UnicodeError): continue
    except OSError: pass
    return list(rows)

def report_history(config):
    entries = []
    # Only explicitly configured historical reports; no personal project catalogue.
    for item in config.get('dashboard_reports', []):
        if not isinstance(item,dict) or not isinstance(item.get('path'),str): continue
        p = Path(item['path']); rid = register_report(p,item.get('title'))
        if not rid: continue
        data = load(p,{}) if p.suffix == '.json' else {}
        counts = tallies(data)
        status = item.get('status')
        if status not in {'COMPLETED','VERIFIED','IN_PROGRESS','FAILED','UNKNOWN'}:
            status = 'FAILED' if counts['failed'] else 'VERIFIED' if counts['passed'] else 'UNKNOWN'
        entries.append({'id':rid,'title':item.get('title',p.name),'summary':item.get('summary') or (f"{counts['passed']} passed · {counts['failed']} failed · {counts['skipped']} skipped" if any(counts.values()) else 'Registered report; open source for scope.'),'status':status,'time':timestamp(data,p),'project':item.get('project','Registered report'),'report_id':rid,'counts':counts,'note':'Historical evidence. A fallback source modification time is not an exact achievement time.'})
    for p in sorted((ROOT/'evidence').glob('verify-*.json'))[:2000]:
        d = load(p,{})
        if not d: continue
        rid = register_report(p, 'Capability verification')
        if rid: entries.append({'id':rid,'title':'Capability check · '+str(d.get('capability','unknown')),'summary':'Bounded operation result; open evidence for exact scope.','status':'VERIFIED' if d.get('state')=='FUNCTIONALLY_VERIFIED' else 'FAILED' if d.get('state')=='FAILED_CHECK' else 'UNKNOWN','time':d.get('checked_at'),'project':'Capabilities','report_id':rid,'counts':{},'note':'Past verification is distinct from present availability.'})
    actions = {}
    for row in json_lines(ROOT/'runtime/control-actions.jsonl',limit=1500,tail=True):
        key = row.get('id')
        if isinstance(key,str) and re.fullmatch('[a-f0-9]{24}',key): actions[key] = row
    for key,row in actions.items():
        rid = register_report(ROOT/'runtime'/('control-action-'+key+'.json'),'Local management action')
        entries.append({'id':key,'title':str(row.get('action','Action')).title()+' · '+str(row.get('service','application')),'summary':str(row.get('message','Authenticated action.'))[:600],'status':{'queued':'IN_PROGRESS','running':'IN_PROGRESS','succeeded':'COMPLETED','failed':'FAILED'}.get(row.get('status'),'UNKNOWN'),'time':row.get('finished_at') or row.get('started_at') or row.get('created_at'),'project':'Control center','report_id':rid,'counts':{},'note':'Local management action, not a software installation.'})
    return sorted(entries,key=lambda x:x.get('time') or '',reverse=True)

def change_rows():
    records = []
    first = json_lines(ROOT/'CHANGES.jsonl',limit=1)
    baseline = first[0].get('generation') if first else None
    for event in reversed(json_lines(ROOT/'CHANGES.jsonl',limit=3000,tail=True)):
        for c in event.get('changes',[]):
            before,after = c.get('before') or {},c.get('after') or {}
            kind = c.get('kind','UNKNOWN')
            if event.get('generation') == baseline and kind == 'ADDED': kind = 'BASELINE'
            if kind == 'CHANGED':
                if before.get('version') != after.get('version'): kind = 'VERSION'
                elif any(before.get(k) != after.get(k) for k in ['path','interpreter','location','real_path','real_executable','prefix']): kind = 'MOVED'
                elif after.get('state') in ['FAILED_CHECK','UNAVAILABLE']: kind = 'FAILED'
                elif before.get('state') == 'FAILED_CHECK' and after.get('state') in ['FUNCTIONALLY_VERIFIED','IMPORTABLE','INSTALLED']: kind = 'REPAIRED'
                else: kind = 'STATE'
            def human(value): return ', '.join(str(value[k]) for k in ['version','interpreter','path','real_path','real_executable','location','state'] if value.get(k) is not None) or 'No record'
            records.append({'id':ident(str(event.get('generation'))+str(c.get('id'))+kind),'time':event.get('observed_at'),'kind':kind,'name':str(c.get('id','Unknown record')),'summary':'First observation; installation time is not established.' if kind=='BASELINE' else 'Recorded metadata difference; discovery time is not necessarily installation time.','before':human(before),'after':human(after),'generation':event.get('generation'),'source':'Sentinel change history','report_id':None})
            if len(records) >= 8000: break
        if len(records) >= 8000: break
    return sorted(records,key=lambda x:x.get('time') or '',reverse=True)

def build_data():
    config = load(ROOT/'config.json',{})
    generation = (ROOT/'current').resolve()
    inventory = {}; graph = {}; pmap = {}
    if (ROOT/'current').exists():
        if generation.parent != ROOT/'generations': raise ValueError('Current pointer is outside owned generations')
        inventory = load(generation/'SOFTWARE-INVENTORY.json',{})
        graph = load(generation/'CAPABILITY-GRAPH.json',{})
        pmap = load(generation/'PROJECT-MAP.json',{})
        if not inventory: raise ValueError('No valid inventory')
        if any(x.get('generation') != inventory.get('generation') for x in [graph,pmap]): raise ValueError('Inconsistent generation')
    REPORTS.clear()
    for name in ['SOFTWARE-INVENTORY.json','ENVIRONMENTS.json','CAPABILITY-GRAPH.json','PROJECT-MAP.json','CURRENT-STATUS.md','SESSION-BRIEF.md']:
        register_report(generation/name,'Current Sentinel · '+name)
    envs = []; names = {}
    for e in inventory.get('environments',[]):
        name = env_name(e); names[e['id']] = name
        envs.append({'id':e['id'],'name':name,'kind':e.get('kind','unknown'),'interpreter':e.get('interpreter'),'prefix':e.get('prefix'),'python_version':e.get('python_version','Unknown'),'owner_context':e.get('owner_context','unknown'),'status':e.get('state','UNKNOWN'),'package_count':len(e.get('packages',[])),'conda_package_count':len(e.get('conda_packages',[])),'observed_at':e.get('observed_at'),'kernels':[]})
    caps = []; lookup = {}
    for c in graph.get('capabilities',[]):
        name = c.get('package',c.get('name',c['id'])); status = verification_state(c.get('state','UNKNOWN'),c.get('last_functional_verification_at'))
        row = {'id':c['id'],'name':name,'package':name,'version':c.get('version'),'category':category(name),'environment':names.get(c.get('environment_id'),'System tools'),'environment_id':c.get('environment_id'),'interpreter':c.get('interpreter') or c.get('path'),'status':status,'label':LABELS.get(status,status),'operations':[c.get('supported_operation','Recorded tool')],'verified_at':c.get('last_functional_verification_at'),'observed_at':c.get('last_observation_at'),'report_id':register_report(c['evidence'],name+' verification') if c.get('evidence') else None,'limitations':c.get('known_limitations',[])}
        caps.append(row); lookup[c['id']] = row
    software = []
    def add(name,version,location,environment,eid,interpreter,status='INSTALLED',source='Package metadata',updated=None,capability=None):
        c = capability or lookup.get(eid+':'+norm(name),{}); status = c.get('status',status)
        software.append({'id':ident(eid+':'+source+':'+norm(name)),'name':name,'version':version or 'Unknown','category':category(name),'location':location or 'Not recorded','environment':environment,'environment_id':eid,'interpreter':interpreter,'status':status,'label':LABELS.get(status,status),'observed_at':c.get('observed_at') or inventory.get('observed_at'),'verified_at':c.get('verified_at'),'updated_at':updated,'capabilities':c.get('operations',[]),'report_id':c.get('report_id'),'source_kind':source})
    for e in inventory.get('environments',[]):
        seen = set(); eid = e['id']
        for p in e.get('packages',[]):
            seen.add((norm(p['name']),p.get('version')))
            add(p['name'],p.get('version'),p.get('location'),names[eid],eid,e['interpreter'],status=e.get('state','INSTALLED'),source='Python distribution',updated=iso_mtime(Path(p.get('metadata_path','/nonexistent'))/'METADATA'))
        for p in e.get('conda_packages',[]):
            if (norm(p['name']),p.get('version')) not in seen: add(p['name'],p.get('version'),p.get('location',e.get('prefix')),names[eid],eid,e['interpreter'],source='Conda package',updated=iso_mtime(p.get('metadata_path','/nonexistent')))
    for p in inventory.get('arch_packages',{}).get('packages',[]): add(p['name'],p.get('version'),'Native package database','Arch Linux','arch-system',None,source='Arch package')
    for t in inventory.get('tools',[]): add(t['name'],t.get('version'),t.get('real_path',t.get('path')),'System command line','system-tools',t.get('path'),status=t.get('state','INSTALLED'),source='Executable',capability=lookup.get(t['id']))
    projects = []
    for p in pmap.get('projects',[]):
        path = Path(p['path']); reports = []
        # Project source is never opened implicitly: reports must be explicitly configured.
        for item in config.get('dashboard_reports',[]):
            if item.get('project_path') == str(path):
                rid = register_report(item['path'],item.get('title'))
                if rid: reports.append({'id':rid,'title':item.get('title',Path(item['path']).name)})
        projects.append({'id':ident(str(path)),'name':p.get('name',path.name),'path':str(path),'owner_context':p.get('owner_context','unknown'),'status':'UNKNOWN' if p.get('state')=='DISCOVERED' else p.get('state','UNKNOWN'),'label':'Source found; runtime not verified' if p.get('state')=='DISCOVERED' else p.get('state','UNKNOWN'),'summary':p.get('historical_status','Registered project. Availability does not prove functional acceptance.'),'observed_at':p.get('observed_at'),'reports':reports,'service_ids':p.get('service_ids',[]),'limitations':['Historical project notes do not establish current service state.']})
    history = report_history(config); changes = change_rows()
    ai = {'cpu_verified':False,'cuda_available':None,'gpu_verified':False,'evidence_report_id':None}
    for cap in caps:
        if norm(cap['package']) != 'torch' or cap['status'] != 'FUNCTIONALLY_VERIFIED': continue
        raw = lookup.get(cap['id']); source = next((c for c in graph.get('capabilities',[]) if c['id']==cap['id']),{})
        evidence = load(source.get('evidence','/nonexistent'),{})
        try: tensor = json.loads(evidence.get('output','{}'))
        except (TypeError,ValueError): tensor = {}
        if tensor.get('cpu_tensor') == 'FUNCTIONALLY_VERIFIED':
            ai.update(cpu_verified=True,cuda_available=tensor.get('cuda_available'),gpu_verified=tensor.get('gpu_operation')=='FUNCTIONALLY_VERIFIED',evidence_report_id=cap['report_id'])
    unfinished = [{'id':'unverified','title':'Unverified tools need named operation checks','summary':str(sum(c['status']!='FUNCTIONALLY_VERIFIED' for c in caps))+' capability records do not have current functional verification.','status':'UNKNOWN','report_id':None}]
    return {'meta':{'generation':inventory.get('generation'),'observed_at':inventory.get('observed_at'),'errors':inventory.get('errors',[]),'counts':{'software':len(software),'environments':len(envs),'projects':len(projects),'verified_capabilities':sum(c['status']=='FUNCTIONALLY_VERIFIED' for c in caps),'capabilities':len(caps),'history':len(history),'changes':len(changes)},'limitations':['Software records are per environment and metadata source, not a count of independent applications.','Initial observation does not establish installation time.','Named operations only are verified. Configured application endpoints have read-only status/Open in this portable release.'],'ai':ai,'state_dir':str(ROOT)},'software':sorted(software,key=lambda s:s['name'].lower()),'environments':envs,'projects':projects,'capabilities':caps,'history':history,'changes':changes,'unfinished':unfinished,'reports':[{k:v for k,v in r.items() if k!='resolved'} for r in REPORTS.values()]}

def get_data():
    with LOCK:
        paths = [ROOT/'current',ROOT/'config.json',ROOT/'runtime/control-actions.jsonl']
        signature = tuple((str(p.resolve()),p.stat().st_mtime_ns if p.exists() else None) for p in paths)
        if CACHE.get('signature') != signature or time.monotonic()-CACHE.get('at',0)>30:
            CACHE.update(data=build_data(),signature=signature,at=time.monotonic())
        result = copy.deepcopy(CACHE['data']); meta = result['meta']
        try: age = (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(meta['observed_at'])).total_seconds()
        except (TypeError,ValueError): age = None
        markers = [{'source':name,'detail':load(ROOT/'runtime'/name,{'error':'Unreadable marker'})} for name in ['dirty.json','last-error.json','launcher-last-error.json'] if (ROOT/'runtime'/name).exists()]
        meta.update(age_seconds=round(age,1) if age is not None else None,freshness='STALE' if markers or meta['errors'] or age is None or age>86400 else 'CURRENT',errors=list(meta['errors'])+markers,control_url=load(ROOT/'runtime/control-public.json',{}).get('url'))
        # Re-evaluate age even while the snapshot/model cache is unchanged.
        for row in result['capabilities']+result['software']:
            state = verification_state(row['status'],row.get('verified_at')); row.update(status=state,label=LABELS.get(state,state))
        meta['counts']['verified_capabilities'] = sum(c['status']=='FUNCTIONALLY_VERIFIED' for c in result['capabilities'])
        return result
