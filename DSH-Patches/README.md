# DSH 本地修改保存包（权威源：本目录）

> 本目录是 DSH 定制改动的**权威存档**，随 GitHub 仓库 `1273088489/skills` 同步（与 Skills/ 平级）。
> 维护由 skill **`dsh-patch-archive`** 指导执行（"保存/更新 DSH 修改"即触发）。
> 生成时间：2026-08-28 · 已验证：两个 patch 在官方 origin/master（rc.2）上干净应用。

## 包结构

| 路径 | 内容 | 恢复方式 |
|---|---|---|
| `commits/0001-port-rc.7-wip-rc.2.patch` | 已提交本地 commit：模型推理能力自动推断 + 重试调优（catalog.ts / retry-policy.ts + 4 测试） | `git am`（保留 commit 信息） |
| `worktree/live-route-and-effort.patch` | 工作区改动：子代理活路由 + 思考等级派发（6 源码 + 1 新测试） | `git apply` |
| `dot-dsh/settings.yaml.masked` | ~/.dsh/settings.yaml 备份（密钥已脱敏，恢复时手动填回） | 手动对照 |
| `dot-dsh/skills-subagent-effort-grading/` | 难度分级 skill 模板 | 复制回 ~/.dsh/skills/ |
| `dot-dsh/cordis.patch.yml` | Web profile 插件补丁层 | 复制回 ~/.dsh/profiles/web/ |

## 恢复步骤（克隆新 DSH 仓库后）

```bash
# 0) 拉取本仓库
cd ~/projects/skills && git pull

# 1) 已提交改动
cd <新克隆的 deepseek-harness>
git am ~/projects/skills/DSH-Patches/commits/*.patch

# 2) 工作区改动
git apply ~/projects/skills/DSH-Patches/worktree/*.patch

# 3) 配置类（仓库外，克隆不覆盖，双保险）
cp -r ~/projects/skills/DSH-Patches/dot-dsh/skills-subagent-effort-grading ~/.dsh/skills/
cp ~/projects/skills/DSH-Patches/dot-dsh/cordis.patch.yml ~/.dsh/profiles/web/
# settings.yaml 用 masked 版对照，手动填回真实密钥
```

## 更新流程（新增改动后）

由 `dsh-patch-archive` skill 执行：盘点 DSH 仓库（`git log origin/master..HEAD` + `git status`）→ 导出 commit/worktree patch → 脱敏复制配置 → 刷新本 README → 在 origin/master 临时 worktree 验证可应用 → commit 到本仓库（**push 需用户确认**）。
