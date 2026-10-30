#!/usr/bin/env python3
"""Audit explicit public tree/archive inputs without serializing matched secrets."""
import argparse,datetime,hashlib,json,re,tarfile,zipfile
from pathlib import Path
PATTERNS=[re.compile(x) for x in [rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',rb'\bgh[pousr]_[A-Za-z0-9]{25,}',rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}',rb'\bAKIA[0-9A-Z]{16}\b']]
DENY_DIRS={'private','.ssh','.codex','generations','runtime','venvs','.venv','.qa','.release-work','node_modules','__pycache__'}
DENY_FILES={'auth.json','hosts.yml','id_rsa','id_ed25519','.env','.git-credentials','SOFTWARE-INVENTORY.json','ENVIRONMENTS.json','PROJECT-MAP.json','CAPABILITY-GRAPH.json','CHANGES.jsonl','CONTROL-BASELINE.json'}
def inspect(name,raw):
 parts=Path(name).parts
 issues=[]
 if any(p in DENY_DIRS for p in parts) or Path(name).name in DENY_FILES:issues.append('forbidden operational/private path')
 if any(p.search(raw) for p in PATTERNS):issues.append('credential/private-key pattern')
 return issues

def main():
 p=argparse.ArgumentParser();p.add_argument('paths',nargs='+');p.add_argument('--output',required=True);a=p.parse_args();items=[];issues=[]
 def item(name,raw):
  found=inspect(name,raw);items.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
  if found:issues.append({'path':name,'issues':found})
 for name in a.paths:
  path=Path(name)
  if path.is_dir():
   for f in sorted(path.rglob('*')):
    rel=f.relative_to(path)
    if any(x in {'.git','.qa','.release-work','dist','build','__pycache__'} or x.endswith('.egg-info') for x in rel.parts):continue
    if f.is_file():item(str(rel),f.read_bytes())
  elif zipfile.is_zipfile(path):
   with zipfile.ZipFile(path) as z:
    for entry in z.infolist():
     if not entry.is_dir():item(path.name+'/'+entry.filename,z.read(entry))
  elif tarfile.is_tarfile(path):
   with tarfile.open(path) as t:
    for entry in t:
     if entry.isfile():item(path.name+'/'+entry.name,t.extractfile(entry).read())
     if entry.issym() or entry.islnk():issues.append({'path':entry.name,'issues':['archive link requires manual review']})
  else:item(path.name,path.read_bytes())
 result={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS' if not issues else 'FAIL','files_checked':len(items),'issues':issues,'files':items,'limitations':'Pattern/path audit, not a proof against every secret. Public staging is allowlisted separately; active-secret comparison is performed privately on the release host.'}
 target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','files_checked','issues']}));return bool(issues)
if __name__=='__main__':raise SystemExit(main())
