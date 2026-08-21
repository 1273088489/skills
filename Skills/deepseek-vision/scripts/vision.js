#!/usr/bin/env node
/**
 * DeepSeek Vision Bridge — vision.js
 *
 * 让纯文本主模型（DeepSeek 等）也能看图：把图片交给 GLM-4.6V-Flash
 * (智谱 OpenAI 兼容接口)，返回文字描述/OCR/结构化结果。
 *
 * 用法:
 *   node vision.js <图片路径> [问题]                    描述一张本地图片
 *   node vision.js --url <图片URL> [问题]               描述网络图片
 *   node vision.js --clipboard [问题]                   读剪贴板图片
 *   node vision.js --image a.png --image b.png [问题]   多图
 *   node vision.js --json --image a.png [问题]          JSON 输出(供脚本解析)
 *   node vision.js --setup                              交互式配置 + 自检
 *   node vision.js --check                              仅自检(不发图)
 *
 * 配置(环境变量):
 *   ZHIPU_API_KEY     必填  智谱 API Key
 *   VISION_MODEL      默认  glm-4.6v-flash
 *   VISION_BASE_URL   默认  https://open.bigmodel.cn/api/paas/v4
 */

const fs = require("fs");
const path = require("path");
const https = require("https");
const http = require("http");
const os = require("os");
const readline = require("readline");
const { execFileSync } = require("child_process");

// ---- 可配置项 ----
const DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4";
const DEFAULT_MODEL = "glm-4.6v-flash";
// 降级顺序：当 VISION_MODEL(默认 glm-4.6v-flash) 返回 429 限流时依次尝试这些模型
const FALLBACK_MODELS = ["glm-4v-flash", "glm-4v"];

function env(name, fallback) {
  const v = process.env[name];
  return v && v.trim() ? v.trim() : fallback;
}

// 尝试加载同目录 .env（可选，非必需）
function loadDotEnv() {
  for (const dir of [path.resolve(__dirname), process.cwd()]) {
    const p = path.join(dir, ".env");
    if (!fs.existsSync(p)) continue;
    try {
      const lines = fs.readFileSync(p, "utf8").split(/\r?\n/);
      for (const line of lines) {
        const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
        if (m && !(m[1] in process.env)) {
          process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
        }
      }
    } catch (e) { /* ignore */ }
  }
}
loadDotEnv();

const BASE_URL = env("VISION_BASE_URL", DEFAULT_BASE_URL);
const MODEL = env("VISION_MODEL", DEFAULT_MODEL);
const API_KEY = env("ZHIPU_API_KEY", "");

// ---- 提示词模板：按场景输出，省 token ----
function buildPrompt(userPrompt) {
  if (userPrompt) return userPrompt;
  return (
    "请识别这张图片，用中文输出。默认给出：1) 场景/主体概述；2) 图中可见的文字(OCR)；" +
    "3) 与错误、数据、UI 相关的关键细节。看不清的内容明确说\u4e0d看清，不要猜测。"
  );
}

const SCENE_PROMPTS = {
  error: "这是出错截图。只提取错误信息、错误代码、堆栈/行号和相关文字，逐字列出。不含无关描述。",
  ocr: "逐字提取图片中的所有文字(OCR)，按阅读顺序输出。不要添加解释。",
  ui: "这是界面截图。列出可见的应用/按钮/菜单/主要文字和布局结构。",
  chart: "这是图表/表格。提取标题、坐标轴、分类和关键数值。看不清的不要编造。",
};
// ---- 参数解析 ----
function parseArgs(argv) {
  const o = { images: [], urls: [], userPrompt: "", clipboard: false, json: false, setup: false, check: false, scene: null };
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--json") o.json = true;
    else if (a === "--clipboard") o.clipboard = true;
    else if (a === "--setup") o.setup = true;
    else if (a === "--check") o.check = true;
    else if (a === "--url") { o.urls.push(argv[++i]); }
    else if (a === "--image") { o.images.push(argv[++i]); }
    else if (a === "--scene") { o.scene = argv[++i]; }
    else if (a.startsWith("--")) { /* ignore unknown */ }
    else positional.push(a);
  }
  if (positional.length >= 1 && o.images.length === 0 && o.urls.length === 0 && !o.clipboard) {
    // 第一个位置参数是图片，其余是问题
    o.images.push(positional[0]);
    o.userPrompt = positional.slice(1).join(" ");
  } else {
    o.userPrompt = positional.join(" ");
  }
  return o;
}

// ---- 读剪贴板图片 ----
function getClipboardReader() {
  if (process.platform === "darwin") {
    return (outPath) => {
      const s = path.join(__dirname, "clipboard.swift");
      if (!fs.existsSync(s)) throw new Error("缺少 clipboard.swift");
      execFileSync("/usr/bin/swift", [s, outPath], { stdio: "pipe" });
      return outPath;
    };
  }
  if (process.platform === "win32") {
    return (outPath) => {
      const s = path.join(__dirname, "clipboard.ps1");
      if (!fs.existsSync(s)) throw new Error("缺少 clipboard.ps1");
      execFileSync(
        "powershell",
        ["-NoProfile", "-NonInteractive", "-Sta", "-ExecutionPolicy", "Bypass", "-File", s, "-OutFile", outPath],
        { stdio: "pipe", windowsHide: true }
      );
      return outPath;
    };
  }
  return null;
}

function readClipboardImage() {
  const r = getClipboardReader();
  if (!r) throw new Error("剪贴板读取暂不支持当前平台: " + process.platform + " (支持 macOS/Windows)");
  const out = path.join(os.tmpdir(), "vision-clipboard-" + Date.now() + ".png");
  r(out);
  return out;
}
// ---- 把图片转成 data URL / 校验文件 ----
function imageToDataURL(source) {
  if (/^data:image\//i.test(source)) return source;
  if (/^https?:\/\//i.test(source)) return source; // 远程 URL，直接传
  const resolved = path.resolve(source);
  if (!fs.existsSync(resolved)) throw new Error("文件不存在: " + resolved);
  const ext = path.extname(resolved).toLowerCase().replace(".", "");
  const mime = { jpg: "jpeg", jpeg: "jpeg", png: "png", gif: "gif", webp: "webp", bmp: "bmp" };
  const data = fs.readFileSync(resolved);
  return "data:image/" + (mime[ext] || "jpeg") + ";base64," + data.toString("base64");
}

// ---- 发起 OpenAI 兼容请求 ----
function request(payload) {
  const url = new URL(BASE_URL.replace(/\/?$/, "") + "/chat/completions");
  const body = JSON.stringify(payload);
  const transport = url.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const req = transport.request(
      url,
      { method: "POST", headers: { Authorization: "Bearer " + API_KEY, "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) } },
      (res) => {
        let data = "";
        res.on("data", (c) => (data += c));
        res.on("end", () => {
          if (res.statusCode >= 400) {
            let msg = data;
            try { msg = JSON.parse(data).error?.message || data; } catch (e) { /* keep raw */ }
            return reject(new Error("API " + res.statusCode + ": " + String(msg).slice(0, 500)));
          }
          try { resolve(JSON.parse(data)); }
          catch (e) { reject(new Error("响应解析失败: " + data.slice(0, 300))); }
        });
      }
    );
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

function buildContent(images) {
  // 多图时，每张作为独立 content part（OpenAI 兼容多图）
  return images.map((img) => {
    const dataUrl = imageToDataURL(img);
    if (/^https?:/.test(dataUrl)) {
      return { type: "image_url", image_url: { url: dataUrl } };
    }
    return { type: "image_url", image_url: { url: dataUrl } };
  });
}
function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(question, (a) => { rl.close(); resolve(a.trim()); }));
}

async function setup() {
  const current = API_KEY || "(未设置)";
  console.log("当前 ZHIPU_API_KEY: " + current);
  const key = await ask("请输入新的智谱 API Key（留空保持不变）: ");
  if (key) {
    process.env.ZHIPU_API_KEY = key;
    console.log("已临时设置。建议写入 Windows 用户环境变量（持久生效）。");
  }
  console.log("模型: " + MODEL);
  console.log("Base URL: " + BASE_URL);
  const doCheck = await ask("是否现在用一张占位自检？(y/n) ");
  if (doCheck.toLowerCase() === "y") {
    console.log("自检需要真实图片。请稍后运行: node vision.js <图片路径> 验证链路。");
  }
}

async function check() {
  const ok = { key: !!API_KEY, baseUrl: DEFAULT_BASE_URL, model: MODEL };
  console.log("ZHIPU_API_KEY: " + (ok.key ? "已设置" : "未设置(必需)"));
  console.log("VISION_MODEL: " + MODEL);
  console.log("VISION_BASE_URL: " + BASE_URL);
  if (!ok.key) {
    console.log("提示: 请设置环境变量 ZHIPU_API_KEY，或运行 --setup。");
    process.exitCode = 1;
  }
}

async function main() {
  const o = parseArgs(process.argv.slice(2));

  if (o.setup) { await setup(); return; }
  if (o.check) { await check(); return; }

  if (!API_KEY) {
    console.error("错误: 未设置 ZHIPU_API_KEY 环境变量。请运行 node vision.js --setup 或设置环境变量。");
    process.exit(1);
  }

  // 汇总图片源
  const sources = [];
  for (const im of o.images) sources.push(im);
  for (const u of o.urls) sources.push(u);
  if (o.clipboard) sources.push(readClipboardImage());

  if (sources.length === 0) {
    console.error("用法: node vision.js <图片路径|--url <url>|--clipboard> [问题]  [--json] [--scene error|ocr|ui|chart]");
    process.exit(1);
  }

  const scenePrompt = o.scene ? SCENE_PROMPTS[o.scene] || o.scene : null;
  const text = o.userPrompt || scenePrompt || buildPrompt();

  const content = buildContent(sources).concat({ type: "text", text });

  // 依次尝试主模型和降级模型；429(限流)时自动降级，其他错误直接失败
  const modelQueue = [MODEL, ...FALLBACK_MODELS.filter((m) => m !== MODEL)];
  let usedModel = MODEL;
  let answer = null;
  let lastError = null;

  for (const m of modelQueue) {
    const payload = { model: m, messages: [{ role: "user", content }], temperature: 0.1 };
    try {
      const resp = await request(payload);
      answer = resp.choices?.[0]?.message?.content ?? "(无返回内容)";
      usedModel = m;
      break;
    } catch (e) {
      lastError = e;
      const isRateLimit = /429|1305|访问量过大|限流/i.test(String(e.message || e));
      if (!isRateLimit) break; // 非限流错误不降级
      if (!o.json) console.error("模型 " + m + " 限流(429)，自动降级到下一个…");
    }
  }

  if (answer === null) {
    const msg = lastError ? String(lastError.message || lastError) : "所有视觉模型均失败";
    if (o.json) console.log(JSON.stringify({ ok: false, error: msg }));
    else console.error("识图失败: " + msg);
    process.exit(1);
  }

  if (o.json) {
    console.log(JSON.stringify({ ok: true, model: usedModel, sources, answer }, null, 2));
  } else {
    if (usedModel !== MODEL) console.error("(使用降级模型: " + usedModel + ")");
    console.log(answer);
  }
}

main().catch((e) => { console.error("识图失败: " + (e.message || e)); process.exit(1); });
