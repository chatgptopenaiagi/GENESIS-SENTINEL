#!/usr/bin/env python3
"""Build the Python distributions and an offline Linux installer bundle.

Run with an existing build/setuptools/wheel environment. No dependency installs.
"""
import argparse,gzip,hashlib,io,json,os,platform,subprocess,sys,tarfile
from pathlib import Path
B=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--platform',default='linux-aarch64',choices=['linux-aarch64','linux-x86_64']);p.add_argument('--skip-python-build',action='store_true');a=p.parse_args();dist=B/'dist';dist.mkdir(exist_ok=True)
 if not a.skip_python_build:subprocess.run([sys.executable,'-m','build','--no-isolation','--outdir',str(dist)],cwd=B,check=True)
 wheel=dist/'genesis_arch_sentinel-0.1.0-py3-none-any.whl'
 if not wheel.is_file():raise SystemExit('Build the wheel first.')
 files={wheel.name:wheel,'install.sh':B/'tools/install.sh'}
 for n in ['INSTALL.md','RECOVERY.md','ARCHITECTURE.md','THEORY.md','LICENSE','README.md']:files[n]=B/n
 for root in ['docs','examples']:
  for path in sorted((B/root).rglob('*')):
   if path.is_file():files[str(path.relative_to(B))]=path
 archive=dist/f'genesis-sentinel-0.1.0-{a.platform}.tar.gz';epoch=int(os.environ.get('SOURCE_DATE_EPOCH','315532800'))
 with archive.open('wb') as out,gzip.GzipFile(filename='',mode='wb',fileobj=out,mtime=epoch) as gz,tarfile.open(fileobj=gz,mode='w') as tar:
  for name,path in sorted(files.items()):
   raw=path.read_bytes();info=tarfile.TarInfo('genesis-sentinel-0.1.0/'+name);info.size=len(raw);info.mode=0o755 if name=='install.sh' else 0o644;info.mtime=epoch;tar.addfile(info,io.BytesIO(raw))
 print(json.dumps({'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(files),'scope':'Offline installer wrapping the included Python wheel; no native standalone executable.'}))
if __name__=='__main__':main()
