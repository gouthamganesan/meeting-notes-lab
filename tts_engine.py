"""Offline streaming speech generation using Microsoft's supplied inference service."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import importlib.util
import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import soundfile as sf

LANGUAGES = {"en": "English", "in": "English · Indian accent", "de": "German", "fr": "French",
             "it": "Italian", "jp": "Japanese", "kr": "Korean", "nl": "Dutch",
             "pl": "Polish", "pt": "Portuguese", "sp": "Spanish"}
jobs = {}
events = {}
executor = ThreadPoolExecutor(max_workers=1)
_service = None


def voices():
    entries = {}
    for group, folder in [("base", ROOT / "vendor/VibeVoice/demo/voices/streaming_model"),
                          ("extra", ROOT / "models/experimental-voices")]:
        for path in sorted(folder.rglob("*.pt")):
            key = group + ":" + path.stem
            prefix = path.stem.split("-", 1)[0].lower()
            name = path.stem.split("-", 1)[-1].replace("_", " ")
            entries[key] = {"id": key, "name": name, "language": LANGUAGES.get(prefix, "English"),
                            "experimental": group == "extra" or prefix not in ("en", "in"),
                            "path": path}
    return entries


def catalog():
    return [{k: v for k, v in entry.items() if k != "path"} for entry in voices().values()]


def service():
    global _service
    if _service is None:
        import torch
        path = ROOT / "vendor/VibeVoice/demo/web/app.py"
        spec = importlib.util.spec_from_file_location("upstream_vibevoice_tts", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        class LocalPresetService(module.StreamingTTSService):
            def _ensure_voice_cached(self, key):
                if key not in self._voice_cache:
                    # Only bundled Microsoft presets are accepted; no user-supplied pickle files.
                    preset = self.voice_presets[key].resolve()
                    allowed = [ROOT / "vendor/VibeVoice/demo/voices/streaming_model", ROOT / "models/experimental-voices"]
                    if not any(preset.is_relative_to(folder.resolve()) for folder in allowed):
                        raise ValueError("Voice preset is outside the installed catalog.")
                    self._voice_cache[key] = torch.load(preset, map_location=self._torch_device, weights_only=False)
                return self._voice_cache[key]
        loaded = LocalPresetService(str(ROOT / "models/realtime"), device=device)
        loaded.load()
        loaded.voice_presets = {key: value["path"] for key, value in voices().items()}
        loaded.default_voice_key = "base:en-Carter_man"
        _service = loaded
    return _service


def generate(job_id, params):
    job, stop = jobs[job_id], events[job_id]
    folder = ROOT / "outputs" / job_id
    start = time.perf_counter()
    try:
        if stop.is_set():
            job.update(status="cancelled", message="Generation cancelled.")
            return
        job.update(status="loading", message="Loading the speech model. The first run takes longer…")
        model = service()
        if stop.is_set():
            job.update(status="cancelled", message="Generation cancelled.")
            return
        import torch
        torch.manual_seed(params["seed"])
        job.update(status="generating", message="Generating speech…", device=model.device)
        generated_at = time.perf_counter()
        chunks, total = [], 0
        for index, chunk in enumerate(model.stream(
            params["text"], voice_key=params["voice"], cfg_scale=params["guidance"],
            inference_steps=params["steps"], stop_event=stop,
        )):
            if not np.isfinite(chunk).all():
                raise RuntimeError("The model produced invalid audio. Try a different voice or text.")
            if not len(chunk):
                continue
            if not chunks:
                job["first_audio_seconds"] = round(time.perf_counter() - start, 2)
            chunks.append(chunk)
            total += len(chunk)
            filename = f"chunk-{index:05d}.wav"
            sf.write(folder / filename, chunk, 24000, subtype="PCM_16")
            job["chunks"].append(f"/api/tts/audio/{job_id}/{filename}")
            job.update(audio_seconds=round(total/24000, 2), message=f"Generated {total/24000:.1f} seconds of speech…")
        if not chunks:
            job.update(status="cancelled" if job.get("cancel_requested") else "error",
                       message="Generation cancelled." if job.get("cancel_requested") else "No audio was generated. Try a longer sentence.")
            return
        sf.write(folder / "speech.wav", np.concatenate(chunks), 24000, subtype="PCM_16")
        elapsed = time.perf_counter()-generated_at
        metrics = {"device": model.device, "total_seconds": round(time.perf_counter()-start,2),
                   "generation_seconds": round(elapsed,2), "audio_seconds": round(total/24000,2),
                   "first_audio_seconds": job["first_audio_seconds"], "realtime_factor": round(elapsed/(total/24000),2)}
        (folder / "metrics.json").write_text(json.dumps(metrics, indent=2))
        job.update(status="cancelled" if job.get("cancel_requested") else "done", metrics=metrics,
            message="Stopped. The generated portion is ready to download." if job.get("cancel_requested") else "Your audio is ready.",
            audio_url=f"/api/tts/audio/{job_id}/speech.wav")
    except Exception as exc:
        (folder / "error.log").write_text(traceback.format_exc())
        job.update(status="error", message=f"Speech generation failed: {exc}")


def submit(params):
    if params["voice"] not in voices():
        raise ValueError("Choose an installed voice.")
    if len(params["text"].strip()) < 10:
        raise ValueError("Use a full sentence; this model is unstable on very short text.")
    if any(job["status"] in {"queued", "loading", "generating"} for job in jobs.values()):
        raise ValueError("A speech generation is already running. Stop it or wait for it to finish.")
    job_id = uuid.uuid4().hex
    folder = ROOT / "outputs" / job_id
    folder.mkdir()
    (folder / "input.txt").write_text(params["text"])
    (folder / "settings.json").write_text(json.dumps(params, indent=2))
    jobs[job_id] = {"id": job_id, "status": "queued", "message": "Waiting to generate…", "chunks": [], "audio_seconds": 0}
    events[job_id] = threading.Event()
    executor.submit(generate, job_id, params)
    return job_id
