"""Portable Linux software inventory with explicit capability verification."""
import argparse
import json
import os
from pathlib import Path
import sys
from . import __version__, core
from .config import state_dir,validate_config

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version',action='version',version='GENESIS Sentinel '+__version__)
    p.add_argument('--state-dir',help='private state directory (or GENESIS_SENTINEL_HOME / XDG_STATE_HOME)')
    commands=p.add_subparsers(dest='command',required=True)
    i=commands.add_parser('init');i.add_argument('--config',help='copy a JSON template without changing its interpreter/project paths')
    r=commands.add_parser('refresh');mode=r.add_mutually_exclusive_group();mode.add_argument('--quick',action='store_true');mode.add_argument('--full',action='store_true')
    commands.add_parser('status');commands.add_parser('report');commands.add_parser('brief')
    v=commands.add_parser('verify');v.add_argument('capability_id')
    d=commands.add_parser('mark-dirty');d.add_argument('reason',nargs='+')
    r=commands.add_parser('register-root');r.add_argument('path');r.add_argument('--tool',action='store_true')
    e=commands.add_parser('register-python');e.add_argument('interpreter')
    e=commands.add_parser('recover');e.add_argument('generation')
    e=commands.add_parser('integrate');e.add_argument('--guidance',required=True);e.add_argument('--launcher');e.add_argument('--original')
    commands.add_parser('unintegrate')
    d=commands.add_parser('dashboard');d.add_argument('action',choices=['start','stop','restart','status','access']);d.add_argument('--port',type=int)
    return p

def main(argv=None):
    args=parser().parse_args(argv);root=state_dir(args.state_dir)
    root.mkdir(parents=True,exist_ok=True,mode=0o700);root.chmod(0o700)
    try:
        if args.command=='init':
            with core.writer(root):
                if (root/'config.json').exists():raise ValueError('config.json exists; initialization never overwrites it')
                value=core.load(args.config) if args.config else core.default_config()
                core.atomic(root/'config.json',validate_config(value))
            print('Initialized '+str(root))
        elif args.command=='refresh':core.refresh(root,args.full)
        elif args.command=='status':core.status(root)
        elif args.command in ['report','brief']:
            path=root/('CURRENT-STATUS.md' if args.command=='report' else 'SESSION-BRIEF.md')
            if not path.is_file():raise ValueError('no saved snapshot; run refresh first')
            print(path.read_text(),end='')
        elif args.command=='verify':return 0 if core.verify(args.capability_id,root) else 1
        elif args.command=='mark-dirty':core.mark_dirty(root,' '.join(args.reason))
        elif args.command in ['register-root','register-python']:
            path=Path(args.path if args.command=='register-root' else args.interpreter).expanduser()
            if not path.is_absolute():raise ValueError('register an absolute path')
            if args.command=='register-root' and not path.is_dir():raise ValueError('project root must exist')
            if args.command=='register-python' and (not path.is_file() or not os.access(path,os.X_OK)):raise ValueError('interpreter must exist and be executable')
            # Resolve only environment parent, preserving a venv executable symlink.
            canonical=str(path.resolve()) if args.command=='register-root' else str(path.parent.resolve()/path.name)
            with core.writer(root):
                cfg=core.load_config(root)
                if args.command=='register-python':
                    if canonical not in cfg['interpreters']:cfg['interpreters'].append(canonical)
                elif args.tool:
                    if canonical not in cfg['tool_roots']:cfg['tool_roots'].append(canonical)
                elif canonical not in [e['path'] for e in cfg['projects']+cfg['extra_roots']]:cfg['extra_roots'].append({'path':canonical,'name':path.name})
                core.atomic(root/'config.json',validate_config(cfg));core.mark_dirty(root,'registered local path')
        elif args.command=='recover':print(core.recover(root,args.generation))
        elif args.command=='integrate':
            from .integration import install
            print(json.dumps(install(root,args.guidance,args.launcher,args.original),indent=2))
        elif args.command=='unintegrate':
            from .integration import uninstall
            print(json.dumps(uninstall(root),indent=2))
        elif args.command=='dashboard':
            os.environ['GENESIS_SENTINEL_HOME']=str(root)
            from .control_lifecycle import main as dashboard_main
            return dashboard_main([args.action]+(['--port',str(args.port)] if args.port else []))
        return 0
    except Exception as error:
        core.atomic(root/'runtime/last-error.json',{'at':core.now(),'error':str(error),'last_valid_snapshot_retained':True})
        print('Sentinel: '+str(error),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
