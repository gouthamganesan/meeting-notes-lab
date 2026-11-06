#!/usr/bin/env python3
"""Reproduce the compact transcription runtime. No accounts or paid services."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'model-manifest.json').read_text())
SETUP = json.loads((ROOT / 'SETUP.json').read_text())

def run(*args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)

def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): digest.update(chunk)
    return digest.hexdigest()

def artifacts():
    repo='microsoft/VibeVoice-ASR-BitNet'; info=MANIFEST[repo]
    for item in info['files']:
        name=item['rfilename']
        yield ROOT/'models/asr-bitnet'/name, f"https://huggingface.co/{repo}/resolve/{info['revision']}/{name}", item['lfs']['sha256']
    info=MANIFEST['snakers4/silero-vad']
    yield ROOT/'models/silero-vad/silero_vad.onnx', f"https://raw.githubusercontent.com/snakers4/silero-vad/{info['revision']}/src/silero_vad/data/silero_vad.onnx", info['sha256']

def download(path,url,expected):
    if path.exists():
        if sha256(path)==expected:
            print('Verified',path.name,flush=True);return
        raise RuntimeError(f'{path} has an unexpected checksum. Move it aside before retrying.')
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.part')
    print('Downloading',path.name,flush=True)
    request=urllib.request.Request(url,headers={'User-Agent':'Meeting-Notes-Lab-Setup'})
    with urllib.request.urlopen(request,timeout=120) as response, temporary.open('wb') as out:
        shutil.copyfileobj(response,out,1024*1024)
    if sha256(temporary)!=expected:raise RuntimeError(f'Checksum mismatch: {temporary}. Final model was not changed.')
    temporary.replace(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Verify existing model checksums and binary, without downloads or installs')
    args=parser.parse_args()
    if args.check:
        for path,_,expected in artifacts():
            assert path.exists() and sha256(path)==expected, f'Missing or invalid model: {path}'
            print('Verified',path.name)
        assert (ROOT/'vendor/VibeASR.cpp/build-local/bin/asr_stream_server').is_file(), 'Build the ASR binary first'
        print('Compact runtime files verified.');return
    if not shutil.which('uv'):raise SystemExit('Install uv from https://docs.astral.sh/uv/ then rerun this script.')
    if not shutil.which('git'):raise SystemExit('Install Git and the Xcode command-line tools first.')
    if not (ROOT/'.venv/bin/python').exists():run('uv','venv','--python','3.11','.venv')
    run('uv','pip','install','--python','.venv/bin/python','-r','requirements.txt')
    info=SETUP['sources']['VibeASR.cpp'];source=ROOT/'vendor/VibeASR.cpp'
    if not source.exists():
        source.parent.mkdir(exist_ok=True)
        run('git','clone','--no-checkout',info['url'],source)
        run('git','-C',source,'checkout','--detach',info['commit'])
    else:
        head=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        if head!=info['commit']:raise SystemExit('Existing VibeASR.cpp revision differs. Preserve your checkout and resolve it before setup.')
    run('git','-C',source,'submodule','update','--init','--recursive')
    run(ROOT/'.venv/bin/cmake','-S',source,'-B',source/'build-local','-DCMAKE_BUILD_TYPE=Release','-DLLAMA_CURL=OFF','-DCMAKE_POLICY_VERSION_MINIMUM=3.5')
    run(ROOT/'.venv/bin/cmake','--build',source/'build-local','--target','asr_infer','asr_stream_server','-j','6')
    for artifact in artifacts():download(*artifact)
    print('Ready. Run ./start.command or .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 7860')

if __name__=='__main__':main()
