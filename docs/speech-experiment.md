# Optional speech-generation experiment

The main interface uses compact ASR. The Create speech tab uses the optional local speech runtime for text input, voice selection, generation, cancellation, playback and WAV download.

The tested setup used Microsoft VibeVoice at commit `16fb2cb1217c9934a886e1948ffb06120caa2df5`, PyTorch 2.15.0, Transformers 4.51.3, float32 and SDPA on Apple Metal. The Realtime-0.5B weights were about 2.04 GB. The full environment is in `requirements.lock.txt`.

To reproduce this optional setup, clone the pinned upstream source into `vendor/VibeVoice` and install its `streamingtts` extra into `.venv`. Follow the [official Realtime instructions](https://github.com/microsoft/VibeVoice/blob/main/docs/vibevoice-realtime-0.5b.md) to obtain the weights, placing the model files under `models/realtime`. The tested model revision was `6bce5f06044837fe6d2c5d7a71a84f0416bd57e4`.

Download only the tokenizer files from `Qwen/Qwen2.5-0.5B` into `models/Qwen2.5-0.5B-tokenizer`, and set `language_model_pretrained_name` in the model's `preprocessor_config.json` to that folder's absolute path. The Qwen language-model weights are not needed. The upstream base voice presets are read from `vendor/VibeVoice/demo/voices/streaming_model`.

The installed official preset files contain serialized Transformers objects. `tts_engine.py` restricts loading to the installed catalog directories and does not accept uploaded preset files. Only use trusted upstream presets. Extra experimental presets are optional and are read from `models/experimental-voices`.

With this runtime installed:

```sh
.venv/bin/python scripts/speech_test.py
```

The test generates synthetic speech, checks streamed chunks and the final WAV, transcribes the clip, downloads TXT/SRT/JSON and checks cancellation. It does not use the physical microphone. Timings are measurements of this Mac and sample, not a general speed guarantee.

The API endpoints are `/api/tts/voices`, `/api/tts`, `/api/tts/jobs/{id}`, `/api/tts/jobs/{id}/cancel` and `/api/tts/audio/{id}/{filename}`. The Create speech tab uses these endpoints. Audio playback begins after generation; streamed chunks are available through the API.
