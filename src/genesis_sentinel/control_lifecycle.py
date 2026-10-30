"""Identity-checked lifecycle of the portable loopback control center."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from .config import state_dir
from . import control_server as server
from .control_services import identity
B=state_dir();P=B/'private/control';R=B/'runtime'
def configure(root):
    global B,P,R
    B=Path(root);P=B/'private/control';R=B/'runtime';server.configure(B)
def owned(record):
    info=identity(record.get('pid',0))
    return bool(info and info==record.get('identity') and 'genesis_sentinel.control_server' in info.get('args',[]))
def live(record):
    if not owned(record): return False
    try:
        op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open(record['url']+'api/session',timeout=3) as f:
            return f.status==200 and isinstance(json.load(f).get('authenticated'),bool)
    except (OSError,ValueError,KeyError): return False
def status():
    record=server.read(P/'process.json');okay=live(record)
    out={'url':record.get('url',server.read(R/'control-public.json').get('url','http://127.0.0.1:8091/')),'state':'RUNNING' if okay else 'UNKNOWN' if owned(record) else 'STOPPED','owned':owned(record),'observed_at':server.now(),'access_helper':'genesis-sentinel-dashboard access','state_dir':str(B)}
    server.atomic(R/'control-public.json',{**server.read(R/'control-public.json'),**out},0o600)
    return out
def start(preferred_port=8091):
    record=server.read(P/'process.json')
    if live(record): return status()
    if owned(record): raise RuntimeError('Owned control center is not ready; inspect its private server.log. No duplicate started.')
    port=None
    for candidate in range(preferred_port,min(preferred_port+9,65536)):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            try: sock.bind(('127.0.0.1',candidate));port=candidate;break
            except OSError: continue
    if port is None: raise RuntimeError('No free port in requested range; no existing process stopped.')
    server.access();log=P/'server.log';env=os.environ.copy();env['GENESIS_SENTINEL_HOME']=str(B)
    with log.open('ab') as out:
        log.chmod(0o600)
        child=subprocess.Popen([sys.executable,'-m','genesis_sentinel.control_server','--port',str(port)],stdin=subprocess.DEVNULL,stdout=out,stderr=out,start_new_session=True,env=env)
    record={'pid':child.pid,'url':'http://127.0.0.1:'+str(port)+'/', 'started_at':server.now()}
    for _ in range(30):
        info=identity(child.pid)
        if 'genesis_sentinel.control_server' in info.get('args',[]): record['identity']=info;break
        if child.poll() is not None: break
        time.sleep(.1)
    server.atomic(P/'process.json',record)
    for _ in range(40):
        if live(record): return status()
        if child.poll() is not None: break
        time.sleep(.25)
    raise RuntimeError('Control center did not become ready; inspect private/control/server.log.')
def stop():
    record=server.read(P/'process.json')
    if owned(record):
        active=[p for p in R.glob('control-action-*.json') if server.read(p).get('status') in ['queued','running']]
        if active: raise RuntimeError('A management action is active; wait before stopping the control center.')
        os.killpg(record['pid'],signal.SIGTERM)
        for _ in range(40):
            if not owned(record): break
            time.sleep(.15)
        if owned(record): raise RuntimeError('Owned control center is still stopping; no force kill sent.')
    elif identity(record.get('pid',0)): raise RuntimeError('Recorded PID belongs to another process; nothing stopped.')
    return status()
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir');parser.add_argument('--port',type=int,default=8091)
    parser.add_argument('command',choices=['start','stop','restart','status','access'])
    args=parser.parse_args(argv)
    if not 1024<=args.port<=65535: parser.error('Choose a nonprivileged port (1024..65535).')
    configure(state_dir(args.state_dir));server.setup_storage()
    with (P/'lifecycle.lock').open('a') as lock:
        deadline=time.monotonic()+15
        while True:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>deadline: raise SystemExit('Control-center lifecycle is busy; retry shortly.')
                time.sleep(.1)
        try:
            if args.command=='access':
                if not sys.stdout.isatty(): raise RuntimeError('Access requires an operator terminal; passwords are not written to logs.')
                info=status();credentials=server.access();print(info['url']+'\nUsername: '+credentials['username']+'\nPassword: '+credentials['password']);return 0
            if args.command=='restart': stop();result=start(args.port)
            elif args.command=='start': result=start(args.port)
            else: result=globals()[args.command]()
            print(result['state']+': '+result['url']);return 0
        except RuntimeError as e: raise SystemExit(str(e))
if __name__=='__main__': raise SystemExit(main())
