"""Bounded metadata refresh followed by exec of an explicitly selected program."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
from . import core
from .config import state_dir
MARKER='GENESIS_SENTINEL_PREPARING'

def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir');parser.add_argument('--original',required=True)
    parser.add_argument('args',nargs=argparse.REMAINDER);parsed=parser.parse_args(args)
    remaining=parsed.args[1:] if parsed.args[:1]==['--'] else parsed.args
    original=Path(parsed.original).absolute();root=state_dir(parsed.state_dir)
    if not original.is_file() or not os.access(original,os.X_OK):parser.error('original is not an executable file')
    # An owned wrapper may never be reconfigured as its own original.
    record=core.load(root/'runtime/integration.json',{});wrapper=record.get('launcher') or {}
    if wrapper.get('path') and original.resolve()==Path(wrapper['path']).resolve():parser.error('recursive original executable rejected')
    if not os.environ.get(MARKER) and not any(x in remaining for x in ['-h','--help','-V','--version']):
        env=os.environ.copy();env[MARKER]='1'
        command=[sys.executable,'-m','genesis_sentinel','--state-dir',str(root),'refresh','--quick']
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,env=env)
        try:
            result=process.wait(timeout=30)
            if result:raise RuntimeError('inventory refresh failed')
            (root/'runtime/launcher-last-error.json').unlink(missing_ok=True)
        except (subprocess.TimeoutExpired,RuntimeError) as error:
            if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
            core.atomic(root/'runtime/launcher-last-error.json',{'at':core.now(),'state':'STALE','error':str(error),'last_valid_snapshot_retained':True})
            print('[Sentinel] Refresh unavailable; last snapshot is stale. Continuing to the original program.',file=sys.stderr)
    os.environ.pop(MARKER,None)
    os.execv(str(original),[str(original),*remaining])
    return 0
if __name__=='__main__':raise SystemExit(main())
