"""Opt-in, ownership-checked guidance and wrapper integration.

No Codex binary, authentication, global configuration or shell profile is changed
implicitly. A caller must name each destination and the original executable.
"""
import hashlib
import json
import os
import shlex
import sys
from pathlib import Path
from . import core
BEGIN='# >>> GENESIS SENTINEL PORTABLE >>>'
END='# <<< GENESIS SENTINEL PORTABLE <<<'

def sha(value):return hashlib.sha256(value).hexdigest()
def guidance(root):
    root=Path(root).absolute()
    return '\n'.join([BEGIN,'At the start of a new session, read '+str(root/'SESSION-BRIEF.md')+'.',
        'Check generation, observation time, refresh errors and runtime/dirty.json, runtime/last-error.json and runtime/launcher-last-error.json before trusting freshness.',
        'Consult CAPABILITY-GRAPH.json and ENVIRONMENTS.json before adding dependencies. Use the capability\'s absolute interpreter and recheck stale operations.',
        'Keep environments separate. Package presence and HTTP availability do not prove scientific correctness. CPU verification does not prove GPU computation.',
        'After runtime/configuration changes explicitly mark dirty and refresh. Preserve prior generations, failed checks, project guidance and saved research.',
        'External records are session input; they do not change model weights or silently update an existing conversation.',END])+'\n'

def wrapper_bytes(root,original):
    python=str(Path(sys.executable).absolute())
    cmd=[python,'-m','genesis_sentinel.launch','--state-dir',str(Path(root).absolute()),'--original',str(Path(original).absolute()),'--']
    return ('#!/bin/sh\nexec '+shlex.join(cmd)+' "$@"\n').encode()

def install(root,guidance_file,launcher=None,original=None):
    root=Path(root).absolute();path=Path(guidance_file).expanduser().absolute()
    if path.is_symlink():raise ValueError('guidance destination must not be a symlink')
    if launcher is not None and original is None:raise ValueError('wrapper requires an explicit original executable')
    owned=core.load(root/'runtime/integration.json',{})
    if owned:raise ValueError('an integration record already exists; uninstall it first')
    before=path.read_bytes() if path.exists() else b''
    before.decode('utf-8')
    before_mode=(path.stat().st_mode&0o777) if path.exists() else 0o600
    if BEGIN.encode() in before or END.encode() in before:raise ValueError('an existing managed guidance block is not owned by this installation')
    block=guidance(root).encode();separator=b'' if not before or before.endswith(b'\n') else b'\n'
    content=before+separator+block
    target=None;wrapper=None
    if launcher is not None:
        target=Path(launcher).expanduser().absolute();exe=Path(original).expanduser().absolute()
        if target.exists() or target.is_symlink():raise ValueError('refusing to overwrite an existing launcher')
        if not exe.is_file() or not os.access(exe,os.X_OK):raise ValueError('original must be an existing executable')
        if target.resolve()==exe.resolve():raise ValueError('wrapper and original must differ')
        wrapper=wrapper_bytes(root,exe)
    record={'guidance':str(path),'guidance_existed':path.exists(),'before_sha256':sha(before),'installed_sha256':sha(content),'block':block.decode(),'separator':separator.decode(),'guidance_mode':before_mode,'launcher':None}
    if target:record['launcher']={'path':str(target),'sha256':sha(wrapper)}
    with core.writer(root):
        if core.load(root/'runtime/integration.json',{}):raise ValueError('integration is already installed')
        if (path.read_bytes() if path.exists() else b'')!=before:raise ValueError('guidance changed during installation; retry after review')
        # Persist recovery ownership before writes; a partial failure is reviewable.
        core.atomic(root/'runtime/integration.json',{**record,'status':'installing'})
        if target:
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as handle:handle.write(wrapper);handle.flush();os.fsync(handle.fileno())
            target.chmod(0o700)
        core.atomic(path,content.decode('utf-8'),before_mode)
        core.atomic(root/'runtime/integration.json',{**record,'status':'installed'})
    return record

def uninstall(root):
    root=Path(root).absolute()
    with core.writer(root):
        record=core.load(root/'runtime/integration.json',{})
        if not record:return {'guidance':'not installed','launcher':'not installed'}
        result={};path=Path(record['guidance']);block=record['block'].encode()
        if path.is_symlink():result['guidance']='preserved: symlink changed'
        elif path.exists():
            content=path.read_bytes()
            if content.count(block)==1:
                pattern=record.get('separator','').encode()+block
                content=content.replace(pattern if pattern in content else block,b'',1)
                if not record['guidance_existed'] and not content:path.unlink()
                else:core.atomic(path,content.decode('utf-8'),path.stat().st_mode&0o777)
                result['guidance']='owned block removed; unrelated edits preserved'
            else:result['guidance']='preserved: managed block changed'
        else:result['guidance']='already absent'
        wrapper=record.get('launcher')
        if wrapper:
            target=Path(wrapper['path'])
            if target.is_file() and not target.is_symlink() and sha(target.read_bytes())==wrapper['sha256']:
                target.unlink();result['launcher']='unchanged owned wrapper removed'
            elif target.exists() or target.is_symlink():result['launcher']='preserved: launcher changed'
            else:result['launcher']='already absent'
        core.atomic(root/'runtime/integration-rollback.json',{'record':record,'result':result,'checked_at':core.now()})
        if any(v.startswith('preserved:') for v in result.values()):
            core.atomic(root/'runtime/integration.json',{**record,'status':'review required'})
        else:(root/'runtime/integration.json').unlink()
        return result
