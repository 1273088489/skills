# DSH 本地修改保存包（权威源：本目录）

> 本目录是 DSH 定制改动的**权威存档**，随 GitHub 仓库 `1273088489/skills` 同步（与 Skills/ 平级）。
> 维护由 skill **`dsh-patch-archive`** 指导执行（"保存/更新 DSH 修改"即触发）。
> 生成时间：2026-09-11 · 已验证：所有 preset 通过 DSH 0.1.5-rc.1 loader 校验（ALL PRESETS HEALTHY）。

## 包结构

| 路径 | 内容 | 恢复方式 |
|---|---|---|
| `commits/0004-port-0.1.5-rc.1-unified-ladder.patch` | **当前权威**：catalog 统一档位 + 重试（3way 移植到 `dsh-v0.1.5-rc.1`） | `git am` / `git apply --3way` |
| `commits/0001\u20130003` | 旧基线补丁（0.1.2 / 0.1.3 用）。**0003 不要打到 0.1.5**（上游已原生支持 reasoningEffort） | 历史 |
| `presets/code.agent.cordis.yml` | **0.1.5 关键修复**：persona 由 `text:` 改为 `prefix:`/`suffix:`，否则新建会话失败 | 复制回 `~/.dsh/.agent-presets/code/` |
| `dot-dsh/cordis.patch.yml` | Web profile 补丁层（密钥已脱敏；含稳妥禁用项） | 复制回 `~/.dsh/profiles/web/` 后填回密钥 |
| `dot-dsh/profiles-web-patches-liangshen.patch` | **P0 修复**：pnpm patch，修 `@linxin666/dsh-liangshen` 自带 preset 的旧 persona 格式 | 放到 `~/.dsh/profiles/web/patches/`，并在 pnpm-workspace.yaml 登记 patchedDependencies |
| `dot-dsh/profiles-web-package.json` | Web profile 插件版本钉（dsh-web-all 0.3.20 等） | 对照 `~/.dsh/profiles/web/package.json` |
| `dot-dsh/settings.yaml.masked` | ~/.dsh/settings.yaml 备份（密钥已脱敏） | 手动对照 |
| `dot-dsh/skills-subagent-effort-grading/` | 难度分级 skill 模板 | 复制回 ~/.dsh/skills/ |

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

## 恢复步骤（克隆 DSH 到 0.1.5-rc.1 后）

```bash
cd ~/projects/skills && git pull
cd <新克隆的 deepseek-harness>
git checkout dsh-v0.1.5-rc.1
git am ~/projects/skills/DSH-Patches/commits/0004-port-0.1.5-rc.1-unified-ladder.patch

# preset 修复（0.1.5 必需）
cp ~/projects/skills/DSH-Patches/presets/code.agent.cordis.yml ~/.dsh/.agent-presets/code/agent.cordis.yml

# profile 配置 + 插件
cp ~/projects/skills/DSH-Patches/dot-dsh/cordis.patch.yml ~/.dsh/profiles/web/
mkdir -p ~/.dsh/profiles/web/patches
cp ~/projects/skills/DSH-Patches/dot-dsh/profiles-web-patches-liangshen.patch ~/.dsh/profiles/web/patches/@linxin666__dsh-liangshen.patch
# 对照 profiles-web-package.json 钉版本，并在 pnpm-workspace.yaml 加：
#   patchedDependencies:
#     '@linxin666/dsh-liangshen': patches/@linxin666__dsh-liangshen.patch
cd ~/.dsh/profiles/web && pnpm install
```

## 更新流程（新增改动后）

由 `dsh-patch-archive` skill 执行：盘点 DSH 仓库（`git log origin/master..HEAD` + `git status`）→ 导出 commit/worktree patch → 脱敏复制配置 → 刷新本 README → 在目标 tag 临时 worktree 验证可应用 → commit 到本仓库（**push 需用户确认**）。
