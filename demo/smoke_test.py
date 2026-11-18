"""端到端冒烟测试：用带已知缺陷的样稿，断言 guard 能全部抓到。

这个测试是「闸门有效性」的证明：如果哪天有人改坏了正则或对齐逻辑，
让某个缺陷漏网，这里会立刻红——而不是等真实用户丢数据。

缺陷清单（与 demo 样稿一一对应）：
  1. coverage  : 译稿缺第 7 段（段数 7→6）
  2. keep      : 第 6 段丢 <KEEP:table:1>
  3. math      : 第 4 段丢行间公式
  4. num       : 第 6 段 12 → 21
  5. residue   : 第 2 段残留「如图」
  6. glossary  : 第 5 段 注意力机制 → focus mechanism
  7. back-keep : 回译侧第 6 段占位符丢失
  8. back-math : 回译侧第 4 段公式丢失

用法：python demo/smoke_test.py [demo 目录]   （默认 demo）
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import bt_common as bc  # noqa: E402
import glossary as gl  # noqa: E402

PY = sys.executable


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], capture_output=True, text=True, encoding="utf-8")


def find(checks: list[dict], key: str) -> dict:
    return next(c for c in checks if c["key"] == key)


def expect_block(check: dict, block: int | None, fragment: str, label: str) -> None:
    hit = any(
        (item["block"] == block or block is None)
        and fragment in item["detail"]
        for item in check["items"]
    )
    assert hit, f"[smoke] {label} 未被捕获（期望 第{block}段 含「{fragment}」）\n实际：{check['items']}"


def main() -> int:
    demo = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "demo"
    print("=" * 60)
    print("back-translate-refinement · 端到端冒烟测试")
    print("=" * 60)

    # ---- [1] bt_common 自检 ----
    tok = bc.protected("见 $O(n^2)$ 与 <KEEP:figure:1>，共 5 项[2]。")
    assert tok["math"] == ["$O(n^2)$"] and tok["keep"] == [("figure", 1)]
    assert bc.protected("共５０％")["num"] == ["50%"]
    print("[1] bt_common token 抽取               PASS")

    # ---- [2] 术语抽取：候选里必须出现核心术语 ----
    text = bc.read_text(demo / "sample_zh.md")
    cands = gl.extract_candidates(text, min_count=2)
    assert "注意力机制" in cands, f"核心术语未被抽取：{list(cands)[:8]}"
    assert "自注意力" in cands
    print(f"[2] glossary 抽取（{len(cands)} 个候选，含注意力机制）PASS")

    # ---- [3] 术语表校验 ----
    rc = run(["scripts/glossary.py", "validate", "--glossary", str(demo / "glossary.csv")])
    assert rc.returncode == 0 and "校验通过" in rc.stdout, rc.stdout + rc.stderr
    print("[3] glossary validate                  PASS")

    # ---- [4] guard：六类缺陷全部捕获 ----
    out_json = demo / "guard_report.json"
    rc = run([
        "scripts/guard.py",
        "--source", str(demo / "sample_zh.md"),
        "--translation", str(demo / "sample_en.md"),
        "--back", str(demo / "sample_zh_bt.md"),
        "--glossary", str(demo / "glossary.csv"),
        "--json", str(out_json),
    ])
    assert rc.returncode == 2, f"guard 应判 FAIL(2)，实际 {rc.returncode}：{rc.stdout[-400:]}"
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert report["verdict"] == "FAIL"

    checks = report["checks"]
    cov = find(checks, "coverage")
    expect_block(cov, None, "段数不一致：原稿 7 段，译稿 6 段", "缺陷1 段数不一致")
    expect_block(cov, 7, "译稿缺少该段", "缺陷1 第7段缺失")

    keep = find(checks, "keep")
    expect_block(keep, 6, "<KEEP:table:1>", "缺陷2 表格占位符丢失")

    math = find(checks, "math")
    expect_block(math, 4, "$$L=-\\sum_{i=1}^{N} y_i \\log p_i$$", "缺陷3 行间公式丢失")

    num = find(checks, "num")
    expect_block(num, 6, "丢失：12", "缺陷4a 12 丢失")
    expect_block(num, 6, "多出：21", "缺陷4b 21 凭空出现")

    residue = find(checks, "residue")
    expect_block(residue, 2, "残留 2 个汉字", "缺陷5 译稿残留中文")

    term = find(checks, "glossary")
    expect_block(term, 5, "注意力机制", "缺陷6 术语漂移")

    back_keep = find(checks, "back-keep")
    expect_block(back_keep, 6, "<KEEP:table:1>", "缺陷7 回译占位符丢失")
    back_math = find(checks, "back-math")
    expect_block(back_math, 4, "$$L=-\\sum_{i=1}^{N} y_i \\log p_i$$", "缺陷8 回译公式丢失")

    print(f"[4] guard 六类缺陷全部捕获（error {report['counts']['error']} / warn {report['counts']['warn']}）PASS")

    # ---- [5] 报告生成 ----
    rc = run(["scripts/report.py", str(out_json)])
    assert rc.returncode == 0, rc.stdout + rc.stderr
    md = (demo / "guard_report.md").read_text(encoding="utf-8")
    html = (demo / "guard_report.html").read_text(encoding="utf-8")
    assert "结论：FAIL" in md and "六、可复现信息" in md
    assert "sha256" in md and html.startswith("<!DOCTYPE html>")
    print("[5] report.py MD + HTML（含 sha256 复现块）PASS")

    # ---- [6] 反向回归：干净稿应判 PASS ----
    # 直接写完整的「正确译稿 + 正确回译稿」，而不是在缺陷稿上打补丁——
    # 链式 replace 漏掉一处还原（如 KEEP 占位符）就会得到假阴性。
    clean_en = demo / "_clean_en.md"
    clean_en.write_text("\n\n".join([
        "This chapter discusses the role of the attention mechanism in large-scale language models. Compared with recurrent networks, self-attention can model dependencies over arbitrary distances within a constant path length, and its time complexity is $O(n^2)$[1].",
        "As <KEEP:figure:1> shows, the encoder is composed of 6 identical stacked layers, each of which contains two sublayers: self-attention and a <KEEP:math:1> feed-forward network.",
        "The experiments were conducted on 8 GPUs with a batch size of 4096 and a learning rate of 0.0001, training 12M parameters.",
        "The training objective is to minimize the cross-entropy loss, denoted as $$L=-\\sum_{i=1}^{N} y_i \\log p_i$$, where N is the number of samples.",
        "The attention mechanism can be written as <KEEP:math:2>, where Q, K, and V are the query, key, and value matrices[2,3].",
        "The comparison results are given in <KEEP:table:1>, with parameter counts increasing from 12M to 340M.",
        "The self-attention structure has clear advantages in modeling long-range dependencies, but it also brings quadratic complexity.",
    ]), encoding="utf-8")
    clean_bt = demo / "_clean_bt.md"
    clean_bt.write_text("\n\n".join([
        "本章讨论自注意力机制在大规模语言模型中的作用。与循环网络相比，自注意力能在常数路径长度内对任意距离的依赖建模，时间复杂度为 $O(n^2)$[1]。",
        "如图 <KEEP:figure:1> 所示，编码器由 6 个相同的堆叠层组成，每层包含自注意力与 <KEEP:math:1> 前馈网络两个子层。",
        "实验在 8 块 GPU 上进行，批量大小为 4096，学习率为 0.0001，训练了 12M 参数。",
        "训练目标是最小化交叉熵损失，记为 $$L=-\\sum_{i=1}^{N} y_i \\log p_i$$，其中 N 为样本数。",
        "注意力机制的计算可写为 <KEEP:math:2>，其中 Q、K、V 分别为查询、键、值矩阵[2,3]。",
        "表 <KEEP:table:1> 给出了模型的对比结果，参数量从 12M 增至 340M。",
        "综上，自注意力结构在长程依赖建模上具有明显优势，但也带来了二次复杂度。",
    ]), encoding="utf-8")
    rc = run([
        "scripts/guard.py",
        "--source", str(demo / "sample_zh.md"),
        "--translation", str(clean_en),
        "--back", str(clean_bt),
        "--glossary", str(demo / "glossary.csv"),
    ])
    assert rc.returncode == 0, f"干净稿应 PASS(0)，实际 {rc.returncode}：\n{rc.stdout[-800:]}"
    print("[6] 反向回归：干净稿 PASS              PASS")

    clean_bt.unlink(missing_ok=True)
    clean_en.unlink(missing_ok=True)

    print("-" * 60)
    print("smoke test: ALL PASS（闸门有效性 + 报告 + 反向回归）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
