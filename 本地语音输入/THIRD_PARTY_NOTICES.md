# 第三方来源与许可证

本应用自主接入代码采用 MIT 许可证。未复制 Handy 源码，仅参考其“识别后再用本地模型清理”的流程。

| 组件 | 来源 | 许可证／注意事项 |
| --- | --- | --- |
| sherpa-onnx 1.13.8 | https://github.com/k2-fsa/sherpa-onnx | Apache-2.0 |
| Zipformer zh 14M streaming | https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23 | 模型卡标注 Apache-2.0 |
| Paraformer zh offline | https://huggingface.co/csukuangfj/sherpa-onnx-paraformer-zh-2023-09-14 | 模型卡标注 Apache-2.0 |
| CT-Transformer punctuation | https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models | 以原模型许可为准 |
| Silero VAD | https://github.com/snakers4/silero-vad | MIT，许可附于 models/vad/LICENSE |
| llama.cpp b11312 | https://github.com/ggml-org/llama.cpp | MIT，附于 runtime/llama/LICENSE-llama.cpp；OpenMP 许可同目录 |
| Qwen3.5-0.8B | https://huggingface.co/Qwen/Qwen3.5-0.8B | Apache-2.0，许可附于 models/cleanup/LICENSE-Qwen |
| PySide6 / Qt | https://www.qt.io/licensing | LGPLv3/GPLv3/commercial；本包使用动态 DLL，不宣称 Qt 采用 MIT |
| NumPy | https://numpy.org | BSD-3-Clause，及其二进制依赖许可 |
| sounddevice / PortAudio | https://python-sounddevice.readthedocs.io | MIT，PortAudio 许可随依赖分发 |
| pynput | https://github.com/moses-palmer/pynput | LGPLv3 |
| pyperclip | https://github.com/asweigart/pyperclip | BSD-3-Clause |
| Python | https://www.python.org | PSF License |
| PyInstaller | https://pyinstaller.org | GPL with bootloader exception；构建工具，不限制应用必须采用 GPL |

模型来源、整理引擎版本与校验值在 `cleanup_sources.json`。依赖安装包自带的完整许可证位于 `licenses`。本次封装供个人本地使用，不代表已完成公开或商业发行审查。
