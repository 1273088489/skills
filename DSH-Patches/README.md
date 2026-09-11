# DSH 本地修改保存包（权威源：本目录）

> 本目录是 DSH 定制改动的**权威存档**，随 GitHub 仓库 `1273088489/skills` 同步（与 Skills/ 平级）。
> 维护由 skill **`dsh-patch-archive`** 指导执行（"保存/更新 DSH 修改"即触发）。
> 生成时间：2026-09-11 · 已验证：所有 preset 通过 DSH 0.1.5-rc.1 loader 校验（ALL PRESETS HEALTHY）。

## 包结构

| 路径 | 内容 | 恢复方式 |
|---|---|---|
| `commits/0004-port-0.1.5-rc.1-unified-ladder.patch` | **当前权威**：catalog 统一档位 + 重试（3way 移植到 `dsh-v0.1.5-rc.1`）。patch-id `5cf3a9e3` 与 HEAD `d53ccc0954` 校验一致 | `git am` / `git apply --3way` |
| `commits/0001–0003` | 旧基线补丁（0.1.2 / 0.1.3 用）。**0003 不要打到 0.1.5**（上游已原生支持 reasoningEffort） | 历史 |
| `presets/code.agent.cordis.yml` | **0.1.5 关键修复**：persona 由 `text:` 改为 `prefix:`/`suffix:`，否则新建会话失败 | 复制回 `~/.dsh/.agent-presets/code/` |
| `dot-dsh/cordis.patch.yml` | Web profile 补丁层（密钥已脱敏；含稳妥禁用项） | 复制回 `~/.dsh/profiles/web/` 后填回密钥 |
| `dot-dsh/profiles-web-patches-liangshen.patch` | **P0 修复**：pnpm patch，修 `@linxin666/dsh-liangshen` 自带 preset 的旧 persona 格式 | 放到 `~/.dsh/profiles/web/patches/`，并在 pnpm-workspace.yaml 登记 patchedDependencies |
| `dot-dsh/profiles-web-package.json` | Web profile 插件版本钉（dsh-web-all 0.3.20、**dsh-mnemon ^0.5.7** 等） | 对照 `~/.dsh/profiles/web/package.json` |
| `dot-dsh/settings.yaml.masked` | ~/.dsh/settings.yaml 备份（**20 个敏感字段已脱敏为 `<MASKED>`**） | 手动对照，填回密钥 |
| `dot-dsh/skills-subagent-effort-grading/` | 难度分级 skill 模板 | 复制回 ~/.dsh/skills/ |

## ⚠️ liangshen preset 为什么不单独归档

`~/.dsh/.agent-presets/liangshen/`（agent.cordis.yml / preset.yml / custom-bash.mjs / tool-bootstrap.mjs / NOTICE）
**由 `@linxin666/dsh-liangshen` 插件在 host 启动时自动同步**，5 个文件经逐一比对与插件 `presets/liangshen/` 完全一致。

- 用户层不是权威源，归档用户层会产生"看起来是修复、实际被插件覆盖"的假象
- 上游已在插件自带 preset 里改用 `prefix:` 格式；若旧版上游回退，由 `profiles-web-patches-liangshen.patch` 兜底
- **结论：不需要也不应该把用户层 liangshen preset 纳入本包**（2026-09-11 复核修正）

## 0.1.5 升级踩坑修复记录（2026-09-11）

### P0（已修）：persona 配置格式变更导致新建会话失败

DSH 0.1.5 把 `@deepseek-ai/dsh-persona` 的配置从 `text:` 拆成 `prefix:`（**必填**）+ `suffix:`。

- `~/.dsh/.agent-presets/code/agent.cordis.yml`：默认 preset，已修（原 `text:` → `prefix:`+`suffix:`）
- `~/.dsh/.agent-presets/liangshen/agent.cordis.yml`：已修
- `@linxin666/dsh-liangshen` **自带的 preset 也是旧格式**，且插件启动会同步覆盖用户层 → 已用 **pnpm patch 持久修复**，重装不丢

症状：新建会话直接失败（挂载阶段 schema 校验 `$.prefix missing required value`）。

### P1（已清理）：archive-manager 冗余禁用项

`web-ui-archive-manager` 未安装且 web-all 已不再打包，原先的 `disabled` 行为无指向的死配置，已移除。

### 仍需注意

- `ui-chat-recovery` 依赖的 `@deepseek-ai/dsh-client-runtime` 在 0.1.5 已删除（提交 `be531688f3`），**必须保持禁用**，等作者发布适配版
- `desktop-launcher` 声明面在 0.1.5 仍存在，可尝试启用；失败再关回

## 记忆插件：dsh-mnemon（2026-09-11 新增）

Web profile 采用 **`dsh-mnemon ^0.5.7`** + 全局 `@mnemon-dev/mnemon` CLI `0.2.8` 作为长期记忆方案（未采用 dsh-memory-evolve）。

**恢复时必须注意**：

1. **CLI 要先装**（插件不含二进制）：`npm install --global @mnemon-dev/mnemon@latest`
2. **必须钉 `0.5.7`，不要用 `0.5.6`**：0.5.7 的 `cordis.patch.yml` 新增了
   `- id: connection \ inject: [webRuntime, webServer]`。DSH 0.1.5 的 Web profile 只在 `connection` 上注入 `webRuntime`，
   缺 `webServer` 会让 mnemon 的 7 条 RPC 通道全部注册失败（记忆系统页面 HTTP 405）。
3. **pnpm `minimumReleaseAge` 会默认挡回 0.5.7**，需显式指定版本：
   `dsh plugin --profile web add dsh-mnemon@0.5.7`
4. 数据根 `~/.mnemon/`（runtime / documents / data），**不在本包内**，需单独备份或用 Mnemon Pack 导出

## 恢复步骤（克隆 DSH 到 0.1.5-rc.1 后）

```bash
cd ~/projects/skills && git pull
cd <新克隆的 deepseek-harness>
git checkout dsh-v0.1.5-rc.1
git am ~/projects/skills/DSH-Patches/commits/0004-port-0.1.5-rc.1-unified-ladder.patch

# preset 修复（0.1.5 必需）
cp ~/projects/skills/DSH-Patches/presets/code.agent.cordis.yml ~/.dsh/.agent-presets/code/agent.cordis.yml

# 记忆插件 CLI（必须先装二进制）
npm install --global @mnemon-dev/mnemon@latest && mnemon --version

# profile 配置 + 插件
cp ~/projects/skills/DSH-Patches/dot-dsh/cordis.patch.yml ~/.dsh/profiles/web/
mkdir -p ~/.dsh/profiles/web/patches
cp ~/projects/skills/DSH-Patches/dot-dsh/profiles-web-patches-liangshen.patch ~/.dsh/profiles/web/patches/@linxin666__dsh-liangshen.patch
# 对照 profiles-web-package.json 钉版本，并在 pnpm-workspace.yaml 加：
#   patchedDependencies:
#     '@linxin666/dsh-liangshen': patches/@linxin666__dsh-liangshen.patch
cd ~/.dsh/profiles/web && pnpm install
dsh plugin --profile web add dsh-mnemon@0.5.7   # 必须钉 0.5.7，见上
```

## 验证记录（2026-09-11）

在临时 worktree 上实测，恢复链路可用：

| 验证项 | 方法 | 结果 |
|---|---|---|
| commit 0004 可应用 | `git worktree add <tmp> dsh-v0.1.5-rc.1` → `git am 0004` | ✅ 成功 |
| **内容精确性** | 应用后 `HEAD^{tree}` 与实时 DSH `HEAD^{tree}` 对比 | ✅ **`f438ba61` 完全相同** |
| patch-id | `git show HEAD \| git patch-id --stable` | ✅ `5cf3a9e3` 两侧一致 |
| patch 可重复应用 | `git apply --check` | ✅ 通过 |
| preset / pnpm patch | 与 `~/.dsh` 实时文件 `diff` | ✅ 逐字节一致 |
| 脱敏完整性 | grep 密钥模式 | ✅ 无残留 |

**关于基线的重要说明**：本地 `master`（`d53ccc09`）的父提交是 **`183f08e9`**，即 tag `dsh-v0.1.5-rc.1`；
而 `origin/master` 已前进到 `aa8262ec09`（多出 9 个 commit，全部是 docs / README 类改动）。

- 归档 0004 忠实记录了**用户当时的真实基线**，在 `dsh-v0.1.5-rc.1` 上可**精确重建**（tree 全等）
- 在 `origin/master` 上也能 `am` 成功（因改动集中在 `packages/llm/`，与 docs 不冲突），但 tree 会因上游 docs 变化而不同——**这是正常的，不代表归档有误**
- 恢复时**优先 `git checkout dsh-v0.1.5-rc.1`**，与 README 恢复步骤一致

## 更新流程（新增改动后）

由 `dsh-patch-archive` skill 执行：盘点 DSH 仓库（`git log origin/master..HEAD` + `git status`）→ 导出 commit/worktree patch → 脱敏复制配置 → 刷新本 README → 在目标 tag 临时 worktree 验证可应用 → commit 到本仓库（**push 需用户确认**）。

## 变更日志

- **2026-09-11（本次）**：刷新 `settings.yaml.masked`（模型/provider 大改：新增 yydsgrok / yydsglm / cat / newapi / d1，移除 wc-glm / wc-ds，新增 subagent-model-selection）；`profiles-web-package.json` 加入 dsh-mnemon；新增「记忆插件 dsh-mnemon」章节与 0.5.7 钉版本说明；复核确认 liangshen preset 无需归档（插件自动同步）
- **2026-09-11**：`fix(dsh-patches)`：0.1.5 persona 格式修复（P0）+ 清理冗余禁用项（P1）
- **2026-09-10**：归档 0.1.5-rc.1 移植补丁 0004 与稳妥插件配置
- **2026-09-05**：归档 subagent reasoning_effort 派发与 catalog 统一思考档位两个新 commit
- **2026-08-28**：建立 DSH-Patches 存档 + dsh-patch-archive 维护 skill
