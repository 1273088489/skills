---
name: dsh-patch-archive
description: 维护用户的 DSH 本地改动保存包。当用户说「保存/更新 DSH 修改」「更新补丁包」「把我的改动存起来」时使用：把 DSH 仓库里的新改动（未 push 的 commit + 工作区改动 + 配置类文件）导出到保存包并验证可复用。
---

# DSH 补丁保存包维护

用户的 DSH 定制改动统一收在 **`~/projects/skills/DSH-Patches/`**（GitHub 仓库 `1273088489/skills` 的平级目录，是权威源）。DSH 发布新版或重新克隆仓库后，靠这个包一键恢复。

## 包结构（以 DSH-Patches/README.md 为最新清单）

| 路径 | 内容 |
|---|---|
| `commits/*.patch` | 已提交的本地 commit（未 push 的上游领先提交），用 `git am` 恢复 |
| `worktree/*.patch` | 未提交的工作区改动，用 `git apply` 恢复；按功能主题拆文件 |
| `dot-dsh/settings.yaml.masked` | ~/.dsh/settings.yaml 脱敏备份（恢复时手动填回密钥） |
| `dot-dsh/skills-*/ ` | ~/.dsh/skills 下的自定义 skill 模板 |
| `dot-dsh/cordis.patch.yml` | Web profile 插件补丁层 |

## 更新流程（用户要求保存新改动时执行）

1. **盘点 DSH 仓库**（`/home/angel/deepseek-harness`）：
   - 新 commit：`git log origin/master..HEAD --oneline`（本地领先上游的都是用户改动）
   - 工作区：`git status --short` + `git diff --stat`
   - 新文件要纳入 diff：`git add -N <文件>` 后再 `git diff`
2. **导出 commit**：`git format-patch -N <sha> -o DSH-Patches/commits --stdout > DSH-Patches/commits/<NNN>-<描述>.patch`（保留 commit 信息）
3. **导出工作区改动**：按功能主题拆多个 patch（如 retry、活路由、effort 分开），写入 `DSH-Patches/worktree/`
4. **导出配置类**：settings.yaml（**密钥脱敏**）、自定义 skill、cordis.patch.yml 复制进 `dot-dsh/`
5. **刷新 README**：更新包结构清单、恢复步骤、变更日志
6. **验证**：在临时 worktree 上用官方上游测试可应用性：
   ```bash
   git -C /home/angel/deepseek-harness worktree add /tmp/dsh-verify origin/master
   cd /tmp/dsh-verify && git am <commit patch> && git apply --check <worktree patch>
   git -C /home/angel/deepseek-harness worktree remove /tmp/dsh-verify --force
   ```
7. **提交到 skills 仓库**：`git -C ~/projects/skills add -A && git commit`（**push 必须经用户确认**，不自动 push）

## 恢复流程（用户克隆新源码后）

1. 从 skills 仓库拉取：`cd ~/projects/skills && git pull`
2. 到新克隆的 DSH 仓库：`git am ~/projects/skills/DSH-Patches/commits/*.patch` → `git apply ~/projects/skills/DSH-Patches/worktree/*.patch`
3. 配置类按 README 复制回 `~/.dsh/`

## 边界

- **只导出不破坏**：所有 git 操作只读（format-patch / diff），不改 DSH 仓库内容
- **push 需确认**：skills 仓库的 push 是外部副作用，必须先问用户
- **冲突处理**：新版 DSH 改了同批文件导致 apply 失败时，用 `git apply --reject` 看 `.rej` 手工合并
- **skill 闭环**：本 skill 的模板也在 `dot-dsh/skills-dsh-patch-archive/` 备份，最坏情况（~/.dsh 被删）可从包里恢复
