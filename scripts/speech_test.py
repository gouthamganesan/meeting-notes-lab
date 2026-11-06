"""Local speech API integration checks with generated, non-private audio."""
import json
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import server

ROOT = Path(__file__).resolve().parents[1]
(ROOT / "logs").mkdir(exist_ok=True)
c = TestClient(server.app)
report=[]
voices=c.get('/api/tts/voices').json()['voices']
assert any(voice["id"] == "base:en-Carter_man" for voice in voices), "Install the base speech presets first"
payload=dict(text='Welcome to your local voice studio. Create speech, capture a thought, or turn a video into subtitles.', voice='base:en-Carter_man', steps=5,guidance=1.5,seed=42)
assert c.post('/api/tts',json={**payload,'voice':'not-installed'}).status_code==400
assert c.post('/api/tts',json={**payload,'text':'Hi'}).status_code==422
r=c.post('/api/tts',json=payload);assert r.status_code==200,r.text
id=r.json()['id']
for _ in range(180):
 job=c.get('/api/tts/jobs/'+id).json()
 if job['status'] in ('done','error','cancelled'):break
 time.sleep(1)
assert job['status']=='done',job
assert len(job['chunks'])>1
wav=c.get(job['audio_url']);assert wav.status_code==200 and wav.content[:4]==b'RIFF'
report.append({'test':'Speech API, installed voices, validation, streaming WAV chunks and final WAV','passed':True,'metrics':job['metrics']})
r=c.post('/api/files',files={'file':('generated.wav',wav.content,'audio/wav')},data={'hotwords':'VibeVoice'})
assert r.status_code==200,r.text
id=r.json()['id']
for _ in range(180):
 job=c.get('/api/jobs/'+id).json()
 if job['status'] in ('done','error'):break
 time.sleep(1)
assert job['status']=='done',job
assert all(phrase in job['text'].lower() for phrase in ['voice studio', 'create speech', 'capture a thought', 'subtitles']),job
assert 'srt' in job['downloads'] and 'json' in job['downloads'],job
for url in job['downloads'].values():assert c.get(url).status_code==200
report.append({'test':'Generated speech round-trip transcription, vocabulary hints, TXT/SRT/JSON downloads','passed':True,'transcript':job['text']})
r=c.post('/api/tts',json={**payload,'text':payload['text']*20});id=r.json()['id']
assert c.post('/api/tts',json=payload).status_code==400
assert c.post('/api/tts/jobs/'+id+'/cancel').status_code==200
for _ in range(60):
 job=c.get('/api/tts/jobs/'+id).json()
 if job['status'] in ('done','error','cancelled'):break
 time.sleep(1)
assert job['status']=='cancelled',job
report.append({'test':'Cancellation and concurrent job rejection','passed':True})
server.engine.close()
(ROOT/'logs/speech-api-tests.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
