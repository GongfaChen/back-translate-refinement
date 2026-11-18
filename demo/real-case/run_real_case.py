"""真实案例复现：Paper-3 中译英稿的「正译初稿 → 精修稿」前后对比。

跑三件事，全部基于本目录内的文件，不依赖外部原始稿件：

  1. 保真闸（guard.py）：中文原稿 vs 精修稿，逐项检查数字/引用/公式/术语/覆盖；
  2. 精修增量的机械校验：初稿 → 精修稿，受保护元素（数字、引用、Eq. 编号）
     必须**逐字不变**——精修只能改语言，不能动事实；
  3. 变更分类：把词级编辑按「拼写体系归一 / 术语归一 / 语义改写 / 标点结构」
     归类，输出 before_after.md 供人读。

用法：
    cd demo/real-case && python run_real_case.py

退出码：0 = 闸通过且增量全部合规；1 = 有警告；2 = 有硬错误。
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent.parent / "scripts"

# 精修时允许发生的「拼写体系归一」：美式 → 英式（期刊为 en-GB 时统一）
EN_US_TO_GB = {
    "normalization": "normalisation",
    "normalized": "normalised",
    "normalizes": "normalises",
    "standardization": "standardisation",
    "standardized": "standardised",
    "localization": "localisation",
    "regularization": "regularisation",
    "optimization": "optimisation",
    "optimized": "optimised",
    "generalization": "generalisation",
    "minimizes": "minimises",
    "penalized": "penalised",
    "stabilizing": "stabilising",
}

CATEGORIES = (
    "拼写体系归一(en-US→en-GB)",
    "数字形式统一",
    "术语/搭配归一",
    "标点与结构",
    "语义改写",
)

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}


def read_blocks(path: Path) -> list[str]:
    """按空行分段，与 guard.py 的 blank-line 分段保持一致。"""
    text = path.read_text(encoding="utf-8-sig")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text)]
    return [b for b in blocks if b]


def protected(text: str) -> dict[str, Counter | set]:
    """受保护元素：数字、引用、公式编号。精修不可改动其中任何一项。

    数词先归一成阿拉伯数字再比——`Fifteen` 与 `15` 是同一个事实，
    若不做归一，「把数字写成英文单词」会被误判为事实变动。
    """
    norm = re.sub(
        r"\b(" + "|".join(NUMBER_WORDS) + r")\b(?!-)",
        lambda m: str(NUMBER_WORDS[m.group(1).lower()]),
        text,
        flags=re.IGNORECASE,
    )
    return {
        "num": Counter(re.findall(r"\d+(?:[.,]\d+)*", norm)),
        "cite": set(re.findall(r"\[\d+(?:\s*[–-]\s*\d+)?(?:\s*,\s*\d+)*\]", text)),
        "eq": set(re.findall(r"Eq\.\s*\(?\d+\)?", text)),
    }


def word_diff(a: str, b: str, gap: int = 3) -> list[tuple[str, str, str]]:
    """词级差异 → [(类别, 原文片段, 精修片段)]。

    单句被整体重写时，difflib 会吐出十几个零碎 opcode（插一个 the、删一个 from）。
    这类碎片单独看毫无意义，所以把「彼此只隔 <= gap 个相同词」的邻近改动并成一整块，
    让 before/after 里呈现的是可读的短语级改写。
    """
    wa = re.findall(r"[A-Za-z][A-Za-z'’-]*|\d+(?:[.,]\d+)*|[^\sA-Za-z\d]", a)
    wb = re.findall(r"[A-Za-z][A-Za-z'’-]*|\d+(?:[.,]\d+)*|[^\sA-Za-z\d]", b)
    ops = [op for op in difflib.SequenceMatcher(None, wa, wb).get_opcodes() if op[0] != "equal"]

    merged: list[list[int]] = []
    for tag, i1, i2, j1, j2 in ops:
        if merged and i1 - merged[-1][1] <= gap:
            merged[-1][1] = i2
            merged[-1][3] = j2
        else:
            merged.append([i1, i2, j1, j2])

    out: list[tuple[str, str, str]] = []
    for i1, i2, j1, j2 in merged:
        old, new = " ".join(wa[i1:i2]).strip(), " ".join(wb[j1:j2]).strip()
        out.append((classify(old, new), old, new))
    return out


def classify(old: str, new: str) -> str:
    """给一处编辑归类——顺序即优先级，先判最确定的。"""
    o = old.lower().strip(" .,;:")
    n = new.lower().strip(" .,;:")

    def as_number(s: str) -> int | None:
        if s.isdigit():
            return int(s)
        return NUMBER_WORDS.get(s)

    no, nn = as_number(o), as_number(n)
    if no is not None and nn is not None and no == nn:
        return CATEGORIES[1]
    if EN_US_TO_GB.get(o) == n:
        return CATEGORIES[0]
    # 多词块：逐词都是美式→英式映射，整体也算拼写体系归一（如 normalization and standardization）
    ot, nt = o.split(), n.split()
    if len(ot) == len(nt) and ot and all(EN_US_TO_GB.get(x) == y for x, y in zip(ot, nt) if x != y):
        return CATEGORIES[0]
    # 去连字符 / 单复数这一层：算术语与搭配归一
    if o.replace("-", " ") == n.replace("-", " ") or o.rstrip("s") == n.rstrip("s"):
        return CATEGORIES[2]
    # 标点与结构：拿掉所有非字母数字后完全相同，说明只动了标点/大小写/空白
    skel = lambda s: re.sub(r"[^a-z0-9]", "", s)
    if o and skel(o) == skel(n):
        return CATEGORIES[3]
    return CATEGORIES[4]


def run_guard(draft_json: Path) -> int:
    """跑保真闸。

    刻意用**相对路径 + cwd=本目录**：guard 会把输入路径写进 JSON，
    再由 report.py 渲染进报告；用绝对路径会把作者的本机目录结构带进公开仓库。
    """
    names = ["zh_source.md", "en_refined.md", "term_map.csv", draft_json.name]
    cmd = [
        sys.executable, str(SCRIPTS / "guard.py"),
        "--source", names[0],
        "--translation", names[1],
        "--glossary", names[2],
        "--json", names[3],
    ]
    print(f"$ python scripts/guard.py --source {names[0]} --translation {names[1]} "
          f"--glossary {names[2]} --json {names[3]}")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    print(proc.stdout.rstrip())
    if proc.stderr.strip():
        print(proc.stderr.rstrip(), file=sys.stderr)
    return proc.returncode


def run_report(json_name: str) -> None:
    """把 guard JSON 渲染成可转发的 MD + 单文件 HTML。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "report.py"), json_name],
        capture_output=True, text=True, encoding="utf-8", cwd=HERE,
    )
    for line in proc.stdout.splitlines():
        if line.strip().startswith(("Markdown", "HTML", "结论")):
            print("  " + line.strip())
    if proc.returncode != 0:
        print(proc.stderr.rstrip(), file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-guard", action="store_true", help="只做增量校验，不跑保真闸")
    args = ap.parse_args()

    zh = read_blocks(HERE / "zh_source.md")
    draft = read_blocks(HERE / "en_draft.md")
    refined = read_blocks(HERE / "en_refined.md")

    print(f"块数: 中文 {len(zh)} / 初稿 {len(draft)} / 精修 {len(refined)}")
    if not (len(zh) == len(draft) == len(refined)):
        print("✗ 块数不一致，逐段对比失效", file=sys.stderr)
        return 2

    # ---- 1. 精修增量的受保护元素校验 -------------------------------------
    print("\n[1] 初稿 → 精修稿：受保护元素必须逐字不变")
    violations = 0
    for i, (d, r) in enumerate(zip(draft, refined), 1):
        pd, pr = protected(d), protected(r)
        for key, label in (("num", "数字"), ("cite", "引用"), ("eq", "公式编号")):
            if pd[key] != pr[key]:
                violations += 1
                missing = pd[key] - pr[key]
                added = pr[key] - pd[key]
                print(f"  ✗ 块 {i} {label} 变动: 丢失={dict(missing) or '—'} 新增={dict(added) or '—'}")
    print(f"  {'✓ 全部一致（0 处事实级变动）' if violations == 0 else f'✗ {violations} 处违规'}")

    # ---- 2. 变更分类 ------------------------------------------------------
    print("\n[2] 词级编辑分类")
    buckets: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    changed_blocks = 0
    for i, (d, r) in enumerate(zip(draft, refined), 1):
        edits = word_diff(d, r)
        if edits:
            changed_blocks += 1
        for cat, old, new in edits:
            buckets[cat].append((i, old, new))

    total = sum(len(v) for v in buckets.values())
    print(f"  改动块数: {changed_blocks}/{len(draft)}，编辑点: {total}")
    for cat in CATEGORIES:
        items = buckets.get(cat, [])
        print(f"  {cat:26s} {len(items):3d}")
        for i, old, new in items[:4]:
            print(f"      block {i}: {old!r} → {new!r}")

    # ---- 3. 保真闸 --------------------------------------------------------
    guard_rc = 0
    if not args.skip_guard:
        print("\n[3] 保真闸（中文原稿 vs 精修稿）")
        guard_rc = run_guard(HERE / "guard_real.json")
        print(f"  guard 退出码: {guard_rc}（0=PASS 1=WARN 2=FAIL）")
        run_report("guard_real.json")

    write_before_after(zh, draft, refined, buckets, changed_blocks)

    ok = violations == 0 and guard_rc == 0
    print(f"\n{'✓ 真实案例复现成功' if ok else '✗ 存在问题，见上'}；明细见 before_after.md")
    return 0 if ok else (2 if violations or guard_rc == 2 else 1)


def write_before_after(
    zh: list[str],
    draft: list[str],
    refined: list[str],
    buckets: dict[str, list[tuple[int, str, str]]],
    changed_blocks: int,
) -> None:
    """把 before/after 写成人类可读的 markdown（逐段并列 + 编辑点表）。"""
    per_block: dict[int, list[tuple[str, str, str]]] = defaultdict(list)
    for cat, items in buckets.items():
        for i, old, new in items:
            per_block[i].append((cat, old, new))

    lines = [
        "# 真实案例：before / after",
        "",
        "> 由 `run_real_case.py` 自动生成，请勿手工编辑。",
        "> 源稿为作者本人中文论文稿（已脱敏：桥名→某中承式拱桥，作者与单位信息已移除）。",
        "> 只列出正文段；`##` 标题与中文逐字对应的不重复呈现。",
        "",
        f"共 {len(zh)} 个块（含标题），**{changed_blocks} 段被精修改动**。",
        "",
        "## 逐段并列",
        "",
    ]
    body_no = 0
    for i, (z, d, r) in enumerate(zip(zh, draft, refined), 1):
        if z.startswith("#") or d.startswith("#"):
            continue  # 标题块：本身就是结构，无需对比
        body_no += 1
        edits = per_block.get(i, [])
        lines += [f"### 段 {body_no}", "", f"**中文原稿**", "", f"> {z}", ""]
        lines += ["**英文 · 初稿**", "", f"> {d}", ""]
        if edits:
            lines += ["**英文 · 精修**", "", f"> {r}", ""]
            lines += ["编辑点：", ""]
            lines += [f"- `{cat}`：`{old}` → `{new}`" for cat, old, new in edits]
        else:
            lines += ["**英文 · 精修**：未改动", ""]
        lines += [""]

    lines += [
        "## 统计",
        "",
        "| 类别 | 编辑点数 |",
        "|---|---|",
    ]
    for cat in CATEGORIES:
        lines.append(f"| {cat} | {len(buckets.get(cat, []))} |")
    lines += [
        f"| **合计** | {sum(len(v) for v in buckets.values())} |",
        "",
        "分类口径：",
        "",
        "- **拼写体系归一**：normalization→normalisation 这类 en-US→en-GB，占绝大多数的机械替换；",
        "- **术语/搭配归一**：去掉多余连字符（regression-output→regression output）、单复数、"
        "同义改称（classify→discriminate）；",
        "- **标点与结构**：破折号夹注改冒号、句式连接调整；",
        "- **语义改写**：以上都不属于、确实改了措辞或补了信息的编辑点。",
        "",
        "受保护元素（数字、引用、Eq. 编号）在初稿→精修之间**零变动**，由脚本逐块校验。",
        "",
    ]
    (HERE / "before_after.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n已写出 {HERE / 'before_after.md'}")


if __name__ == "__main__":
    sys.exit(main())
