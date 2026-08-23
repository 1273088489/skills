---
name: skill-map
description: 个人全量技能导航图——约 120 个技能按家族分组的路由表。当不确定该用哪个技能时使用：用户问"用哪个技能/该走什么流程/有没有能做 X 的技能"，任务方向不明需要定位入口，或想主动指定技能前先核对。先在此定位场景与入口，再加载具体技能。
---

# Skill Map — 个人技能总导航

> 先定位**场景** → 找到该家族的**入口** → 再进入具体技能。本图只指路，不执行。

## 使用规则

1. **有路由器的家族先问路由器**，不要直接猜下游技能。
2. **描述即触发**：直接说出需求，匹配的技能通常会被自动加载；本图用于主动指定与兜底。
3. 本图找不到合适技能 → `find-skills` 搜索可安装的新技能。

## 第 0 步 · 规模判断（选技能之前）

判断者是执行的 agent，无需用户指定：
- **简单**：目标单一、预计一个会话内完成 → 直接进对应技能单线干完。
- **中等**：多步骤但路径清晰 → 主技能推进，独立支线用后台 subagent 并行；有跨会话丢失风险 → 叠加 `long-task-continuation`。
- **复杂**：迷雾大、跨多个家族、明显超会话 → 先拆解再动手：**方向不明用 `wayfinder`（产出决策），方向已定用 `chaijie`（产出依赖任务）**。
- **团队自动拉起条件**（全部满足才自动组队，否则降级为后台 subagent 并行，点名才拉团）：① 可并行独立工作流 ≥3 且各自工作量可观；② 预计多轮次/长时段；③ 拉起前公告队伍构成与任务切分（说完即走，不等批准，随时可喊停）；④ 硬上限：成员 ≤4，发现方向性错误立即解散。异常兜底 `team-orchestration`。（用户已常设授权此规则）

原则：**从简起步，证据触发升级**——中途发现混淆、反调试、跨域等信号就当场叠加对应技能，不做预判性重装上阵。技能数量不是质量指标，决策点被覆盖才是。
4. `competition-*` 共 44 个为内部下游技能，仅由 `ctf-sandbox-orchestrator` 自动调度，**不要直接调用**。

## 四个总入口

| 场景 | 入口 |
|---|---|
| 工程开发全流程（想法 → 上线） | `ask-matt` |
| 安全 · 逆向 · 渗透 · DFIR | `reverse-skill-router` |
| CTF 比赛 | `ctf-sandbox-orchestrator` |
| Aegis 规范工作流检查 | `using-aegis` |

Aegis 家族另有：定目标边界 `goal-framing` · 升级方法包 `update-aegis`。

## 1. 安全 · 逆向 · 渗透

入口 `reverse-skill-router`；单一明确目标可直达：

| 目标 | 首选 |
|---|---|
| 分析任意二进制 exe/dll/so/elf | `ida-reverse`（无 IDA 用 `ghidra-reverse`；纯 CLI 用 `radare2`） |
| 特定运行时 | Go/Rust `go-rust-reverse` · .NET `dotnet-reverse` · macOS `macos-reverse` |
| 逆向理解原理（未到利用） | `reverse-engineering`；写出稳定 exploit 走 `pwn-chain` |
| 补丁差分 | N-day 武器化 `patch-diff-exploit` · 跨版本符号迁移 `binary-diff` |
| 移动端 | APK CLI 逆向 `apk-reverse` · 授权测试+Frida `mobile-reverse` |
| 前端/扩展 | JS 签名风控 `js-reverse` · 浏览器扩展 `browser-extension-reverse` · JS 自定义 VM/风控解释器 `dsl-vm-reverse` |
| 协议/固件/硬件 | 私有协议 PCAP `protocol-reverse` · 固件 IoT `firmware-pentest` · UART/JTAG `hardware-security` |
| 对抗防御方 | EDR/AV 绕过研究 `edr-bypass-re` |
| 渗透执行 | 工具链(Nmap/SQLMap/Burp) `pentest-tools` · SRC 众测实战 `src-hunter` · 多阶段编排 `attack-chain` |
| 渗透域专项 | API `api-security` · 云/K8s `cloud-k8s` · 数据库 `database-security` · 邮件 `email-security` · 身份联邦 `identity-federation` · AD `windows-ad` |
| 新兴攻击面 | LLM 应用 `llm-security` · 工控 `ot-ics` · 供应链 `supply-chain-security` · 厚客户端 `thick-client` |
| 无线 | Wi-Fi `wifi-wireless` · SDR `radio-sdr` |
| 蓝队/取证 | 威胁狩猎 `threat-hunting` · 恶意软件 `malware-analysis` · 数字取证 `digital-forensics` |
| 交付物 | 正式报告 `docs-generator`（RE/渗透/CTF 收尾必走）· 案例包审查 `case-review` |

## 2. CTF

`ctf-sandbox-orchestrator` 总入口，自动分流 competition-* 下游；出报告走 `docs-generator`。

## 3. 工程开发主流程（Matt Pocock 套件）

地图即 `ask-matt`。主干：`grill-with-docs`（追问+留 ADR）→ 设计问题谈不清时 `handoff` 进 `prototype` 再带回 → 多会话 `to-spec`→`to-tickets`→逐票 `implement`（内含 tdd + code-review）；单会话直接 `implement`。
常用单点：`grilling` · `tdd` · `code-review` · `triage`（外来 issue 分流）· `wayfinder`（超大迷雾工程）· `improve-codebase-architecture`（空闲保养）
首次使用先跑 `setup-matt-pocock-skills`。

## 4. 任务拆分 · 多智能体

拆依赖任务 `chaijie` · 计划文档 `writing-plans` → 执行 `executing-plans` · 并行委派 `dispatching-parallel-agents`（≥2 个独立任务）/ `subagent-driven-development`（按计划逐个）· AgentTeams 卡死恢复 `team-orchestration` · 跨会话续命 `long-task-continuation` · 交接后台 agent `claude-handoff`

## 5. 架构 · 代码质量

`codebase-design`（深模块词汇）· `design-an-interface`（多方案接口比选）· `setup-ts-deep-modules`（TS 深模块约束）· 统一语言 `domain-modeling`/`ubiquitous-language`/`establishing-project-context` · ADR `recording-architecture-decisions` · `first-principles-review` · 退役旧逻辑 `anti-entropy-governance` · 重构访谈 `request-refactor-plan` · `migrate-to-shoehorn` · Issue 整理 `qa`

## 6. Bug · 调试

复杂根因 `diagnosing-bugs`（反馈回路优先）· 通用调试纪律 `systematic-debugging` · 只想"看一眼解释报错"→ `ponytail` 只读模式

## 7. Git · 工程实践

`setup-pre-commit` · `git-guardrails-claude-code`（拦危险 git 操作）· `using-git-worktrees` · `resolving-merge-conflicts` · `finishing-a-development-branch` · 审查往来 `requesting-code-review`/`receiving-code-review` · 收尾核验 `verification-before-completion`

## 8. 文档 · 笔记 · 学习 · 可视化

调研落盘 `research` · 任务导向文档 `docs-generator` · Obsidian `obsidian-vault` · 视频→笔记 `video-inbox`（Windows）· 学概念 `teach` · 练习册 `scaffold-exercises` · 画图 `diagram-generator`（mermaid/graphviz/plantuml）
写作三阶段 `writing-fragments`→`writing-shape`→`writing-beats` · 改稿 `edit-article`

## 9. 浏览器 · 自动化 · 视觉

用户真实浏览器（带登录态）`kimi-webbridge` · Playwright/桌面 GUI 自动化 `browser-automation` · 交互式配置向导 `wizard` · 纯文本模型看图 `deepseek-vision`

## 10. 沟通风格 · 追问

极简回复 `communicating-concisely` · 最简方案防过度设计 `ponytail`（lite/full/ultra）· 连环追问 `grilling`（一轮问完 `batch-grill-me` · 梳理工作流 `loop-me` · 问卷化 `to-questionnaire`）

## 11. 元技能 · 环境

写/改技能 `writing-skills`+`writing-great-skills` · 找新技能 `find-skills` · Orca 操作 `orca-cli`

## 易混淆对照

| 别选错 | 区别 |
|---|---|
| `code-audit` ≠ `code-review` | 前者=安全审计（SAST/Semgrep/CodeQL）；后者=规范+规格双轴 diff 审查 |
| `tdd` ≠ `test-driven-development` | 后者=Aegis strict TDD 路由（需显式 TDD Route: strict 决策） |
| `grilling` ≠ `brainstorming` | 前者拷问已有想法暴露遗漏；后者发散定义模糊的新特性 |
| `kimi-webbridge` ≠ `browser-automation` | 前者用你真实浏览器的登录态；后者 Playwright/Windows UIA 无头自动化 |
| `wayfinder` ≠ `chaijie` | 前者解决"方向不明"——先消雾，产出决策；后者解决"方向已定但太大"——直接拆带依赖的任务。迷雾未散不拆解 |
| AgentTeams 工具 ≠ `team-orchestration` 技能 | 前者是车队本身（工具层）；后者是驾驶手册——挂起唤醒、误报核实、改派与收尾验证的异常路径手册 |

## 脚注

来源四层：`~/.dsh/skills`（自装 47 个）、`@dhicoc/dsh-reverse-skill` 插件（安全/CTF 全家）、Aegis 包（22 个流程技能）、`~/.agents/skills`（find-skills/orca-cli）。
项目专属技能只在对应仓库内生效：deepseek-harness 的 `dsh-*` 系列、new-api 的 `i18n-translate`/`shadcn-ui` 等，全局任务勿找它们。
