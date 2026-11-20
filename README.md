# back-translate-refinement

[English](README.en.md) | 简体中文

[![CI](https://img.shields.io/github/actions/workflow/status/GongfaChen/back-translate-refinement/ci.yml?branch=main&label=CI)](https://github.com/GongfaChen/back-translate-refinement/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/GongfaChen/back-translate-refinement)](https://github.com/GongfaChen/back-translate-refinement/releases)
[![license](https://img.shields.io/github/license/GongfaChen/back-translate-refinement)](LICENSE)
[![python](https://img.shields.io/badge/python-3.12%2B-3776AB)](requirements.txt)
[![platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

**Agent skill：把中文稿件翻译成"语义严格一致"的英文——回译比对 + 确定性保真闸 + 可转发的质检报告。**

不是"又一个翻译工具"。翻译质量不是靠模型更大，而是靠**让损耗可见**：

```text
中文原稿 ──正译──▶ 英文译稿 ──回译（盲）──▶ 中文回译稿
                                                │
                中文原稿 ◀────── 逐段比对 ──────┘
                     │
                     ▼
        缺失 / 添加 / 扭曲 / 术语漂移 → 修英文 → 再回译 → 循环
```

工具链把循环里**机械可判**的部分全部自动化（LLM 数数字不可靠、数结构不可靠、保一致不可靠——这三类恰是审稿人最先挑的硬错误）。

> **配套仓库**：[pdf-to-pptx-omml](https://github.com/GongfaChen/pdf-to-pptx-omml)
> —— 把 PDF 教材章节变成公式可编辑的 PPT（含扫描版教材）。
> 英文讲义要做出来再翻好，两仓可以串成全链路。

## 效果演示

`demo/` 里有一份 7 段样稿，**故意植入 6 类典型缺陷**（漏一段、丢表格占位、丢公式、12M 写成 21M、残留中文、术语漂移）。guard 全部抓到，并生成可转发的质检报告：

![质检报告](assets/report_preview.png)

```bash
cd demo && python smoke_test.py     # 复现：跑样稿、断言 6 类缺陷全被抓住
```

## 真实案例：一篇投稿论文的中译英稿

上面的样稿是"植入缺陷"的教学例子。`demo/real-case/` 里的是**真实产物**：
一篇桥梁监测论文（拱桥吊杆索力异常两阶段识别）的中译英稿，脱敏后放出了
**机器正译初稿**与**回译比对精修后**两版对照。

**摘要首句**（精修改动最大的一段）：

| | |
|---|---|
| 中文 | 针对运行荷载变化下桥面振动特征易受干扰、异常检出难以直接给出吊杆状态信息的问题，提出……两阶段识别方法 |
| 初稿 | To address **interference from** varying operational loads and **the limited** hanger-state information **provided by** anomaly detection alone, a two-stage **method combines** a Modal-Space Anomaly Index…… |
| 精修 | To address **the susceptibility of deck-vibration features to interference under** varying operational loads and **the difficulty for** anomaly detection alone **to provide** hanger-state information **directly**, a two-stage **identification method is proposed that combines**…… |

改动不是"换个词显得更高级"，而是把中文的**主语与因果**补回英文里：原句说的是"桥面振动特征易受干扰"，
初稿写成 `interference from loads`，主语丢了；精修把它显式化为 `the susceptibility of deck-vibration features to interference`。

**术语与拼写体系**（全文 42 个被改单元里，大多数是这一类）：

```
localization → localisation      standardization → standardisation
normalizes   → normalises        regression-output → regression output
classify predefined → discriminate
```

**全文口径**（359 个单元，本案例是其中 14 块）：

| 指标 | 值 |
|---|---|
| 精修改动单元 | 42（11.7%） |
| 数字 token / 引用 token | 882 / 28 |
| 初稿 → 精修的事实级变动 | **0**（数字、引用、`Eq.` 编号逐字保留，脚本逐块复算） |
| 保真闸 | 10 项全 PASS |

```bash
cd demo/real-case && python run_real_case.py    # 保真闸 + 增量校验 + 变更分类，约 1 秒
```

逐段并列见 [`demo/real-case/before_after.md`](demo/real-case/before_after.md)，
质检报告见 [`demo/real-case/guard_real_report.html`](demo/real-case/guard_real_report.html)。

> 有一处值得单说：精修稿原本把 `15` 写成 `Fifteen`，**保真闸当场报了 error**（中文是数字 15）。
> 处置不是简单换回数字——英文句首不宜以阿拉伯数字开头——而是把数字移进句中：
> `Fifteen zeros are padded at each end ...` → `At each end of the convolution, 15 zeros are padded ...`。
> 闸负责把嫌疑摆上桌面，怎么改才既合规又不伤文体仍然是人的活。
> 详细披露与"能证明什么/不能证明什么"见 [`demo/real-case/README.md`](demo/real-case/README.md)。

## 核心组件

| 文件 | 作用 |
|---|---|
| `SKILL.md` | Agent 工作流：正译 → 回译（盲）→ 硬闸 → 语义比对 → 修正 → 交付 |
| `scripts/bt_probe.py` | **免费诊断**（只读）：规模、受保护元素统计、分批建议、风险清单（docx 公式丢失等） |
| `scripts/glossary.py` | 术语抽取（CJK n-gram + 原文自带「中文（English）」对照）+ 术语表自身校验 |
| `scripts/guard.py` | **确定性保真闸**（核心资产）：占位符 / 占位符顺序 / 公式逐字 / 数字 / 引用 / 段落覆盖 / 残留中文 / 术语一致性 / 长度异常 / 相邻重复，共 **10 项**（带 `--back` 再补 3 项回译检查，共 13 项） |
| `scripts/report.py` | 把 guard JSON 渲染成可转发的质检报告（Markdown + 单文件 HTML，含输入 sha256 与复现命令） |
| `scripts/license_check.py` | 许可钩子：纯 Python Ed25519（与 pdf-to-pptx-omml 共用同一套后端），当前全免费放行 |
| `references/pitfalls.md` | 30 条实战坑（本仓库最重要的复利资产） |
| `references/fidelity-rubric.md` | 语义四分类判定标准 + 迭代终止条件 |
| `references/structured-preservation.md` | 占位符规范：内联 / 整块两种约定 + docx/LaTeX 识别要点 |

## 快速开始

```bash
git clone git@github.com:GongfaChen/back-translate-refinement.git
cd back-translate-refinement
pip install -r requirements.txt        # python-docx 仅处理 .docx 时需要

python scripts/check_env.py                             # 环境闸（只读）
python scripts/bt_probe.py 你的原稿.md                   # 免费诊断
python scripts/glossary.py extract --source 你的原稿.md --out terms.csv   # 术语候选
# 按 SKILL.md Step 2–3 产出正译稿与回译稿（回译必须盲）后：
python scripts/guard.py --source 原稿.md --translation 译稿.md \
  --back 回译稿.md --glossary terms.csv --json out.json  # 确定性保真闸
python scripts/report.py out.json                        # 可转发质检报告
```

退出码：`0` PASS｜`1` WARN｜`2` FAIL——适合直接嵌进 CI 或批量流水线。

## 设计原则

1. **脚本判机械项，模型判语义**——分工写在 SKILL.md 里，两层都过才算交付。
2. **段号即锚点**——分段必须确定性；段数对不上，一切比对失效，guard 第一项就查它。
3. **回译必须盲**——模型若能"记住"原稿，损耗会被悄悄补上，比对失去意义。
4. **报告可复现**——输入 sha256 + 完整命令，同一输入必然得到同一结论。
5. **报告明确边界**——机械项全对 ≠ 语义没走样；报告第七节专讲"本报告不能证明什么"。

## 验证状态

- `bt_common` 自检：token 抽取顺序、公式内数字不重复计数、全角归一、分段确定性
- `license_check --self-test`：RFC 8032 官方向量 + 篡改/过期/越权/免费模式/小阶公钥拒绝
- `check_env`：Python 版本、依赖矩阵、6 模块 import、Ed25519 签名往返
- demo 端到端：7 段样稿（6 类植入缺陷）→ guard 报 9 error / 2 warn，逐条与植入缺陷一一对应 → report.py 产出 MD + HTML
- 真实案例复现：Paper-3 脱敏稿 14 块 → guard 10 项全 PASS；初稿→精修 18 个编辑点，数字 51 / 引用 10 / 公式编号 1 零漂移
- CI：GitHub Actions（Ubuntu × Python 3.12/3.13），上述各项均作为独立 step 跑

## 已知限制

- 语义一致性（缺失/添加/扭曲）无法由脚本判定——那是 SKILL.md Step 5 的工作，报告会明确声明这一点
- 作者-年份引用、科学计数法（1e-4）等非逐字等价形态，机械检查抓不住，靠术语表 + 人工
- 长度比阈值按**中译英**标定（`英文词/汉字`，默认带 0.35–1.10）；反向（英→中）或其它语对未系统测试，
  需要把 `--length-band` 换成反向区间（中文字符/英文词，约 1.2–2.8），或放宽成 `0,99` 先绕过该项
- `1e-4`、`v2.0` 这类含字母数字混合 token 的比较规则偏保守（宁可放过，不可误报）

## Roadmap

- [x] v0.1 开源核心：probe + 术语抽取 + 10 项确定性保真闸 + 可转发报告 + 30 条坑
- [ ] 批量文档模式（整本处理，断点续跑）
- [ ] docx 公式内容级校验（OMML → LaTeX 归一比较）
- [ ] Markdown 语法标记多重集检查（加粗/链接/代码块）
- [ ] 与 pdf-to-pptx-omml 联动：教材 PDF → 英文讲义 → 公式可编辑 PPT 全链路

## License

MIT（`assets/` 下截图为自产演示，无第三方版权内容）
