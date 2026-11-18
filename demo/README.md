# demo：带已知缺陷的样稿

一组 7 段的中英对照样稿 + 回译稿 + 术语表，**故意植入 8 处缺陷**（覆盖 guard 的全部核心检查项）。

## 运行

```bash
python demo/smoke_test.py demo      # 端到端冒烟：断言全部缺陷被捕获 + 干净稿 PASS
```

| 文件 | 内容 |
|---|---|
| `sample_zh.md` | 中文原稿（7 段，自注意力主题，含公式/占位符/引用/数字） |
| `sample_en.md` | 英译稿（**植入缺陷**：缺第 7 段、丢表格占位、丢公式、12M→21M、残留「如图」、attention→focus） |
| `sample_zh_bt.md` | 回译稿（对应缺陷稿） |
| `glossary.csv` | 术语表（4 条，含「多个可接受译法」示例） |
| `smoke_test.py` | 端到端断言：[1] token 抽取 [2] 术语抽取 [3] 术语表校验 [4] 六类缺陷全捕获 [5] 报告生成 [6] **反向回归**（正确稿必须 PASS） |

缺陷清单见 `smoke_test.py` 文件头注释。运行后生成的 `guard_report.json/.md/.html` 已被 `.gitignore` 排除。

## real-case：真实稿件（不是植入缺陷）

`real-case/` 是另一类材料：一篇投稿论文的中译英稿，脱敏后放出**正译初稿**与**精修稿**两版对照，
用来回答"这套流程在真稿上到底改了什么、有没有改坏"。

```bash
python demo/real-case/run_real_case.py     # 保真闸 + 增量校验 + 变更分类
```

结论与边界见 [`real-case/README.md`](real-case/README.md)。
