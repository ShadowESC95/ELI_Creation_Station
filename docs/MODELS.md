# Models

## The rule

**One main model stays loaded; every specialist loads when a job needs it and unloads when idle.**

| | Main model | Specialist models |
|---|---|---|
| What | The language model: writing, planning, code, ELI's voice | Images, video, music, speech, captions, 3D, upscaling, background removal, reading the screen |
| Where it runs | In process (a GGUF through llama.cpp, sized to the memory free), a model server, or ELI v3's own | A worker process of its own (`runtimes/`), in an environment built for its engine (`runtime/workers/<name>`) |
| When | Loaded at start, kept loaded | Loaded for a job; unloaded after `idle_unload_seconds` (Settings; 0 = at once) |
| Unloaded | At shut-down only, or for one job if you allowed it to step aside | By ending its worker, which returns every byte to every vendor's driver |

How the planner finds room for a specialist (`models/manager.py`), in order: beside what is loaded on
a card it can use; on another card; by unloading the longest-idle specialists; on the processor, if
the model may run there; by letting the main model step aside for this one job, only if allowed.
Otherwise the job is refused with the reason and nothing is unloaded. How many specialists may be
loaded at once follows the tier (1 on T0-T2, 2 on T3, 3 on T4) unless set.

## The models folder

One folder per kind, each model in `models/<kind>/<model id>/` with `LICENSE.<model id>.txt` beside
its files. Folders shared in kind with ELI v3 are read from ELI v3 too (never written), so a model
ELI v3 already has is not fetched twice.

| Folder | Holds | Read from ELI v3 |
|---|---|---|
| `llm/` | Main language models (GGUF) | `gguf/base` |
| `code/` | Coding models (GGUF) | |
| `embeddings/` | Text and image embedders: searching the library | `embeddings` |
| `vision/` | Vision-language models and projectors: reading the screen, describing images | `vision` |
| `image/` | Text-to-image and image-to-image | |
| `image-adapters/` | LoRA, ControlNet, IP-Adapter | |
| `upscale/` | Upscalers | |
| `segmentation/` | Background removal, masks | |
| `depth/` | Depth estimation | |
| `video/` | Text-to-video, image-to-video | |
| `interpolation/` | Frame interpolation | |
| `speech/` | Text-to-speech voices | `tts` |
| `transcription/` | Speech-to-text: captions | `whisper` |
| `music/` | Music and sound effects | |
| `3d/` | Image-to-3D, meshes | |
| `ocr/` | Text recognition data | |
| `voices/` | Voice clones made with consent: never published | |
| `lora/` | Styles trained on your own work: never published | |

`eli-creation models folders` makes them, each with a README.

## The licence gate

Creation Station downloads only models whose licence is permissive (Apache-2.0, MIT, BSD...), whose
licence is recorded, and whose revision is pinned (`models/licences.py`). The catalogue
(`models/catalogue.json`) lists candidates by task, best first; `verified` is true only where ELI
already records the licence. Known traps, never fetched:

| Model | Licence | Why |
|---|---|---|
| FLUX.1 [dev] | FLUX.1 [dev] Non-Commercial | Outputs may not be used commercially |
| MusicGen weights | CC-BY-NC-4.0 | Non-commercial |
| Stable Diffusion 3.5, Stable Audio Open | Stability AI Community License | A revenue threshold ELI cannot accept for every buyer |
| SDXL-Turbo, SD-Turbo | Stability non-commercial research | Non-commercial |
| Tencent Hunyuan models | Tencent Hunyuan Community License | Excludes the EU, the UK and South Korea |
| Qwen2.5-3B | Qwen Research License | Research only |
| XTTS-v2 | Coqui Public Model License | Non-commercial; removed from ELI v3 for this reason |

A model you bring yourself is used under its own licence, which you accept. Every asset it makes
carries that licence's class in its manifest, and an export warns before a non-commercial output is
used commercially.
