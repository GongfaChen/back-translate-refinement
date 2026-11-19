"""免费诊断：动手翻之前先告诉你「这稿能不能做、风险在哪、要分几批」。

对标 pdf-to-pptx-omml 的 probe：把「付费/返工」拦在动手之前。
只读，不改任何文件，不需要 API Key。

用法：
    python scripts/bt_probe.py 原稿.md [--translation 译稿.md] [--glossary terms.csv] [--report out.md]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bt_common as bc
from license_check import require_license_or_exit

# 不含表头的一行 = 1 条术语；粗略估算，不追求精确
BATCH_CJK = 1500  # 单批建议汉字上限（超过就分批判正译/回译）
LONG_BLOCK_CJK = 800  # 单段超过这个字数，建议手工再切


def analyze(path: str, mode: str) -> dict:
    text = bc.read_text(path)
    blocks = bc.segment(text, mode)
    tokens = bc.protected(text)
    docx = bc.docx_stats(path)

    # 占比一律在「去掉受保护 token 的正文」上算：
    # 否则一段纯中文只要含 $O(n^2)$ 和一个 <KEEP:...> 就会被判成中英混排。
    plain_blocks = [bc.strip_kee_math(b) for b in blocks]
    ratios = [bc.cjk_ratio(b) for b in plain_blocks if b.strip()]
    plain_text = bc.strip_kee_math(text)

    return {
        "path": str(Path(path).resolve()),
        "suffix": Path(path).suffix.lower(),
        "text": text,
        "blocks": blocks,
        "tokens": tokens,
        "docx": docx,
        "cjk": bc.cjk_chars(text),
        "en_words": bc.en_words(text),
        "cjk_ratio": round(bc.cjk_ratio(plain_text), 3),
        "block_cjk_max": max((bc.cjk_chars(b) for b in blocks), default=0),
        "mixed_blocks": sum(1 for r in ratios if 0.15 < r < 0.75),
    }


def risks(src: dict) -> list[tuple[str, str]]:
    """返回 [(级别, 说明)]，级别 ∈ {高, 中, 低}。"""
    out: list[tuple[str, str]] = []
    tok = src["tokens"]

    if tok["math"] and not tok["keep"]:
        out.append(("高", f"含 {len(tok['math'])} 处公式但**没有任何 KEEP 占位符**——正译时必须逐处加 <KEEP:math:N>，否则公式会在往返中丢失"))
    if tok["cite"] and not tok["keep"]:
        out.append(("中", f"含 {len(tok['cite'])} 处文献引用，建议用 <KEEP:cite:N> 占位，避免译稿把 [1] 改写成 (1) 或直接删掉"))
    if src["docx"]["equations"] and not tok["math"]:
        out.append(("高", f"docx 内有 {src['docx']['equations']} 个公式对象（OMML），但文本层抽不到——转成纯文本会**直接丢公式**，建议保留原 docx 并逐处占位"))
    if src["docx"]["tables"] and not any(k == "table" for k, _ in tok["keep"]):
        out.append(("中", f"docx 有 {src['docx']['tables']} 个表格，未见 <KEEP:table:N>：整表不翻译，须占位保留"))
    if src["docx"]["images"] and not any(k == "figure" for k, _ in tok["keep"]):
        out.append(("中", f"docx 有 {src['docx']['images']} 张图片，未见 <KEEP:figure:N>：图片与 caption 都须占位保留"))

    if src["cjk_ratio"] < 0.5:
        out.append(("中", f"汉字占比仅 {src['cjk_ratio']:.0%}，原稿可能是中英混排——先确认语义基准是中文，否则回译比对会失真"))
    if src["mixed_blocks"]:
        out.append(("低", f"{src['mixed_blocks']} 段为中英混排（汉字占比 15%–75%），这些段建议单独标注"))

    if len(src["blocks"]) > 60:
        batches = -(-len(src["blocks"]) // 30)
        out.append(("中", f"{len(src['blocks'])} 段偏多，建议按 30 段一批分批处理（预计 {batches} 批），否则上下文截断会导致段号错位"))
    if src["block_cjk_max"] > LONG_BLOCK_CJK:
        out.append(("中", f"最长一段 {src['block_cjk_max']} 字，超过 {LONG_BLOCK_CJK}——单段过长会削弱回译的定位能力，建议先按小节拆分"))

    if not out:
        out.append(("低", "未发现结构性风险：分段清晰、受保护元素已占位或不需要占位"))
    return out


def render(src: dict, rs: list[tuple[str, str]], glossary_n: int, tr: dict | None, mode: str) -> str:
    tok = src["tokens"]
    lines: list[str] = []
    lines.append("# 回译精修 · 可做性诊断")
    lines.append("")
    lines.append(f"- 文件：`{src['path']}`")
    lines.append(f"- 规模：**{len(src['blocks'])} 段**｜{src['cjk']} 汉字｜英文词 {src['en_words']}｜汉字占比 {src['cjk_ratio']:.0%}")
    lines.append(
        f"- 受保护元素：占位符 {len(tok['keep'])}｜公式 {len(tok['math'])}｜引用 {len(tok['cite'])}｜数字 {len(tok['num'])}"
    )
    if src["docx"]["paragraphs"]:
        d = src["docx"]
        lines.append(f"- docx 结构：段落 {d['paragraphs']}｜表格 {d['tables']}｜公式对象 {d['equations']}｜图片 {d['images']}")
    lines.append(f"- 分段方式：{mode}" + ("（自动判定）" if mode == "auto" else ""))
    lines.append("")

    # 分批
    batches = max(1, -(-src["cjk"] // BATCH_CJK))
    lines.append("## 处理规模建议")
    lines.append("")
    lines.append(f"- 正译/回译建议分 **{batches}** 批（每批 ≤ {BATCH_CJK} 汉字），逐批跑 guard 再合并")
    lines.append(f"- 迭代上限建议 **3–5 轮**；同一段连续两轮无改进即停（见 SKILL.md Step 5）")
    lines.append(f"- 术语：{'已提供 ' + str(glossary_n) + ' 条' if glossary_n else '**未提供**——建议先跑 glossary.py extract 固化成表，否则前后不一致无从检查'}")
    lines.append("")

    lines.append("## 风险清单")
    lines.append("")
    for level, msg in rs:
        lines.append(f"- **[{level}]** {msg}")
    lines.append("")

    lines.append("## 下一步")
    lines.append("")
    if tr is None:
        lines.append("1. 按 SKILL.md Step 1–2 产出「正译稿」与「回译稿」；")
        lines.append("2. 跑 `python scripts/guard.py --source 原稿 --translation 译稿 --back 回译 --glossary 术语表 --json out.json`；")
        lines.append("3. 按报告里的 error 项逐条修，修完重跑，直到 PASS/WARN；")
        lines.append("4. `python scripts/report.py out.json` 生成可转发的质检报告。")
    else:
        overlap = min(len(src["blocks"]), len(tr["blocks"]))
        lines.append(f"1. 已提供译稿：原稿 {len(src['blocks'])} 段 / 译稿 {len(tr['blocks'])} 段，可直接对齐 {overlap} 段；")
        lines.append("2. 直接跑 `python scripts/guard.py --source 原稿 --translation 译稿 [--back 回译] --json out.json`；")
        lines.append("3. 若段数不一致，先修段边界再来谈保真（段号是全部比对的锚点）。")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="回译精修可做性诊断（免费、只读）")
    ap.add_argument("source", help="原稿（中文，.md/.txt/.docx）")
    ap.add_argument("--translation", help="英译稿（可选：给了就直接评估对齐情况）")
    ap.add_argument("--glossary", help="术语表 CSV（可选：评估术语覆盖）")
    ap.add_argument("--segment-mode", default="auto", choices=["auto", "blank-line", "line"])
    ap.add_argument("--report", help="把诊断写入 Markdown 文件（默认只打印）")
    args = ap.parse_args()

    require_license_or_exit("probe")  # probe 永远免费

    try:
        src = analyze(args.source, args.segment_mode)
        tr = analyze(args.translation, args.segment_mode) if args.translation else None
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error：{exc}", file=sys.stderr)
        return 2

    glossary_n = len(bc.load_glossary(args.glossary)) if args.glossary else 0
    text = render(src, risks(src), glossary_n, tr, args.segment_mode)

    print(text)
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"\n诊断已写入：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
