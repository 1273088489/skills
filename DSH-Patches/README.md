# DSH 本地修改保存包（权威源：本目录）

> 本目录是 DSH 定制改动的**权威存档**，随 GitHub 仓库 `1273088489/skills` 同步（与 Skills/ 平级）。
> 维护由 skill **`dsh-patch-archive`** 指导执行（"保存/更新 DSH 修改"即触发）。
> 生成时间：2026-09-10 · 已验证：0004 在官方 tag `dsh-v0.1.5-rc.1` 上 `git apply --check` 干净通过。

## 包结构

| 路径 | 内容 | 恢复方式 |
|---|---|---|
| `commits/0001-port-rc.7-wip-rc.2.patch` | 旧基线：手工声明推理自动推断 + 重试调优（对 rc.2 / 0.1.3 用 `git am` 或 `--3way`） | 历史 |
| `commits/0002-hand-declared-unified-ladder.patch` | 旧基线：第三方模型统一 low/high/xhigh/max | 历史 |
| `commits/0003-subagent-reasoning-effort.patch` | 旧基线：子代理按次传 reasoning_effort。**0.1.5-rc.1 上游已原生支持，不要再打** | 仅旧版 |
| `commits/0004-port-0.1.5-rc.1-unified-ladder.patch` | **当前权威**：0001+0002 已 3way 移植到 `dsh-v0.1.5-rc.1`（catalog 统一档位 + 重试） | `git apply` 或 `git am` |
| `dot-dsh/cordis.patch.yml` | Web profile 补丁层（密钥已脱敏；含 0.1.5 启动稳妥禁用项） | 复制回 `~/.dsh/profiles/web/` 后填回密钥 |
| `dot-dsh/profiles-web-package.json` | Web profile 插件版本钉（dsh-web-all 0.3.20 等） | 对照 `~/.dsh/profiles/web/package.json` |
| `dot-dsh/settings.yaml.masked` | ~/.dsh/settings.yaml 备份（密钥已脱敏） | 手动对照 |
| `dot-dsh/skills-subagent-effort-grading/` | 难度分级 skill 模板 | 复制回 ~/.dsh/skills/ |

## 更新说明（2026-09-10）

- DSH 已切到官方 tag `dsh-v0.1.5-rc.1`。本地定制收成 **0004** 一笔，对应该 tag 上的 commit `d53ccc0954`。
- 0003 不要打到 0.1.5：上游已有 `reasoningEffort` / 子代理思考程度。
- Web 插件：`dsh-web-all@0.3.20`、`dsh-context@0.49.1` 等已钉到 0.1.5 适配版；`ui-chat-recovery` 与 `desktop-launcher` 默认 disabled，避免启动整组回滚。
- 旧 0001/0002 仍保留，用于从更老的 tag 恢复（0.1.5 上需 `git apply --3way`）。

## 恢复步骤（克隆 DSH 到 0.1.5-rc.1 后）

```bash
cd ~/projects/skills && git pull
cd <新克隆的 deepseek-harness>
git checkout dsh-v0.1.5-rc.1
git am ~/projects/skills/DSH-Patches/commits/0004-port-0.1.5-rc.1-unified-ladder.patch

# 配置类
cp ~/projects/skills/DSH-Patches/dot-dsh/cordis.patch.yml ~/.dsh/profiles/web/
# 对照 profiles-web-package.json 钉插件版本后 pnpm install
# settings.yaml 用 masked 版对照，手动填回真实密钥
```

## 更新流程（新增改动后）

由 `dsh-patch-archive` skill 执行：盘点 DSH 仓库（`git log origin/master..HEAD` + `git status`）→ 导出 commit/worktree patch → 脱敏复制配置 → 刷新本 README → 在目标 tag 临时 worktree 验证可应用 → commit 到本仓库（**push 需用户确认**）。
