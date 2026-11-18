---
name: back-translate-refinement
description: 回译精修（Back-Translation Refinement）工作流。当用户需要将中文原稿翻译为英文并确保语义精确一致，或提出"回译""翻译精修""back-translate""翻译打磨""翻译校对"等请求时使用。通过"正译→回译→硬闸→语义比对→修正"的迭代循环消除单向翻译的语义损耗；占位符机制完整保留插图、表格、文献、公式；确定性脚本产出可转发的质检报告。
version: 2.0.0
agent_created: true
---

# Back-Translate Refinement 回译精修

## Purpose

把「中文原稿」变成**语义精确、与原意完全一致**的「英文译稿」，并完整保留原稿中的非文本元素（插图、表格、文献引用、公式、数学符号）。

核心思想：**单向翻译的损耗看不见，回译把损耗变成可见的差异**——正译（中→英）→ 回译（英→中）→ 比对（回译稿 vs 原稿）→ 修正英文 → 再回译，循环到语义一致。

两层质检，各司其职，不可互相替代：

| 层 | 谁来做 | 判什么 | 为什么 |
|---|---|---|---|
| **硬闸（guard.py）** | 脚本，100% 确定性 | 占位符、公式、数字、引用、段落覆盖、术语一致性、漏译残留、长度异常 | LLM 数数字不可靠、数结构不可靠、保一致不可靠；这三类恰是审稿人最先挑的硬错误 |
| **语义比对（Step 5）** | 模型/人工 | 语义缺失、添加、扭曲四分类 | 机械项全对 ≠ 意思没变；「手段不同但结果相同」只有语义层能判 |

## When to Use

- 用户要求"回译精修""翻译精修""回译""翻译打磨""back-translate""翻译校对"。
- 用户需要把中文稿件翻译为英文，且要求语义与原稿严格一致（学术论文、基金申报、技术报告）。
- 待处理文档包含插图、表格、公式、引用等必须原样保留的结构化内容。

## Workflow

### Step 0 — 环境闸与诊断（免费、只读）

```bash
python scripts/check_env.py
python scripts/bt_probe.py 原稿.md --translation 译稿.md 2>/dev/null || python scripts/bt_probe.py 原稿.md
```

- probe 给出：段数、汉字数、受保护元素统计、分批建议、风险清单（如「含 12 处公式但无占位符」「docx 公式对象转文本会丢」）。
- **先修结构问题再翻译**：probe 报的每一条「高」级风险都必须在 Step 2 之前解决。
- 超过 60 段或 1500 字 × N：按 probe 建议分批，每批独立走完整个循环后再合并。

### Step 1 — 术语固化（先于一切翻译）

```bash
python scripts/glossary.py extract --source 原稿.md --out terms_draft.csv
python scripts/glossary.py validate --glossary terms.csv
```

- 从候选清单里确认译法（原文自带「中文（English）」对照的会自动填入）。
- **术语表是后续所有一致性检查的基准**。没有术语表，术语漂移（第 3 段 attention mechanism、第 9 段 focus mechanism）无从谈起。
- 领域已有规范译名（如标准术语、期刊惯例）优先采用；拿不准的标进 note，交付时向用户说明。

### Step 2 — 正译（Forward Translation）

把原稿逐段译为英文：

- **段号即锚点**：一段对一段，不合并、不拆分、不调序。段数对不上，一切比对失效（guard 第一项就是查这个）。
- 遇插图/表格/引用/公式/行内数学，按 `references/structured-preservation.md` 加 `<KEEP:type:id>` 占位，ID 全程不变。
- 仅译正文；不改写占位元素，不翻译占位标记本身。

### Step 3 — 回译（Back Translation）

把英文译稿逐段译回中文（不看原稿！）：

- 段落对应与 Step 2 完全一致；占位标记原样保留。
- **回译必须「盲」**：如果先看了原稿再回译，损耗会被悄悄补上，比对就失去意义。这是整个机制的根基。

### Step 4 — 硬闸（先于语义比对）

```bash
python scripts/guard.py --source 原稿.md --translation 译稿.md --back 回译稿.md \
  --glossary terms.csv --json out.json
```

- 退出码 0=PASS / 1=WARN / 2=FAIL。**error 不清零，禁止进入语义比对**——在语义有问题的稿子上做语义精修是浪费时间。
- error 项（必须修）：段落覆盖、占位符数量、占位符顺序、公式、数字、引用、译稿残留中文。
- warn 项（需人工确认）：术语一致性、长度比越界、相邻重复段。
- 修复 = 改英文译稿 → 重新回译对应段 → 重跑 guard。逐条清零后进入 Step 5。

### Step 5 — 语义比对与修正（迭代）

逐段比较「回译稿」与「原稿」，按 `references/fidelity-rubric.md` 归类：

- **语义缺失** / **语义添加** / **语义扭曲** / **术语不一致**。
- 只比较实质含义，措辞差异不算差异。
- 修正循环：改英文 → 重回译该段 → 再比对。约束：
  - 迭代上限默认 **5 轮**；
  - 同一段**连续 2 轮无改进**即停，记入修改记录并提示用户；
  - 只改有差异的段落，已一致的段落不动（避免越改越错）。

### Step 6 — 终检与报告

```bash
python scripts/guard.py --source 原稿.md --translation 译稿.md --back 回译稿.md \
  --glossary terms.csv --json final.json && python scripts/report.py final.json
```

- 最终 guard 必须 PASS 或 WARN（有 error 就继续修）。
- `report.py` 生成 Markdown + 单文件 HTML 质检报告（含输入哈希与复现命令），可直接转发给合作者/导师。

### Step 7 — 替换与交付

用最终英文段落替换原稿中的中文段落：

- 占位符按 ID 还原为原始元素，还原后校验：数量一致、内容未改动、位置一致（guard 的 keep 检查就是干这个的）。
- 交付物：
  1. **最终英文稿**（默认；可选中英对照）；
  2. **修改记录**（逐段：迭代轮次、修正原因）；
  3. **质检报告**（HTML/Markdown）；
  4. （若有）**残留差异提示**：达到迭代上限仍未完全一致的段落，明确列出供用户裁决。

## Structured-Element Preservation（关键）

原稿中的插图/表格/引用/公式/行内数学**一律不翻译、不删除、不改动**，全程用 `<KEEP:type:id>` 占位（规范与识别规则见 `references/structured-preservation.md`）。两条铁律：

1. 同一元素的 ID 在正译、回译、比对、修正、还原全程不变；
2. 占位标记本身永不翻译、永不改写。

## Output Format

1. **最终英文稿**（中文段落已替换，结构化元素原样保留）
2. **修改记录**（逐段：是否修正、迭代轮次、原因）
3. **质检报告**（`report.py` 产物，Markdown + HTML）
4. （可选）中英对照表、残留差异提示

## Notes

- 始终以用户的中文原稿为**语义基准**；回译只是检测手段，不是修订目标。
- guard 报告 ≠ 语义验收。报告 PASS 只说明机械项干净；语义一致性由 Step 5 负责。
- 若原稿不含任何结构化元素，可跳过占位符直接做段落级正译/回译（guard 的 keep/cite/math 项会自动 PASS）。
- 分批处理时，术语表与占位符 ID 必须全篇统一（ID 按全篇顺序编，不按批重编）。
