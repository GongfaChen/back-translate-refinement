"""确定性保真闸：把「回译比对」里机器能判的部分全部自动化。

为什么需要这个脚本（而不是全靠 LLM 比对）：

LLM 擅长判断「这句话意思变了吗」，但有三件事它**不可靠**：
  1. 数数字——`12M 参数` 被译成 `21M`，人眼和模型都会漏；
  2. 数结构——`<KEEP:table:1>` 少了一个、公式少了一条，模型看不出来；
  3. 保一致——同一个术语在第 3 段叫 attention mechanism、第 9 段叫 focus mechanism。

这三类恰恰是审稿人和期刊编辑最先挑出来的硬错误，也恰好是脚本可以 100% 稳定判定的。
所以分工是：**脚本判机械项（闸），LLM 判语义项（SKILL.md 的 Step 5）**。

退出码：
  0  PASS（无 error、无 warn）
  1  WARN（只有警告，建议人工复核）
  2  FAIL（存在 error，必须修正后再交付）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bt_common as bc
from license_check import require_license_or_exit

TOOL_VERSION = "0.1.0"


def _file_sha256(path) -> str:
    """输入文件短哈希（12 位），随 JSON 落盘供 report.py 使用。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:12]
    except OSError:
        return "n/a"

EXIT_PASS, EXIT_WARN, EXIT_FAIL = 0, 1, 2


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------


@dataclass
class Item:
    block: int | None
    detail: str


@dataclass
class Check:
    key: str
    title: str
    level: str  # "error" | "warn"
    desc: str = ""
    items: list[Item] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.items

    def add(self, block: int | None, detail: str) -> None:
        self.items.append(Item(block, detail))

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "level": self.level,
            "desc": self.desc,
            "passed": self.passed,
            "count": len(self.items),
            "items": [{"block": i.block, "detail": i.detail} for i in self.items],
        }


# --------------------------------------------------------------------------
# 多重集比较
# --------------------------------------------------------------------------


def _fmt_token(tok) -> str:
    """把 token 显示成人能读的样子：KEEP 元组还原成 <KEEP:figure:1>。"""
    if isinstance(tok, tuple) and len(tok) == 2:
        return f"<KEEP:{tok[0]}:{tok[1]}>"
    return str(tok)


def _fmt(tokens: list) -> str:
    """把若干 token 拼成一句人能读的清单（最多 6 个）。"""
    shown = [_fmt_token(t) for t in tokens[:6]]
    more = f" 等 {len(tokens)} 项" if len(tokens) > 6 else ""
    return "、".join(shown) + more


def diff_tokens(src_tokens: list, tr_tokens: list) -> tuple[list, list]:
    """返回 (缺失, 多出)。缺失 = 原文有译稿没有；多出 = 译稿凭空出现。

    不做 str() 归一：KEEP 的 (type, id) 元组要留着类型，
    否则下游只能打出 ``('table', 1)`` 这种不可读的东西。
    """
    s, t = Counter(src_tokens), Counter(tr_tokens)
    missing: list = []
    extra: list = []
    for tok, n in (s - t).items():
        missing.extend([tok] * n)
    for tok, n in (t - s).items():
        extra.extend([tok] * n)
    return missing, extra


# --------------------------------------------------------------------------
# 各项检查
# --------------------------------------------------------------------------


def check_coverage(src: list[str], tr: list[str]) -> tuple[Check, list[tuple[int, str | None, str | None]]]:
    chk = Check("coverage", "段落覆盖", "error", "原稿与译稿的段数、段落边界必须一一对应（段号即对照锚点）")
    if len(src) != len(tr):
        chk.add(
            None,
            f"段数不一致：原稿 {len(src)} 段，译稿 {len(tr)} 段"
            f"（差 {abs(len(src) - len(tr))} 段）——先对齐段号再谈保真",
        )
    pairs = bc.align(src, tr)
    for idx, s, t in pairs:
        if s is not None and t is None:
            chk.add(idx, f"译稿缺少该段（原文 {bc.cjk_chars(s)} 字）")
        elif s is None and t is not None:
            chk.add(idx, f"译稿多出该段（{bc.en_words(t)} 词，原文无对应段）")
    return chk, pairs


def _token_check(
    key: str,
    title: str,
    desc: str,
    kind: str,
    pairs: list[tuple[int, str | None, str | None]],
    level: str = "error",
) -> Check:
    """通用 token 多重集检查（keep / math / cite / num 共用一套逻辑）。"""
    chk = Check(key, title, level, desc)
    for idx, s, t in pairs:
        if s is None or t is None:
            continue
        miss, extra = diff_tokens(bc.protected(s)[kind], bc.protected(t)[kind])
        if miss:
            chk.add(idx, f"丢失：{_fmt(miss)}")
        if extra:
            chk.add(idx, f"多出：{_fmt(extra)}")
    return chk


def check_keep_order(pairs: list[tuple[int, str | None, str | None]]) -> Check:
    """KEEP 占位符顺序必须单调递增——顺序错乱意味着结构化元素挪位了。

    多重集相等但顺序乱了，是「内容没丢、位置错了」这种最隐蔽的破坏：
    图 1 和表 1 的内容都还在，但换位置了。
    """
    chk = Check("keep-order", "占位符顺序", "error", "同一类型的 KEEP 编号在译稿中必须按原序出现")
    for idx, _s, t in pairs:
        if t is None:
            continue
        seq = bc.protected(t)["keep"]
        last: dict[str, int] = {}
        for kind, num in seq:
            if kind in last and num < last[kind]:
                chk.add(idx, f"<KEEP:{kind}:{num}> 出现在 <KEEP:{kind}:{last[kind]}> 之后，顺序错乱")
                break
            last[kind] = num
    return chk


def check_residue(pairs: list[tuple[int, str | None, str | None]]) -> Check:
    """译稿里不该有中文（除非该段本身就是中文引文）。

    这是最实用的漏译探测：译者跳过某段、或只译了一半，人眼在几百段里看不到，
    脚本一次就能揪出来。
    """
    chk = Check("residue", "译稿残留中文", "error", "英译稿段落中不应残留成片汉字（可能是漏译或只译了一半）")
    for idx, _s, t in pairs:
        if t is None:
            continue
        zh = bc.cjk_chars(bc.strip_kee_math(t))
        if zh >= 2:
            chk.add(idx, f"残留 {zh} 个汉字：{t[:40]}…")
    return chk


def check_glossary(
    pairs: list[tuple[int, str | None, str | None]],
    glossary: list[tuple[str, str]],
    strict: bool,
) -> Check:
    """术语一致性：原文出现的术语，译稿必须用规定的译法。

    只查「原文含术语 → 译稿必须含对应英文」，不反查「译稿含英文就必须有对应中文」——
    英文里合法地省略主语、代词化都是正常的，反查会大量假报。
    """
    level = "error" if strict else "warn"
    chk = Check(
        "glossary",
        "术语一致性",
        level,
        "原文出现的术语，译稿须使用术语表规定的译法（多个可接受译法用 ; 或 / 分隔）",
    )
    if not glossary:
        return chk

    for idx, s, t in pairs:
        if s is None or t is None:
            continue
        plain_src = bc.strip_kee_math(s)
        plain_tr = bc.strip_kee_math(t)
        low_tr = plain_tr.lower()
        for zh, en in glossary:
            if zh not in plain_src:
                continue
            variants = [v.lower() for v in bc.en_variants(en)]
            if not any(v in low_tr for v in variants):
                chk.add(idx, f"用了别的说法：原文「{zh}」应译为 {en}")
    return chk


def check_length(
    pairs: list[tuple[int, str | None, str | None]],
    band: tuple[float, float],
) -> Check:
    """长度比异常 = 漏译或扩写的嫌疑信号（只是嫌疑，需人工确认）。

    技术文本里 1 个汉字约对应 0.5–0.8 个英文词；偏出带外通常意味着
    某半句话被吞掉（偏低）或被解释性扩写（偏高）。
    """
    chk = Check(
        "length",
        "英译长度比",
        "warn",
        f"英文字数/中文字数 合理区间 {band[0]:.2f}–{band[1]:.2f}；越界多为漏译或扩写",
    )
    lo, hi = band
    for idx, s, t in pairs:
        if s is None or t is None:
            continue
        if bc.cjk_chars(bc.strip_kee_math(s)) < 4:  # 太短的段（标题、单句）不判
            continue
        ratio = bc.length_ratio(s, t)
        if ratio == 0.0:
            continue
        if ratio < lo:
            chk.add(idx, f"比值 {ratio:.2f} 偏低（{bc.cjk_chars(bc.strip_kee_math(s))} 字 → {bc.en_words(bc.strip_kee_math(t))} 词），疑漏译")
        elif ratio > hi:
            chk.add(idx, f"比值 {ratio:.2f} 偏高，疑扩写/解释性翻译")
    return chk


def check_back_length(
    pairs: list[tuple[int, str | None, str | None]],
    band: tuple[float, float],
) -> Check:
    """回译长度比（汉字/汉字）。

    回译是中文→中文，所以用汉字数比值：回译相对原稿明显偏短 = 语义在往返中被压缩，
    偏长 = 英文稿添加了原文没有的解释。这条和英译长度比不能共用一个公式。
    """
    chk = Check(
        "back-length",
        "回译长度比",
        "warn",
        f"回译汉字/原稿汉字 合理区间 {band[0]:.2f}–{band[1]:.2f}；越界说明语义在往返中被压缩或膨胀",
    )
    lo, hi = band
    for idx, s, b in pairs:
        if s is None or b is None:
            continue
        zh_s = bc.cjk_chars(bc.strip_kee_math(s))
        zh_b = bc.cjk_chars(bc.strip_kee_math(b))
        if zh_s < 8:  # 段太短时比值噪声大
            continue
        ratio = zh_b / zh_s
        if ratio < lo:
            chk.add(idx, f"回译偏短：{zh_b}/{zh_s} 字（{ratio:.2f}），疑语义被压缩或漏译")
        elif ratio > hi:
            chk.add(idx, f"回译偏长：{zh_b}/{zh_s} 字（{ratio:.2f}），疑英文稿添加了解释")
    return chk


def check_duplicate(blocks: list[str], label: str) -> Check:
    """相邻段落完全重复 = 复制粘贴事故。"""
    chk = Check("duplicate", f"{label}相邻重复段", "warn", "相邻段落内容完全相同，多为复制粘贴失误")
    for i in range(1, len(blocks)):
        if blocks[i] == blocks[i - 1]:
            chk.add(i + 1, f"与第 {i} 段完全相同")
    return chk


# --------------------------------------------------------------------------
# 汇总
# --------------------------------------------------------------------------


def build_report(
    src_path: str,
    tr_path: str,
    back_path: str | None,
    glossary_path: str | None,
    mode: str,
    band: tuple[float, float],
    strict_terms: bool,
) -> dict:
    src_text = bc.read_text(src_path)
    tr_text = bc.read_text(tr_path)
    src_blocks = bc.segment(src_text, mode)
    tr_blocks = bc.segment(tr_text, mode)

    glossary = bc.load_glossary(glossary_path) if glossary_path else []

    coverage, pairs = check_coverage(src_blocks, tr_blocks)

    checks: list[Check] = [
        coverage,
        _token_check("keep", "结构化占位符", "<KEEP:type:id> 必须一个不多一个不少（图/表/公式的位置锚点）", "keep", pairs),
        check_keep_order(pairs),
        _token_check("math", "公式保真", "行内与行间公式必须逐字保留（含上下标、希腊字母）", "math", pairs),
        _token_check("num", "数字保真", "数字与百分号必须一致（12M 写成 21M 就是硬错误）", "num", pairs),
        _token_check("cite", "引用保真", "文献引用标记 [1]、[2-3] 必须保留且数量一致", "cite", pairs),
        check_residue(pairs),
        check_glossary(pairs, glossary, strict_terms),
        check_length(pairs, band),
        check_duplicate(tr_blocks, "译稿"),
    ]

    # 回译（可选）：结构 token 必须能过一次往返而不丢
    back_stats = None
    if back_path:
        back_text = bc.read_text(back_path)
        back_blocks = bc.segment(back_text, mode)
        back_pairs = bc.align(src_blocks, back_blocks)  # (段号, 原稿, 回译)
        checks.append(
            _token_check("back-keep", "回译占位符", "占位符经一次往返后仍须完整（以原稿为基准）", "keep", back_pairs)
        )
        checks.append(
            _token_check("back-math", "回译公式", "公式经一次往返后仍须逐字保留（以原稿为基准）", "math", back_pairs)
        )
        checks.append(check_back_length(back_pairs, (0.65, 1.45)))
        back_stats = {
            "blocks": len(back_blocks),
            "cjk": bc.cjk_chars(back_text),
            "ratio_to_source": round(bc.cjk_chars(back_text) / max(bc.cjk_chars(src_text), 1), 3),
        }

    # 逐段状态：按 check 的 level 汇总到段，段内只要有 error 就是 error
    block_issues: dict[int, list[tuple[str, str]]] = {}
    for chk in checks:
        for item in chk.items:
            if item.block is not None:
                block_issues.setdefault(item.block, []).append((chk.level, f"[{chk.title}] {item.detail}"))

    blocks_out = []
    for idx, s, t in pairs:
        issues = block_issues.get(idx, [])
        if any(lvl == "error" for lvl, _ in issues):
            status = "error"
        elif issues:
            status = "warn"
        else:
            status = "ok"
        blocks_out.append(
            {
                "block": idx,
                "status": status,
                "issues": [text for _lvl, text in issues],
                "cjk": bc.cjk_chars(s or ""),
                "words": bc.en_words(t or ""),
                "ratio": round(bc.length_ratio(s or "", t or ""), 3) if (s and t) else None,
            }
        )

    errors = sum(len(c.items) for c in checks if c.level == "error")
    warns = sum(len(c.items) for c in checks if c.level == "warn")
    verdict = "FAIL" if errors else ("WARN" if warns else "PASS")

    return {
        "tool": "back-translate-refinement/guard",
        "version": TOOL_VERSION,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "mode": mode,
        # 路径按「调用时给的写法」记录（不 resolve 成绝对路径）：用相对路径调用时，
        # 报告里就只出现相对路径，既不会把作者本机目录结构带进公开仓库，
        # 也让同一份输入在任意机器上生成的报告逐字一致（golden 比对的前提）。
        "inputs": {
            "source": str(src_path),
            "translation": str(tr_path),
            "back_translation": str(back_path) if back_path else None,
            "glossary": str(glossary_path) if glossary_path else None,
            "glossary_terms": len(glossary),
            "length_band": list(band),
            "strict_terms": strict_terms,
        },
        # 输入文件哈希随 JSON 落盘，report.py 不必再依赖路径可读（换机器/移动 JSON 都不影响）。
        "input_sha256": {
            "source": _file_sha256(src_path),
            "translation": _file_sha256(tr_path),
            "back_translation": _file_sha256(back_path) if back_path else None,
            "glossary": _file_sha256(glossary_path) if glossary_path else None,
        },
        "stats": {
            "blocks_source": len(src_blocks),
            "blocks_translation": len(tr_blocks),
            "cjk_source": bc.cjk_chars(src_text),
            "en_words_translation": bc.en_words(tr_text),
            "overall_ratio": round(bc.length_ratio(src_text, tr_text), 3),
            "keep_tokens": len(bc.protected(src_text)["keep"]),
            "math_tokens": len(bc.protected(src_text)["math"]),
            "cite_tokens": len(bc.protected(src_text)["cite"]),
            "num_tokens": len(bc.protected(src_text)["num"]),
            "back": back_stats,
        },
        "verdict": verdict,
        "counts": {"error": errors, "warn": warns, "checks": len(checks)},
        "checks": [
            {**c.to_dict(), "level": c.level, "passed": c.passed} for c in checks
        ],
        "blocks": blocks_out,
    }


def render_console(report: dict) -> str:
    lines: list[str] = []
    st = report["stats"]
    lines.append("=" * 62)
    lines.append("回译精修 · 确定性保真闸")
    lines.append("=" * 62)
    lines.append(
        f"原稿 {st['blocks_source']} 段 / {st['cjk_source']} 汉字｜译稿 "
        f"{st['blocks_translation']} 段 / {st['en_words_translation']} 词｜整体比值 {st['overall_ratio']}"
    )
    lines.append(
        f"受保护项：占位符 {st['keep_tokens']}｜公式 {st['math_tokens']}｜引用 "
        f"{st['cite_tokens']}｜数字 {st['num_tokens']}"
    )
    if st.get("back"):
        b = st["back"]
        lines.append(f"回译：{b['blocks']} 段 / {b['cjk']} 汉字（相对原稿 {b['ratio_to_source']}）")
    lines.append("")

    for chk in report["checks"]:
        mark = "PASS" if chk["passed"] else ("FAIL" if chk["level"] == "error" else "WARN")
        lines.append(f"[{mark}] {chk['title']}")
        if not chk["passed"]:
            for item in chk["items"][:12]:
                # 定位信息统一由渲染层加，detail 里不再重复段号
                loc = f"第 {item['block']} 段：" if item["block"] else ""
                lines.append(f"    - {loc}{item['detail']}")
            if chk["count"] > 12:
                lines.append(f"    … 另有 {chk['count'] - 12} 条，见 JSON / 报告")
    lines.append("")
    c = report["counts"]
    lines.append(f"结论：{report['verdict']}（error {c['error']} / warn {c['warn']} / 检查项 {c['checks']}）")
    if report["verdict"] == "FAIL":
        lines.append("→ 存在硬错误，必须修正后重跑；error 项不修，报告不可作为交付凭证。")
    elif report["verdict"] == "WARN":
        lines.append("→ 无硬错误，但有可疑项，建议人工复核后再交付。")
    else:
        lines.append("→ 机械项全部通过。语义一致性仍需按 SKILL.md Step 5 人工/模型比对。")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="回译精修确定性保真闸：占位符/公式/数字/引用/覆盖率/术语/长度/漏译",
        epilog="退出码：0=PASS 1=WARN 2=FAIL",
    )
    ap.add_argument("--source", required=True, help="原稿（中文，.md/.txt/.docx）")
    ap.add_argument("--translation", required=True, help="英译稿")
    ap.add_argument("--back", help="回译稿（中文，可选但强烈建议）")
    ap.add_argument("--glossary", help="术语表 CSV（zh,en[,note]）")
    ap.add_argument(
        "--segment-mode",
        default="auto",
        choices=["auto", "blank-line", "line"],
        help="分段方式（默认 auto：有空行按空行，否则按行）",
    )
    ap.add_argument("--length-band", default="0.35,1.10", help="英译长度比合理区间，默认 0.35,1.10")
    ap.add_argument("--strict-terms", action="store_true", help="把术语不一致从 warn 升级为 error")
    ap.add_argument("--json", dest="json_out", help="输出机器可读 JSON（供 report.py 使用）")
    args = ap.parse_args()

    require_license_or_exit("core")

    try:
        lo, hi = (float(x) for x in args.length_band.split(","))
    except ValueError:
        print("error：--length-band 需形如 0.35,1.10", file=sys.stderr)
        return 4

    try:
        report = build_report(
            args.source,
            args.translation,
            args.back,
            args.glossary,
            args.segment_mode,
            (lo, hi),
            args.strict_terms,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error：{exc}", file=sys.stderr)
        return 4

    print(render_console(report))

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 已写入：{out}")

    return {"PASS": EXIT_PASS, "WARN": EXIT_WARN, "FAIL": EXIT_FAIL}[report["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
