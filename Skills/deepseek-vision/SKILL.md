---
name: deepseek-vision
description: Bridge visual understanding for text-only models like DeepSeek. When the active model cannot natively read images, delegate the image to an external vision model (default GLM-4.6V-Flash via ZHIPU_API_KEY) and return a written description/OCR/structured summary for the text model to reason over. Use when the user shares, attaches, pastes, references, or points to an image (local file, URL, clipboard, or extracted video frame), asks to describe/read/OCR/analyze an image, or when a pipeline (such as video-inbox frame extraction) produces image paths that a text-only model must understand. Do not use Read on images; call the bundled vision.js instead.
---

# DeepSeek Vision (视觉桥接)

给纯文本主模型（DeepSeek 等）装上"识图能力"：把图片交给外部视觉模型，转成文字后交给主模型继续推理。

## 何时使用
- 主模型无法原生识图，却收到图片路径 / 截图 / 剪贴板图 / 视频帧。
- 用户要求描述、读图、OCR、分析 UI/图表。
- 其他 Skill（如 video-inbox）抽帧后需要识别帧内容。

## 规则
1. **不要**用 `Read` 工具直接读图片（文本模型读不出像素）。
2. 遇到图片路径，运行：`node "C:\Users\12730\.codex\skills\deepseek-vision\scripts\vision.js" "<图片路径>" [问题]`
3. 把返回的文字描述作为证据交给主模型推理。

## 命令示例
```bash
# 本地图片
node "...\deepseek-vision\scripts\vision.js" "D:\shot.png" "描述这张截图，提取错误信息和行号"

# 网络 URL
node "...\deepseek-vision\scripts\vision.js" --url "https://example.com/a.png" "图里有什么"

# 剪贴板
node "...\deepseek-vision\scripts\vision.js" --clipboard "识别截图文字"

# JSON 输出（供脚本/Agent 解析）
node "...\deepseek-vision\scripts\vision.js" --json --image "D:\a.png" "提取发票金额和日期"
```

## 配置
- 环境变量 `ZHIPU_API_KEY`（必填）：智谱 API Key。
- 可选：`VISION_MODEL`（默认 `glm-4.6v-flash`）、`VISION_BASE_URL`（默认 `https://open.bigmodel.cn/api/paas/v4`）。
- 首次使用建议先跑自检：`node "...\vision.js" --setup` 或 `node "...\vision.js" --check`。

## 自动降级
- 首选 `glm-4.6v-flash`（免费，官方文档主推）。
- 若该模型返回 429「访问量过大」限流，会自动依次降级到 `glm-4v-flash` → `glm-4v`，避免识别失败。
- 降级时会在输出前提示 `(使用降级模型: xxx)`；JSON 模式通过 `model` 字段反映实际所用模型。

## 隐私
- 图片会以 base64 发送到智谱 `open.bigmodel.cn` 做识别。
- 只把识别文字写回；不把图片复制到 Vault 或日志。
