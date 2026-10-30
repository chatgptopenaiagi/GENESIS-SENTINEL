"""Explicit local state and bounded discovery configuration; no deployment paths."""
import copy
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

def state_dir(value=None):
    value = value or os.environ.get('GENESIS_SENTINEL_HOME')
    if value:
        return Path(value).expanduser().absolute()
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))).expanduser().absolute()/'genesis-sentinel'

def default_config():
    home=Path.home()
    roots=[]
    for p in [os.environ.get('CONDA_PREFIX'), *[str(home/name) for name in ['anaconda3','miniconda3','miniforge3','mambaforge']]]:
        if p and (Path(p)/'conda-meta').is_dir() and str(Path(p).absolute()) not in roots:
            roots.append(str(Path(p).absolute()))
    return {'schema_version':1,'interpreters':[str(Path(sys.executable).absolute())],
            'conda_roots':roots,'conda_registry_files':[str(home/'.conda/environments.txt')],
            'projects':[],'extra_roots':[],'tool_roots':[],
            'tool_names':['octave-cli','obabel','gnuplot','sqlite3','gcc','g++','gfortran','clang','cmake','make','git','node','npm','R','julia','ollama','llama-cli','jupyter','nvidia-smi','codex'],
            'services':[],'scientific_registries':[],'verification_ttl_hours':24,
            'collect_arch_packages':True,'arch_package_db':'/var/lib/pacman/local'}

def validate_config(value):
    if not isinstance(value,dict) or value.get('schema_version',1)!=1:
        raise ValueError('config.json must be a schema_version 1 object')
    result=default_config();result.update(copy.deepcopy(value))
    for key in ['interpreters','conda_roots','conda_registry_files','tool_roots']:
        if not isinstance(result[key],list) or not all(isinstance(p,str) and Path(p).is_absolute() for p in result[key]):
            raise ValueError(key+' must contain absolute paths')
    for key in ['projects','extra_roots']:
        if not isinstance(result[key],list):raise ValueError(key+' must be a list')
        for item in result[key]:
            if not isinstance(item,dict) or not isinstance(item.get('path'),str) or not Path(item['path']).is_absolute():
                raise ValueError(key+' entries need an absolute path')
    if not isinstance(result['tool_names'],list) or not all(isinstance(x,str) and x and '/' not in x and '\\' not in x for x in result['tool_names']):
        raise ValueError('tool_names must contain executable basenames')
    ttl=result['verification_ttl_hours']
    if isinstance(ttl,bool) or not isinstance(ttl,(int,float)) or not 0<ttl<=87600:
        raise ValueError('verification_ttl_hours must be between 0 and 87600')
    if not isinstance(result['services'],list):raise ValueError('services must be a list')
    for item in result['services']:
        if not isinstance(item,dict):raise ValueError('services need a loopback port or URL')
        if 'url' in item:
            try:parts=urlsplit(item['url']);port=parts.port
            except (TypeError,ValueError):raise ValueError('service URL is malformed')
            if parts.scheme!='http' or parts.hostname not in ['127.0.0.1','localhost'] or parts.username or parts.password or parts.query or parts.fragment or not port:
                raise ValueError('service URL must be credential-free HTTP on loopback with an explicit port')
            if 'port' in item and item['port']!=port:raise ValueError('service URL and port differ')
            item['port']=port
        if isinstance(item.get('port'),bool) or not isinstance(item.get('port'),int) or not 1<=item['port']<=65535:
            raise ValueError('services need a numeric loopback port')
        item.setdefault('url','http://127.0.0.1:'+str(item['port'])+'/')
    if not isinstance(result['scientific_registries'],list):raise ValueError('scientific_registries must be a list')
    for item in result['scientific_registries']:
        if not isinstance(item,dict) or not all(isinstance(item.get(k),str) and Path(item[k]).is_absolute() for k in ['path','interpreter']):
            raise ValueError('scientific_registries need absolute path and interpreter')
    if not isinstance(result['collect_arch_packages'],bool):raise ValueError('collect_arch_packages must be boolean')
    return result
