# DSH 本地修改保存包（权威源：本目录）

> 本目录是 DSH 定制改动的**权威存档**，随 GitHub 仓库 `1273088489/skills` 同步（与 Skills/ 平级）。
> 维护由 skill **`dsh-patch-archive`** 指导执行（"保存/更新 DSH 修改"即触发）。
> 最后更新：2026-09-20 · 目标基线：`dsh-v0.1.6-alpha.2`（`ddefc45`）

## 包结构

| 路径 | 内容 | 恢复方式 |
|---|---|---|
| `commits/0005-port-0.1.6-hand-declared-fixed-ladder.patch` | **当前唯一 commit 补丁**：手工声明的模型（无 installed catalog entry）默认拿到固定思考档位 low/medium/high/xhigh/max。提交 `e26239c` | `git am` |
| `worktree/0001-source-launch-resolution-mode.patch` | 源码启动（tsx）时默认走 `link` 解析平面，避免 src/lib 双平面导致 `reading 'prepare'` | `git apply` |
| `worktree/0002-tool-runtime-scheduler-global-symbol.patch` | `TOOL_RUNTIME_SCHEDULER` 改用 `Symbol.for`（全局符号注册表），跨模块重复求值仍共享同一 key | `git apply` |
| `dot-dsh/cordis.patch.yml` | Web profile 补丁层：web-all 全家桶按需禁用清单 | 复制回 `~/.dsh/profiles/web/` |
| `dot-dsh/profiles-web-package.json` | Web profile 插件清单与版本钉 | 对照 `~/.dsh/profiles/web/package.json` |
| `dot-dsh/vendor/dsh-mnemon-0.5.11-fix261.tgz` | **mnemon 本地修复包**（见下） | 解到本地路径后 `pnpm install` |
| `dot-dsh/settings.yaml.masked` | ~/.dsh/settings.yaml 备份（**10 个敏感字段已脱敏**） | 手动对照，填回密钥 |
| `presets/code.agent.cordis.yml` + `code.preset.yml` | `code` agent preset（已适配 0.1.6 的 `workflow-ptc`） | 复制回 `~/.dsh/.agent-presets/code/` |
| `dot-dsh/skills-subagent-effort-grading/` | 难度分级 skill 模板 | 复制回 `~/.dsh/skills/` |
| `dot-dsh/skills-dsh-patch-archive/` | **本维护 skill 自身的备份**（skill 闭环） | 复制回 `~/.dsh/skills/` |

## 2026-09-20 清理记录

### 已删除（确认过时）

| 删除项 | 原因 |
|---|---|
| `commits/0001-port-rc.7-wip-rc.2.patch` | catalog 档位已被 0005 取代；retry 调优未采用 |
| `commits/0002-hand-declared-unified-ladder.patch` | 被 0005 取代 |
| `commits/0003-subagent-reasoning-effort.patch` | **上游已原生支持**：`packages/subagent/tool-subagent/src/model-selection.ts` 自带 `reasoning_effort` 工具参数（0.1.5-rc.1 时该路径尚不存在） |
| `commits/0004-port-0.1.5-rc.1-unified-ladder.patch` | catalog 部分被 0005 取代；retry 部分未采用 |
| `dot-dsh/profiles-web-patches-liangshen.patch` | **上游已自行修复**：`@linxin666/dsh-liangshen` 自带 preset 现已是 `prefix:` 格式，不再需要 pnpm patch |

> **retry 调优说明**：0001/0004 曾把 `DEFAULT_MAX_RETRIES/INITIAL_DELAY_MS/MAX_DELAY_MS` 从
> `5/500/10000` 改成 `4/2000/15000`。该改动**未随 0.1.6 重新应用**，当前工作树是上游原值。
> 若日后需要，可从这两个已删补丁的 git 历史中取回；本包按用户决定不再保留。

### 新增归档

- `commits/0005`：把本地领先提交 `e26239c` 纳入归档
- `worktree/0001`、`worktree/0002`：把 4 个文件的未提交改动按主题拆分归档
- `dot-dsh/vendor/dsh-mnemon-0.5.11-fix261.tgz`：**恢复必需**，原因见下
- `presets/code.preset.yml`、`dot-dsh/profiles-web-package.json`、`dot-dsh/cordis.patch.yml`、`dot-dsh/settings.yaml.masked`：全部按实时状态刷新

## ⚠️ mnemon 是本地 file: 依赖（恢复时最容易踩的坑）

实时 `~/.dsh/profiles/web/package.json` 里：

```json
"dsh-mnemon": "file:/home/angel/.dsh/backups/mnemon-fix261/dsh-mnemon-0.5.11-fix261.tgz"
```

这**不是** npm 上的 `dsh-mnemon@0.5.11`。本地修复版与 npm 版差异：

| 文件 | 状态 |
|---|---|
| `lib/client.js` | **有差异**（功能修复所在） |
| `package.json` / `README.md` / `README.zh-CN.md` | 有差异（元数据） |

而 `~/.dsh/backups/` **不在本包内**，所以该 tgz 已复制进 `dot-dsh/vendor/`。
恢复时**必须**先把 tgz 放到本地路径再 `pnpm install`，否则会退回 npm 版并丢掉修复。

同时注意 memory 数据根 `~/.mnemon/`（runtime / documents / data）**也不在本包内**，需单独备份。

## 恢复步骤（克隆 DSH 到 0.1.6-alpha.2 后）

```bash
cd ~/projects/skills && git pull
cd <新克隆的 deepseek-harness>
git checkout dsh-v0.1.6-alpha.2

# 1) commit 补丁
git am ~/projects/skills/DSH-Patches/commits/0005-port-0.1.6-hand-declared-fixed-ladder.patch

# 2) 工作区改动
git apply ~/projects/skills/DSH-Patches/worktree/0001-source-launch-resolution-mode.patch
git apply ~/projects/skills/DSH-Patches/worktree/0002-tool-runtime-scheduler-global-symbol.patch

# 3) agent preset（0.1.6 用 workflow-ptc）
mkdir -p ~/.dsh/.agent-presets/code
cp ~/projects/skills/DSH-Patches/presets/code.agent.cordis.yml ~/.dsh/.agent-presets/code/agent.cordis.yml
cp ~/projects/skills/DSH-Patches/presets/code.preset.yml       ~/.dsh/.agent-presets/code/preset.yml

# 4) 自定义 skill（含本维护 skill 自身的闭环备份）
mkdir -p ~/.dsh/skills
cp -r ~/projects/skills/DSH-Patches/dot-dsh/skills-subagent-effort-grading ~/.dsh/skills/subagent-effort-grading
cp -r ~/projects/skills/DSH-Patches/dot-dsh/skills-dsh-patch-archive      ~/.dsh/skills/dsh-patch-archive

# 5) mnemon CLI（插件不含二进制）
npm install --global @mnemon-dev/mnemon@latest && mnemon --version

# 6) profile 配置 + mnemon 本地修复包
cp ~/projects/skills/DSH-Patches/dot-dsh/cordis.patch.yml ~/.dsh/profiles/web/
mkdir -p ~/.dsh/backups/mnemon-fix261
cp ~/projects/skills/DSH-Patches/dot-dsh/vendor/dsh-mnemon-0.5.11-fix261.tgz \
   ~/.dsh/backups/mnemon-fix261/
# 对照 profiles-web-package.json 钉版本
cd ~/.dsh/profiles/web && pnpm install
```

## 运行态快照（2026-09-20）

- DSH `0.1.6-alpha.2`（tag `dsh-v0.1.6-alpha.2` = `ddefc45`）
- 本地 HEAD `e26239c`（领先上游 1 个提交，即已归档的 0005）
- `@linxin666/dsh-web-all` `0.3.23`；按需启用 10 个 UI 插件（settings / plugin-manager / market / task-board / git-graph / model-capabilities / remote-web-ui / usage / session-archive / preset-center）
- `dsh-mnemon` `0.5.11`（本地修复版）+ mnemon CLI `0.2.8`
- `dsh-free-search` `0.4.32`（provider=tavily，key 在 `~/.dsh/.credentials.yaml`）

## 本包不含（需单独备份）

- `~/.mnemon/` — 记忆数据根
- `~/.dsh/.credentials.yaml` — 凭据中心
- `~/.dsh/profiles/web/node_modules/` — 依赖树
- `~/.dsh/backups/` 其他内容 — 已仅提取 mnemon 修复 tgz

## 更新流程（新增改动后）

由 `dsh-patch-archive` skill 执行：盘点 DSH 仓库（`git log origin/master..HEAD` + `git status`）→ 导出 commit/worktree patch → 脱敏复制配置 → 刷新本 README → 在目标 tag 临时 worktree 验证可应用 → commit 到本仓库（**push 需用户确认**）。

## 变更日志

- **2026-09-26 · settings 漂移修复**：按用户选择，仅刷新 `dot-dsh/settings.yaml.masked`（280 → 398 行，与实时 `~/.dsh/settings.yaml` 逐字节一致，仅 14 处敏感值脱敏：13 个 `apiKeyEnv` 名称 + `describe-image.apiKey` 明文 key）。本次同步补入：12 个自建 provider（含 `minimaxaaaa`/openrouter、`d12`/kimi-k3）、`agent-default-model`、`subagent.maxActiveSubagents`、`subagent-model-selection` 扩至 20 条、`dsh-web-ui-market.enabled: false`、`mnemon.memoryTopology.layers.runtime.enabled: false`、`mnemon-view-8887a1728307a1ff` 策略、`remote-web-ui` 配置块。
  已知剩余漂移（本次未处理，待用户确认）：`dot-dsh/cordis.patch.yml` 仍为 2026-09-20 版，缺 `web-ui-describe-image: disabled: false` 与末尾 `webserver` lan-bind 托管块（`0.0.0.0:3081`）。
- **2026-09-20**：清理过时补丁（0001–0004 与 liangshen patch 删除，理由见上）；新增 `commits/0005` 与 `worktree/0001-0002`；归档 mnemon 本地修复 tgz 到 `dot-dsh/vendor/`；刷新 preset（0.1.6 `workflow-ptc`）、package.json、cordis.patch.yml、settings.yaml.masked；同步较新的 `skill-map` / `video-inbox` 回 Skills/；基线由 0.1.5-rc.1 更新为 0.1.6-alpha.2
- **2026-09-17**：全量盘点（无新 commit / 无工作区改动）；复验 0004 在 `dsh-v0.1.5-rc.1` 可 `git am` 且 tree 一致；刷新 `settings.yaml.masked`；补齐 `dot-dsh/skills-dsh-patch-archive/`
- **2026-09-11**：关闭 dsh-mnemon 空闲复审（`writebackMode: off`）；`cordis.patch.yml` 重新归档
- **2026-09-11**：刷新 `settings.yaml.masked`（provider 大改）；`profiles-web-package.json` 加入 dsh-mnemon；新增记忆插件章节
- **2026-09-05**：归档 subagent reasoning_effort 派发与 catalog 统一思考档位两个 commit
- **2026-08-28**：建立 DSH-Patches 存档 + `dsh-patch-archive` 维护 skill
