---
name: deepseek-vision
description: 图像识别的兜底桥接。仅当原生视觉路径不可用或不够用时才使用：把图片交给外部视觉模型（默认 GLM-4.6V-Flash，经 ZHIPU_API_KEY）转成文字描述、OCR 或结构化摘要。原生优先——内联图片与可被 read_image 回灌的本地文件先由主模型直读，且不得为了"保险"而额外调用外部模型。仅当原生读数失败（乱码/报错/空白），或需要高密度版面解析（表格、表单、发票字段、密集小字 OCR）时降级到本技能。同样用于 video-inbox 等抽帧管线产生的、原生路径无法处理的图片。
---

# DeepSeek Vision (视觉桥接 / 兜底路径)

主模型能否读图由**运行时路由**决定，与厂商名无关。路由声明了图像输入（如
`inputModalities: ['text','image']`）时，主模型可直接读像素，本技能**不应介入**——
它的定位是降级兜底，不是默认入口。

## 何时使用
- 原生路径经**实测**失效：`read_image` 返回乱码、报错或空白。
- 任务需要高密度结构化版面：表格、表单、发票字段、密集小字 OCR。
- video-inbox 等抽帧管线在原生读图不可用时需要识别帧内容。

**不要**仅因为"模型是 DeepSeek 一类厂商"就调用本技能——模态是路由属性，不是品牌属性。
判定顺序永远是：先试原生，再降级。

## 规则
1. **先测原生**：内联图片直接看；磁盘文件用 `read_image` 读成像素。读得通就用原生结果。
2. **不要为了"保险"额外调外部模型**：外部 OCR 文字一旦先进入上下文，会污染原生读数，
   使这张图永远无法再作为识图能力的证据。
3. **不要并发**跑两条路径。要对比就先写下原生读数，再取外部结果比对。
4. 引用外部结果时**标注来源**，与原生读数分开陈述，不得混为一谈。
5. 脚本路径：`<本技能目录>/scripts/vision.js`（本机为
   `~/.dsh/skills/deepseek-vision/scripts/vision.js`）。运行：
   `node "<本技能目录>/scripts/vision.js" "<图片路径>" [问题]`

## 命令示例
```bash
# 本机（WSL）技能目录
SKILL_DIR=~/.dsh/skills/deepseek-vision

# 本地图片
node "$SKILL_DIR/scripts/vision.js" "/home/angel/pic.png" "描述这张截图，提取错误信息和行号"

# 网络 URL
node "$SKILL_DIR/scripts/vision.js" --url "https://example.com/a.png" "图里有什么"

# 剪贴板（Windows 侧需要 powershell.exe 可用）
node "$SKILL_DIR/scripts/vision.js" --clipboard "识别截图文字"

# JSON 输出（供脚本/Agent 解析）
node "$SKILL_DIR/scripts/vision.js" --json --image "/home/angel/a.png" "提取发票金额和日期"
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
