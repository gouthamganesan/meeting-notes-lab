const $ = (id) => document.getElementById(id);
const tabs = ["mic", "file", "speech", "learn"];
function activate(name) {
  $("view-label").textContent = {
    mic: "Your notebook",
    file: "Import recording",
    learn: "Explore VibeVoice",
    speech: "Create speech",
  }[name];
  for (const t of tabs) {
    const active = t === name;
    $(`tab-${t}`).classList.toggle("active", active);
    $(`tab-${t}`).setAttribute("aria-selected", active);
    $(`tab-${t}`).tabIndex = active ? 0 : -1;
    $(`${t}-panel`).hidden = !active;
  }
}
for (const name of tabs) {
  $(`tab-${name}`).onclick = () => activate(name);
  $(`tab-${name}`).onkeydown = (e) => {
    if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
      e.preventDefault();
      const next =
        e.key === "Home"
          ? 0
          : e.key === "End"
            ? tabs.length - 1
            : (tabs.indexOf(name) +
                (e.key === "ArrowRight" ? 1 : -1) +
                tabs.length) %
              tabs.length;
      activate(tabs[next]);
      $(`tab-${tabs[next]}`).focus();
    }
  };
}
document.querySelectorAll("[data-open]").forEach(
  (button) =>
    (button.onclick = () => {
      activate(button.dataset.open);
      $("workspace").focus();
    }),
);
function status(where, text, error = false) {
  $(`${where}-status`).textContent = text;
  $(`${where}-status`).classList.toggle("error", error);
}
function output(where, text) {
  $(`${where}-empty`).hidden = Boolean(text);
  $(`${where}-output`).hidden = !text;
  $(`${where}-output`).textContent =
    text ||
    (where === "live" ? "Your words will appear here." : "No speech detected.");
  $(`${where}-output`).classList.toggle("empty", !text);
  $(`copy-${where}`).disabled = !text;
}
for (const name of ["live", "file"])
  $(`copy-${name}`).onclick = async () => {
    try {
      await navigator.clipboard.writeText($(`${name}-output`).textContent);
      const button = $(`copy-${name}`);
      button.textContent = "Copied";
      setTimeout(() => (button.textContent = "Copy text"), 1500);
    } catch {
      status(name, "Select the transcript and copy it with Command+C.", true);
    }
  };
async function json(response) {
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "The request failed. Check the input and try again.",
    );
  return body;
}
function downloads(where, links) {
  const box = $(`${where}-downloads`);
  box.replaceChildren();
  for (const [type, url] of Object.entries(links || {})) {
    const a = document.createElement("a");
    a.href = url;
    a.download =
      (where === "live"
        ? $("session-title").value.trim() || "conversation"
        : "transcript") +
      "." +
      type;
    a.textContent =
      {
        srt: "Download SRT",
        txt: "Download transcript",
        json: "Download JSON",
      }[type] || type;
    a.className = type === "srt" ? "" : "secondary";
    box.append(a);
  }
  box.hidden = !box.children.length;
}
let selectedFile = null,
  fileBusy = false;
function selectFile(file) {
  if (!file || fileBusy) return;
  selectedFile = file;
  $("filename").textContent = file.name;
  $("file-info").hidden = false;
  status("file", "Ready to transcribe.");
  downloads("file", {});
  runFile();
}
$("file").onchange = (e) => selectFile(e.target.files[0]);
$("dropzone").onkeydown = (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    $("file").click();
  }
};
for (const event of ["dragenter", "dragover"])
  $("dropzone").addEventListener(event, (e) => {
    e.preventDefault();
    $("dropzone").classList.add("dragging");
  });
for (const event of ["dragleave", "drop"])
  $("dropzone").addEventListener(event, (e) => {
    e.preventDefault();
    $("dropzone").classList.remove("dragging");
    if (event === "drop") selectFile(e.dataTransfer.files[0]);
  });
async function followJob(id, where) {
  while (true) {
    const job = await json(await fetch(`/api/jobs/${id}`));
    status(where, job.message, job.status === "error");
    if (job.text) output(where, job.text);
    if (where === "file") {
      $("file-progress").value = job.progress;
    }
    if (job.status === "error") throw new Error(job.message);
    if (job.status === "done") {
      output(where, job.text);
      downloads(where, job.downloads);
      return job;
    }
    await new Promise((r) => setTimeout(r, 700));
  }
}
async function sendFile(blob, name, where) {
  const form = new FormData();
  form.append("file", blob, name);
  form.append("hotwords", $(`${where}-hotwords`).value);
  status(where, "Uploading to the local app…");
  const job = await json(
    await fetch("/api/files", { method: "POST", body: form }),
  );
  return followJob(job.id, where);
}
async function runFile() {
  if (!selectedFile || fileBusy) return;
  fileBusy = true;
  $("file").disabled = true;
  $("dropzone").setAttribute("aria-disabled", "true");
  $("file-progress").hidden = false;
  $("file-progress").value = 0;
  downloads("file", {});
  output("file", "");
  try {
    await sendFile(selectedFile, selectedFile.name, "file");
  } catch (e) {
    status("file", e.message, true);
  } finally {
    fileBusy = false;
    $("file").disabled = false;
    $("dropzone").removeAttribute("aria-disabled");
  }
}

let recording = false,
  stopping = false,
  context,
  media,
  node,
  source,
  mute,
  analyser,
  meterFrame;
let all = [],
  pending = [],
  pendingSamples = 0,
  sampleRate = 48000,
  started = 0,
  clock,
  liveChain = Promise.resolve(),
  liveTexts = [],
  liveError = false,
  streaming = true,
  flushResolve;
function wav(chunks, rate) {
  const length = chunks.reduce((n, c) => n + c.length, 0);
  const buffer = new ArrayBuffer(44 + length * 2),
    v = new DataView(buffer);
  let pos = 0;
  const str = (s) => {
    for (const c of s) v.setUint8(pos++, c.charCodeAt(0));
  };
  str("RIFF");
  v.setUint32(4, 36 + length * 2, true);
  pos = 8;
  str("WAVEfmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, rate, true);
  v.setUint32(28, rate * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  pos = 36;
  str("data");
  v.setUint32(40, length * 2, true);
  pos = 44;
  for (const chunk of chunks)
    for (const value of chunk) {
      v.setInt16(
        pos,
        Math.max(-1, Math.min(1, value)) * (value < 0 ? 32768 : 32767),
        true,
      );
      pos += 2;
    }
  return new Blob([buffer], { type: "audio/wav" });
}
function queueLive() {
  if (!pending.length) return;
  const chunks = pending;
  pending = [];
  pendingSamples = 0;
  const blob = wav(chunks, sampleRate);
  liveChain = liveChain
    .then(async () => {
      status(
        "live",
        recording ? "Listening and transcribing…" : "Finishing the transcript…",
      );
      const form = new FormData();
      form.append("file", blob, "chunk.wav");
      form.append("hotwords", $("live-hotwords").value);
      const result = await json(
        await fetch("/api/live", { method: "POST", body: form }),
      );
      if (result.text) {
        liveTexts.push(result.text);
        output("live", liveTexts.join(" "));
      }
    })
    .catch((e) => {
      liveError = true;
      status("live", e.message, true);
    });
}
async function releaseMic() {
  cancelAnimationFrame(meterFrame);
  analyser?.disconnect();
  media?.getTracks().forEach((track) => track.stop());
  source?.disconnect();
  node?.disconnect();
  mute?.disconnect();
  if (context && context.state !== "closed") await context.close();
  clearInterval(clock);
}
async function start() {
  if (recording || stopping) return;
  $("mic").disabled = true;
  $("try-sample").disabled = true;
  try {
    media = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    context = new AudioContext();
    await context.resume();
    await context.audioWorklet.addModule("/static/recorder.js");
    sampleRate = context.sampleRate;
    node = new AudioWorkletNode(context, "recorder");
    source = context.createMediaStreamSource(media);
    mute = context.createGain();
    mute.gain.value = 0;
    source.connect(node);
    node.connect(mute);
    mute.connect(context.destination);
    analyser = context.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    all = [];
    pending = [];
    pendingSamples = 0;
    liveTexts = [];
    liveChain = Promise.resolve();
    liveError = false;
    streaming = $("stream").checked;
    recording = true;
    $("capture-kind").textContent = "Microphone recording";
    started = Date.now();
    drawMeter();
    $("timer").textContent = "00:00";
    $("live-hotwords").disabled = true;
    node.port.onmessage = (e) => {
      if (e.data === "flushed") {
        flushResolve?.();
        return;
      }
      const samples = e.data;
      all.push(samples);
      if (streaming) {
        pending.push(samples);
        pendingSamples += samples.length;
        if (pendingSamples >= sampleRate * 6) queueLive();
      }
    };
    $("stream").disabled = true;
    $("mic").classList.add("recording");
    $("mic").setAttribute("aria-label", "Stop recording");
    $("mic-label").textContent = "Listening…";
    output("live", "");
    downloads("live", {});
    status(
      "live",
      streaming
        ? "Listening. Text will appear shortly…"
        : "Recording. Your transcript will appear after you stop.",
    );
    clock = setInterval(() => {
      const seconds = Math.floor((Date.now() - started) / 1000);
      $("timer").textContent =
        `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
      if (seconds >= 1800) stop();
    }, 500);
  } catch (e) {
    await releaseMic();
    status(
      "live",
      e.name === "NotAllowedError"
        ? "Microphone access was denied. Allow it in your browser, then tap the mic again."
        : e.message,
      true,
    );
  } finally {
    $("mic").disabled = false;
    if (!recording) $("try-sample").disabled = false;
  }
}
async function stop() {
  if (!recording || stopping) return;
  stopping = true;
  recording = false;
  $("mic").disabled = true;
  try {
    source.disconnect();
    await new Promise((resolve) => {
      flushResolve = resolve;
      node.port.postMessage("flush");
      setTimeout(resolve, 1000);
    });
    await releaseMic();
    $("mic").classList.remove("recording");
    $("mic-label").textContent = "Finishing…";
    if (streaming) {
      queueLive();
      await liveChain;
    }
    const recordingBlob = wav(all, sampleRate);
    if (recordingBlob.size <= 44)
      throw new Error("No audio was recorded. Try again.");
    // Final pass uses the whole recording to repair words cut at live chunk boundaries.
    status("live", "Finalising transcript and subtitle timings…");
    await sendFile(recordingBlob, "recording.wav", "live");
  } catch (e) {
    status("live", e.message, true);
  } finally {
    await releaseMic();
    stopping = false;
    $("mic").disabled = false;
    $("stream").disabled = false;
    $("mic").setAttribute("aria-label", "Start recording");
    $("mic-label").textContent = "Start a conversation";
    $("try-sample").disabled = false;
    $("live-hotwords").disabled = false;
    all = [];
    pending = [];
  }
}
$("mic").onclick = () => (recording ? stop() : start());
$("stream").onchange = () => {
  $("mic-hint").textContent = $("stream").checked
    ? "Tap the mic. Tap again when you’re done."
    : "Text appears after you stop.";
};
window.addEventListener("beforeunload", () =>
  media?.getTracks().forEach((track) => track.stop()),
);

function drawMeter() {
  if (!recording || !analyser) return;
  const canvas = $("level-meter"),
    ctx = canvas.getContext("2d"),
    values = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteTimeDomainData(values);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#a23b58";
  for (let i = 0; i < 12; i++) {
    let peak = 0;
    for (let j = i * 10; j < (i + 1) * 10; j++)
      peak = Math.max(peak, Math.abs((values[j] ?? 128) - 128) / 128);
    const height = Math.max(2, peak * 38);
    ctx.fillRect(i * 10 + 2, (40 - height) / 2, 4, height);
  }
  meterFrame = requestAnimationFrame(drawMeter);
}
$("try-sample").onclick = async () => {
  if (recording || stopping) return;
  $("try-sample").disabled = true;
  $("mic").disabled = true;
  $("stream").disabled = true;
  $("live-hotwords").disabled = true;
  $("session-title").value = "Prototype planning";
  $("capture-kind").textContent = "Synthetic sample · Transcribed locally";
  output("live", "");
  downloads("live", {});
  try {
    status(
      "live",
      "Loading a synthetic sample. This uses the real local transcription model…",
    );
    const response = await fetch("/static/sample.wav");
    if (!response.ok)
      throw new Error("The sample could not be loaded. Try recording instead.");
    const blob = await response.blob();
    await sendFile(blob, "sample.wav", "live");
    status(
      "live",
      "Sample transcribed locally. Your own recording works the same way.",
    );
  } catch (e) {
    status("live", e.message, true);
  } finally {
    $("try-sample").disabled = false;
    $("mic").disabled = false;
    $("stream").disabled = false;
    $("live-hotwords").disabled = false;
  }
};


let speechBusy = false, speechJob = null, speechVoices = [], speechCancelPending = false;
function speechControls() {
  $("speech-generate").disabled = speechBusy || !speechVoices.length || $("speech-text").value.trim().length < 10;
  $("speech-text").disabled = speechBusy;
  $("speech-voice").disabled = speechBusy || !speechVoices.length;
  $("speech-cancel").hidden = !speechBusy;
  $("speech-cancel").disabled = !speechJob || speechCancelPending;
  $("speech-result").setAttribute("aria-busy", String(speechBusy));
  $("speech-progress").hidden = !speechBusy;
}
async function loadSpeechVoices() {
  $("speech-retry").hidden = true;
  try {
    const result = await json(await fetch("/api/tts/voices"));
    speechVoices = result.voices;
    $("speech-voice").replaceChildren();
    for (const [label, experimental] of [["English presets", false], ["Experimental presets", true]]) {
      const group = document.createElement("optgroup");
      group.label = label;
      for (const voice of speechVoices.filter(v => Boolean(v.experimental) === experimental)) {
        const option = document.createElement("option");
        option.value = voice.id;
        option.textContent = `${voice.name} · ${voice.language}${voice.experimental ? " · experimental" : ""}`;
        group.append(option);
      }
      if (group.children.length) $("speech-voice").append(group);
    }
    if (speechVoices.some(v => v.id === "base:en-Carter_man")) $("speech-voice").value = "base:en-Carter_man";
    if (!speechVoices.length) throw new Error("No installed voice presets were found. Speech generation needs the optional runtime and presets described in docs/speech-experiment.md. Set those up, then retry.");
    status("speech", "Your audio will appear here after generation.");
  } catch (e) {
    speechVoices = [];
    status("speech", `Could not load installed voices. ${e.message}`, true);
    $("speech-retry").hidden = false;
  }
  speechControls();
}
$("speech-retry").onclick = loadSpeechVoices;
$("speech-text").oninput = () => {
  $("speech-count").textContent = `${$("speech-text").value.length.toLocaleString()} / 10,000`;
  speechControls();
};
$("speech-form").onsubmit = async (event) => {
  event.preventDefault();
  if (speechBusy || !speechVoices.length) return;
  const text = $("speech-text").value.trim();
  if (text.length < 10) { status("speech", "Write a full sentence of at least 10 characters.", true); return; }
  speechBusy = true;
  speechJob = null;
  speechCancelPending = false;
  $("speech-audio").pause();
  $("speech-audio").removeAttribute("src");
  $("speech-audio").load();
  $("speech-player").hidden = true;
  $("speech-duration").textContent = "";
  speechControls();
  status("speech", "Starting local speech generation…");
  try {
    const submitted = await json(await fetch("/api/tts", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({text, voice: $("speech-voice").value})}));
    speechJob = submitted.id;
    speechControls();
    while (true) {
      if (!speechJob) break;
      const job = await json(await fetch(`/api/tts/jobs/${submitted.id}`));
      if (speechJob !== submitted.id) break;
      status("speech", speechCancelPending ? "Stopping generation. Waiting for the model to finish its current step…" : job.message, job.status === "error");
      $("speech-duration").textContent = job.audio_seconds > 0 ? `${job.audio_seconds.toFixed(1)} seconds generated` : "";
      if (["done", "cancelled", "error"].includes(job.status)) {
        status("speech", job.message, job.status === "error");
        if (job.audio_url) {
          $("speech-audio").src = job.audio_url;
          $("speech-download").href = job.audio_url;
          $("speech-download").textContent = job.status === "cancelled" ? "Download partial WAV" : "Download WAV";
          $("speech-player").hidden = false;
        }
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 700));
    }
  } catch (e) {
    status("speech", speechJob ? `Could not check generation. ${e.message} The local job may still be running; use Stop generation to request a stop.` : e.message, true);
    if (speechJob) {
      // Keep cancellation available when polling fails, rather than orphaning the job.
      $("speech-result").setAttribute("aria-busy", "false");
      $("speech-progress").hidden = true;
      return;
    }
  } finally {
    if (!$("speech-status").textContent.startsWith("Could not check generation.")) {
      speechBusy = false;
      speechJob = null;
      speechControls();
    }
  }
};
$("speech-cancel").onclick = async () => {
  if (!speechJob || speechCancelPending) return;
  speechCancelPending = true;
  speechControls();
  status("speech", "Stopping generation. Waiting for the model to finish its current step…");
  try {
    await json(await fetch(`/api/tts/jobs/${speechJob}/cancel`, {method: "POST"}));
    // Also recover a job whose normal polling loop was interrupted by a network error.
    while (speechJob) {
      const job = await json(await fetch(`/api/tts/jobs/${speechJob}`));
      if (["done", "cancelled", "error"].includes(job.status)) {
        status("speech", job.message, job.status === "error");
        if (job.audio_url) {
          $("speech-audio").src = job.audio_url;
          $("speech-download").href = job.audio_url;
          $("speech-download").textContent = job.status === "cancelled" ? "Download partial WAV" : "Download WAV";
          $("speech-player").hidden = false;
        }
        speechBusy = false;
        speechJob = null;
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 700));
    }
  } catch (e) {
    status("speech", `Could not confirm the stop. ${e.message} Retry Stop generation.`, true);
  } finally {
    speechCancelPending = false;
    speechControls();
  }
};
loadSpeechVoices();
