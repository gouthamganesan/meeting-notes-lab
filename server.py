"""A local microphone and media-file transcription app, using VibeASR.cpp."""
from __future__ import annotations

import atexit
import json
import queue
import re
import subprocess
import threading
import textwrap
import uuid
import tts_engine
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import av
import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)
RATE = 24000
app = FastAPI(docs_url=None, redoc_url=None)
jobs: dict[str, dict] = {}
worker = ThreadPoolExecutor(max_workers=1)


@app.middleware("http")
async def local_requests(request: Request, call_next):
    # Do not let unrelated websites post recordings to a local service.
    host = request.headers.get("host", "").split(":")[0]
    if host not in {"127.0.0.1", "localhost", "testserver"}:
        return JSONResponse({"detail": "Local access only"}, status_code=403)
    origin = request.headers.get("origin")
    if origin and origin not in {"http://127.0.0.1:7860", "http://localhost:7860"}:
        return JSONResponse({"detail": "Local access only"}, status_code=403)
    return await call_next(request)


class Engine:
    """One warm model process; serialize requests and bound protocol waits."""
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        self.lines = queue.Queue()
        self.log = None

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        if self.log:
            self.log.close()
            self.log = None

    def _read(self, timeout=180):
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty:
            self.close()
            raise RuntimeError("The transcription engine timed out. Please try again.")
        if line is None:
            self.close()
            raise RuntimeError("The transcription engine stopped. See logs/asr-engine.log.")
        return line

    def _start(self):
        if self.process and self.process.poll() is None:
            return
        self.close()
        self.lines = queue.Queue()
        (ROOT / "logs").mkdir(exist_ok=True)
        self.log = (ROOT / "logs/asr-engine.log").open("a")
        command = [str(ROOT / "vendor/VibeASR.cpp/build-local/bin/asr_stream_server"),
            "--vae-model", str(ROOT / "models/asr-bitnet/vibeasr-vae-encoder-i8_s.gguf"),
            "--lm-model", str(ROOT / "models/asr-bitnet/vibeasr-lm-i2_s-embed-q6_k.gguf"),
            "-t", "4", "--greedy", "--max-tokens", "4096", "--no-token-stream"]
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, text=True, bufsize=1)
        process, lines = self.process, self.lines
        def read_lines():
            for line in process.stdout:
                lines.put(line.rstrip("\n"))
            lines.put(None)
        threading.Thread(target=read_lines, daemon=True).start()
        if self._read() != "---READY---":
            self.close()
            raise RuntimeError("Could not load the model. See logs/asr-engine.log.")

    def transcribe(self, path: Path, format="text", hotwords=""):
        with self.lock:
            self._start()
            context = " ".join(hotwords.split())[:500]
            self.process.stdin.write(f"CONTEXT:{context}\n")
            self.process.stdin.flush()
            if self._read() != "---ACK---":
                self.close()
                raise RuntimeError("The engine did not accept the vocabulary hints.")
            self.process.stdin.write(f"FORMAT:{format}\n")
            self.process.stdin.flush()
            if self._read() != "---ACK---":
                self.close()
                raise RuntimeError("The transcription engine did not accept the request.")
            self.process.stdin.write(str(path.resolve()) + "\n")
            self.process.stdin.flush()
            output = []
            while True:
                line = self._read()
                if line == "---END---":
                    break
                output.append(line)
            text = "\n".join(output).strip()
            if "[ERROR]" in text:
                raise RuntimeError(text)
            return text


engine = Engine()
atexit.register(engine.close)


def decode_media(source: Path, target: Path, rate=RATE):
    """Stream audio to a mono WAV, retaining its start offset in a video."""
    first_time = None
    count = 0
    with av.open(str(source)) as container, sf.SoundFile(
        target, mode="w", samplerate=rate, channels=1, subtype="PCM_16"
    ) as wav:
        if not container.streams.audio:
            raise ValueError("That file has no audio track. Choose a video with sound or an audio file.")
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=rate)
        container_start = (container.start_time or 0) / av.time_base
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                if first_time is None:
                    first_time = max(0.0, float(converted.time or 0) - container_start)
                samples = converted.to_ndarray().reshape(-1)
                wav.write(samples)
                count += len(samples)
        for converted in resampler.resample(None):
            samples = converted.to_ndarray().reshape(-1)
            wav.write(samples)
            count += len(samples)
    if not count:
        raise ValueError("No audio could be read from that file.")
    return count / rate, first_time or 0.0


def speech_regions(wav: Path):
    """Find real speech boundaries; captions are phrase-level, not word-aligned."""
    import onnxruntime as ort
    vad_wav = wav.with_name("vad.wav")
    duration, _ = decode_media(wav, vad_wav, rate=16000)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(ROOT / "models/silero-vad/silero_vad.onnx"),
        sess_options=options, providers=["CPUExecutionProvider"])
    state = np.zeros((2, 1, 128), dtype=np.float32)
    context = np.zeros((1, 64), dtype=np.float32)
    probabilities, energy = [], []
    with sf.SoundFile(vad_wav) as audio:
        while len(frame := audio.read(512, dtype="float32")):
            frame = np.pad(frame, (0, 512-len(frame))).reshape(1, -1)
            joined = np.concatenate((context, frame), axis=1)
            probability, state = session.run(None, {"input": joined, "state": state,
                "sr": np.array(16000, dtype=np.int64)})
            context = joined[:, -64:]
            probabilities.append(float(probability.item()))
            energy.append(float(np.mean(frame**2)))
    step = 512 / 16000
    regions, start, silence = [], None, None
    for i, probability in enumerate(probabilities):
        if probability >= .5:
            if start is None:
                start = i
            silence = None
        elif probability < .35 and start is not None:
            if silence is None:
                silence = i
            if (i-silence)*step >= .24:
                if (silence-start)*step >= .12:
                    regions.append((start, silence))
                start, silence = None, None
    if start is not None:
        regions.append((start, len(probabilities)))
    # Very short isolated phrases make the compact decoder invent words.
    # Keep nearby phrases together to give it enough acoustic context.
    merged = []
    for start, end in regions:
        if merged:
            previous_start, previous_end = merged[-1]
            short = min(previous_end - previous_start, end - start) * step < 3.0
            if short and (start - previous_end) * step < 1.2 and (end - previous_start) * step <= 8:
                merged[-1] = (previous_start, end)
                continue
        merged.append((start, end))
    split = []
    for start, end in merged:
        while (end-start)*step > 8:
            lo, hi = start+int(5/step), start+int(8/step)
            boundary = lo + int(np.argmin(energy[lo:hi]))
            split.append((start*step, boundary*step))
            start = boundary
        split.append((start*step, min(duration, end*step)))
    padded = []
    for i, (start, end) in enumerate(split):
        left = 0 if i == 0 else (split[i-1][1]+start)/2
        right = duration if i == len(split)-1 else (end+split[i+1][0])/2
        padded.append((max(left, start-.12), min(right, end+.12)))
    return padded


def srt_time(seconds):
    ms = round(max(0, seconds) * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def make_srt(segments):
    blocks = []
    previous_end = 0.0
    for segment in segments:
        start = max(previous_end, segment["start"])
        end = segment["end"]
        if end <= start:
            continue
        text = textwrap.fill(segment["text"].replace("\r", " ").replace("\n", " "), width=60)
        blocks.append(f"{len(blocks)+1}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n")
        previous_end = end
    return "\n".join(blocks)


def process_file(job_id, source, hotwords=""):
    job = jobs[job_id]
    folder = OUTPUTS / job_id
    try:
        job.update(status="processing", message="Reading the audio track…")
        wav = folder / "audio.wav"
        duration, offset = decode_media(source, wav)
        job["duration"] = duration
        job["message"] = "Finding speech and subtitle boundaries…"
        regions = speech_regions(wav)
        segments, texts = [], []
        with sf.SoundFile(wav) as stream:
            for i, (start, end) in enumerate(regions):
                stream.seek(round(start * RATE))
                samples = stream.read(round((end-start) * RATE), dtype="float32")
                path = folder / "chunk.wav"
                sf.write(path, samples, RATE, subtype="PCM_16")
                text = engine.transcribe(path, "text", hotwords)
                if text:
                    segments.append({"start": offset+start, "end": offset+end, "text": text})
                    texts.append(text)
                job.update(progress=min(99, round((i+1) / len(regions) * 100)),
                    text="\n\n".join(texts), message="Transcribing…")
        text = "\n\n".join(texts)
        (folder / "transcript.txt").write_text(text, encoding="utf-8")
        (folder / "segments.json").write_text(json.dumps(segments, indent=2), encoding="utf-8")
        downloads = {"txt": f"/api/download/{job_id}/transcript.txt", "json": f"/api/download/{job_id}/segments.json"}
        if segments:
            (folder / "subtitles.srt").write_text(make_srt(segments), encoding="utf-8")
            downloads["srt"] = f"/api/download/{job_id}/subtitles.srt"
        job.update(status="done", progress=100, text=text, downloads=downloads,
            message="Ready. Subtitle timing follows speech phrases and pauses." if text else "No speech was detected.")
    except Exception as exc:
        job.update(status="error", message=str(exc))


async def save_upload(file: UploadFile, folder: Path):
    suffix = Path(file.filename or "recording.wav").suffix[:12]
    path = folder / ("source" + suffix)
    size = 0
    with path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > 4 * 1024**3:
                raise HTTPException(413, "Use a file smaller than 4 GB.")
            out.write(chunk)
    await file.close()
    return path


@app.get("/api/health")
def health():
    return {"status": "ready", "model": "VibeVoice-ASR-BitNet", "local": True}


@app.post("/api/files")
async def upload_file(file: UploadFile = File(...), hotwords: str = Form("", max_length=500)):
    job_id = uuid.uuid4().hex
    folder = OUTPUTS / job_id
    folder.mkdir()
    source = await save_upload(file, folder)
    jobs[job_id] = {"id": job_id, "status": "queued", "progress": 0,
                    "message": "Waiting for the transcription engine…", "text": ""}
    worker.submit(process_file, job_id, source, hotwords)
    return {"id": job_id}


@app.post("/api/live")
async def live(file: UploadFile = File(...), hotwords: str = Form("", max_length=500)):
    folder = OUTPUTS / ("live-" + uuid.uuid4().hex)
    folder.mkdir()
    source = await save_upload(file, folder)
    import asyncio
    def run():
        wav = folder / "audio.wav"
        duration, _ = decode_media(source, wav)
        if duration > 40:
            raise ValueError("Live chunks must be shorter than 40 seconds.")
        samples, _ = sf.read(wav)
        if len(samples) < RATE // 4 or np.max(np.abs(samples)) < 0.001:
            return {"text": ""}
        text = engine.transcribe(wav, "text", hotwords)
        (folder / "transcript.txt").write_text(text)
        return {"text": text}
    try:
        return await asyncio.get_running_loop().run_in_executor(worker, run)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/jobs/{job_id}")
def status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Recording not found. Please upload it again.")
    return jobs[job_id]


@app.get("/api/download/{job_id}/{filename}")
def download(job_id: str, filename: str):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id) or filename not in {"transcript.txt", "subtitles.srt", "segments.json"}:
        raise HTTPException(404)
    path = OUTPUTS / job_id / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, filename=filename, media_type="text/plain; charset=utf-8")



class SpeechRequest(BaseModel):
    text: str = Field(min_length=10, max_length=10000)
    voice: str = "base:en-Carter_man"
    steps: int = Field(default=5, ge=1, le=20)
    guidance: float = Field(default=1.5, ge=1.0, le=3.0)
    seed: int = Field(default=42, ge=0, le=2147483647)


@app.get("/api/tts/voices")
def speech_voices():
    return {"voices": tts_engine.catalog(), "sample_rate": 24000}


@app.post("/api/tts")
def speech_start(params: SpeechRequest):
    try:
        return {"id": tts_engine.submit(params.model_dump())}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/tts/jobs/{job_id}")
def speech_status(job_id: str):
    if job_id not in tts_engine.jobs:
        raise HTTPException(404, "Speech generation not found.")
    return tts_engine.jobs[job_id]


@app.post("/api/tts/jobs/{job_id}/cancel")
def speech_cancel(job_id: str):
    if job_id not in tts_engine.events:
        raise HTTPException(404)
    if tts_engine.jobs[job_id]["status"] in {"done", "error", "cancelled"}:
        return {"status": tts_engine.jobs[job_id]["status"]}
    tts_engine.jobs[job_id]["cancel_requested"] = True
    tts_engine.events[job_id].set()
    return {"status": "stopping"}


@app.get("/api/tts/audio/{job_id}/{filename}")
def speech_audio(job_id: str, filename: str):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id) or not re.fullmatch(r"speech\.wav|chunk-[0-9]{5}\.wav", filename):
        raise HTTPException(404)
    path = OUTPUTS / job_id / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, filename=filename, media_type="audio/wav")


@app.get("/")
def index():
    return FileResponse(ROOT / "static/index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
