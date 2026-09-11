# WSL Runtime Bootstrap

> **适用范围**：本文档说明如何从零重建 `wsl_runtime` 的虚拟环境与 ASR 模型。
> 仓库只收录 `video_inbox_v2` 源码（80 KB）与 `.gitignore`；
> `.venv`（451 MB）、`models`（464 MB）、`cache` 均为本地产物，**不入库**。
> 换机器或删掉运行时后，按下文重建即可恢复可用状态。

## 为什么需要这份文档

`wsl_runtime` 合计约 940 MB，其中 **99.99% 是可重建的产物**：

| 路径 | 体积 | 是否入库 | 重建方式 |
|---|---|---|---|
| `video_inbox_v2/` | 80 KB | ✅ 已入库 | — |
| `.venv/` | 451 MB | ❌ | `uv venv` + `uv pip install`（见下） |
| `models/` | 464 MB | ❌ | 首次 ASR 时由 faster-whisper 自动下载 |
| `cache/` | 25 MB | ❌ | 运行时产物，无需重建 |
| `temp/` | 空 | ❌ | 运行时自动创建 |

## 前置条件

| 依赖 | 版本要求 | 检查命令 |
|---|---|---|
| Python | **3.12**（实测 3.12.3） | `python3 --version` |
| uv | 用于建 venv（实测 0.12.5） | `uv --version` |
| ffmpeg | 系统包即可（实测 6.1.1） | `ffmpeg -version` |
| 磁盘 | ≥ 1 GB 可用（venv 451M + 模型 464M） | `df -h ~` |

> `uv` 不在 PATH 时：`curl -LsSf https://astral.sh/uv/install.sh | sh`（装到 `~/.local/bin`）。
> `ffmpeg` 缺失时：`sudo apt install ffmpeg`。

**关于 ffmpeg**：`yt_dlp` 以 `format: bestaudio/best` 直接取原始容器（`.m4a`），
再由 `faster-whisper` 经 **PyAV** 解码，因此**不依赖 ffmpeg 做音频转码**。
`static-ffmpeg` 包虽在依赖树中，但源码未 import 它（仅为传递依赖）。系统 ffmpeg 保留作兜底即可。

## 重建步骤

```bash
cd ~/.dsh/skills/video-inbox/wsl_runtime

# 1. 建 venv（Python 3.12）
uv venv --python 3.12 .venv

# 2. 装依赖 —— 只有 3 个顶层包，其余 48 个由它们带入
uv pip install --python .venv/bin/python \
  'faster-whisper==1.2.1' \
  'yt-dlp==2026.8.19' \
  'static-ffmpeg==3.0'

# 3. 建运行目录
mkdir -p models cache temp

# 4. 健康检查（此时 asr_model_cached 应为 false）
.venv/bin/python -m video_inbox_v2 doctor
```

实测耗时：建 venv < 1s，装依赖约 **26 秒**。

## 依赖清单

### 顶层（必须显式声明）

| 包 | 版本 | 用途 |
|---|---|---|
| `faster-whisper` | 1.2.1 | 音频 ASR（CPU / int8） |
| `yt-dlp` | 2026.8.19 | 元数据、字幕、音频抓取 |
| `static-ffmpeg` | 3.0 | 兜底 ffmpeg 供给（当前代码未直接调用） |

### 传递依赖（48 个，自动带入，**不要手工钉**）

- `faster-whisper` → `ctranslate2` `huggingface-hub` `tokenizers` `onnxruntime` `av` `tqdm` `numpy` `protobuf` …
- `yt-dlp` → `certifi` `typing-extensions` …
- `static-ffmpeg` → `requests` `filelock` `progress` `twine` `keyring` `rich` `pyyaml` …

> 传递依赖**不钉版本**：上游补丁版本会自然前移（实测重建得到
> `anyio 4.15.1` / `ctranslate2 4.8.2` / `numpy 2.5.3`，而原 venv 是 4.14.2 / 4.8.1 / 2.5.2）。
> 只要 3 个顶层包版本一致，运行时行为即等价。

## ASR 模型

**不需要手工下载**——首次调用 ASR 时由 faster-whisper 自动拉到 `models/`。

模型定义在 `video_inbox_v2/asr.py`：

```python
WhisperModel(name, device="cpu", compute_type="int8", download_root=str(MODELS_DIR))
```

- 默认模型：`small`（`config.py` 的 `DEFAULT_ASR_MODEL`）
- 可选：`tiny` / `base` / `small` / `medium`（`acquire --asr-model` / `transcribe --asr-model`）
- 落盘位置：`wsl_runtime/models/models--Systran--faster-whisper-small/`（约 **464 MB**）
- 来源：Hugging Face，需要能访问 `huggingface.co`

### 想预下载模型（可选）

不必等到第一次跑任务，提前触发一次即可：

```bash
cd ~/.dsh/skills/video-inbox/wsl_runtime
.venv/bin/python -c "
from faster_whisper import WhisperModel
WhisperModel('small', device='cpu', compute_type='int8',
             download_root='models')
print('ok')
"
```

### ⚠️ 已知坑：`NO_PROXY` 含 `[::1]` 会让下载失败

若本机设了代理且 `NO_PROXY`/`no_proxy` 里带 `[::1]` 这种**带方括号的 IPv6 字面量**，
httpx 会解析失败并抛：

```
httpx.InvalidURL: Invalid port: ':1]'
```

**这不是 skill 的 bug，是环境变量格式问题。** 下载模型时临时清掉该段即可：

```bash
NO_PROXY="127.0.0.1,localhost" no_proxy="127.0.0.1,localhost" \
  .venv/bin/python -c "from faster_whisper import WhisperModel; \
  WhisperModel('small', device='cpu', compute_type='int8', download_root='models')"
```

或从 `~/.bashrc` / `~/.profile` 的 `NO_PROXY` 中永久移除 `[::1]`（`::1` 不带方括号是安全的）。

## 验证

```bash
cd ~/.dsh/skills/video-inbox/wsl_runtime
.venv/bin/python -m video_inbox_v2 doctor
```

期望输出（模型已就绪时）：

```json
{"ok": true, "checks": {
  "python": "3.12.3",
  "yt_dlp": "2026.08.19",
  "faster_whisper": "1.2.1",
  "asr_model_cached": true,
  "vault_exists": true,
  "inbox_exists": true,
  "douyin_route": "browser-only(Plan B); cookie reuse disabled by policy",
  "net_bilibili": 412,
  "net_youtube": 200
}}
```

判读要点：

| 字段 | 说明 |
|---|---|
| `ok` | 全部关键项通过才为 `true` |
| `asr_model_cached` | 模型未下载时为 `false`，首次 ASR 会自动补齐 |
| `vault_exists` / `inbox_exists` | 指向 `/mnt/d/Open-brain-obsidian`；为 `false` 时先确认 vault 已挂载 |
| `net_bilibili` | **412 属正常**（B 站反爬），不影响 yt-dlp 走 API 取流 |

## 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| `httpx.InvalidURL: Invalid port: ':1]'` | `NO_PROXY` 含 `[::1]` | 见上文，临时清空该段 |
| `asr_model_cached: false` 且下载卡住 | HF 不可达 | 检查代理 / 网络；必要时设 `HF_ENDPOINT=https://hf-mirror.com` |
| `vault_exists: false` | 未挂载 D 盘 | `ls /mnt/d/Open-brain-obsidian` 确认；**不得自行 mkdir 建空 vault** |
| `ModuleNotFoundError: video_inbox_v2` | 不在 `wsl_runtime` 目录下执行 | `cd` 到 `wsl_runtime` 再跑（`config.py` 按相对路径定位） |
| venv 建在别的 Python 上 | `uv venv` 未指定版本 | 用 `--python 3.12` 重建 |

## 运行时产物清单（均不入库）

`.gitignore` 已守卫以下路径：

```
.venv/
models/
cache/
temp/
__pycache__/
*.pyc
```

删除后按本文重建即可；`cache/` 丢失只影响已抓取视频的复用，不影响能力。
