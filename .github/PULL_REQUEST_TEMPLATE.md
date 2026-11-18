# Pull Request

## 改了什么

<!-- 一两句话 + 涉及的检查项/文档 -->

## 自查清单

- [ ] `python demo/smoke_test.py demo` 通过（含反向回归：干净稿必须 PASS）
- [ ] `python scripts/bt_common.py` 自检通过
- [ ] `python scripts/license_check.py --self-test` 通过
- [ ] 新增/修改检查项时：更新 `references/pitfalls.md`（说明拦的是哪条坑）
- [ ] 新增依赖时：更新 `requirements.txt` 并在 PR 里说明理由（本工具链刻意少依赖）
- [ ] **SKIP 不等于通过**：环境闸输出里的 SKIP 项需在 PR 里说明影响

## 对确定性检查的特别要求

- 新检查项必须**确定性**：同一输入在任何机器上得到同一结论（这是本仓库的设计原则 1）
- 报告输出同步更新 `references/report-spec.md`（新字段怎么读）
- 若检查为启发式（如长度比），必须在 report-spec.md 声明「越界 ≠ 错误」
