"""术语表工具：从原稿抽取候选术语、校验术语表自身质量。

为什么单独一个脚本：

回译精修最容易出的事故不是「译错」，而是「前后不一致」——
同一概念在第 3 段叫 attention mechanism、第 9 段叫 focus mechanism。
审稿人一眼就能看出来，但人眼在几十页里几乎抓不住。
所以术语必须**先固化再翻译**：先抽候选 → 人工确认译法 → 全篇按表执行 → guard.py 验一致性。

这里只做抽取与校验，一致性检查在 guard.py（单一职责，避免两套规则打架）。

用法：
    python scripts/glossary.py extract --source 原稿.md --out terms.csv [--min-count 2]
    python scripts/glossary.py validate --glossary terms.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bt_common as bc
from license_check import require_license_or_exit

# 这些字出现在 n-gram 里，几乎一定不是术语（虚词或代词起头）
STOP_CHARS = set("的了是和与把被对从而则即也都又很在是有为以之其将这那此各每某所该并或但而且及等就才还很更最")
CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")

# 显式给出的对照：中文（English） / 中文(English)
EXPLICIT_PAIR_RE = re.compile(r"([\u4e00-\u9fff]{2,12})\s*[（(]\s*([A-Za-z][A-Za-z0-9 \-]{1,60})\s*[)）]")


def extract_candidates(text: str, min_count: int, max_n: int = 6) -> Counter:
    """从原文抽 CJK n-gram 候选术语。

    只做统计筛选，不判断「是不是术语」——这一步交给术语表的人工确认列。
    脚本给的是**排序好的候选清单**，把「从零想术语」变成「从 30 个候选里勾选」。
    """
    plain = bc.strip_kee_math(text)
    plain = bc.CITE_RE.sub(" ", plain)
    counter: Counter = Counter()

    for run in CJK_RUN_RE.findall(plain):
        for n in range(2, max_n + 1):
            for i in range(len(run) - n + 1):
                gram = run[i : i + n]
                if gram[0] in STOP_CHARS or gram[-1] in STOP_CHARS:
                    continue
                if any(ch in STOP_CHARS for ch in gram):
                    continue
                counter[gram] += 1

    # 去掉被更长高频词完全包含的短词（如「注意力」包含在「注意力机制」里且频次相同）
    #
    # 阈值按词长分级：2 字词太容易撞上普通词组（模型/网络/依赖），要求更高频次；
    # 3 字以上才可能是完整术语，用基础阈值。不这么做，短篇文档里会漏出大量
    # 「本章讨论自注」这类跨词碎片，候选清单一长就没人看了。
    filtered: Counter = Counter()
    for gram, n in counter.items():
        threshold = min_count + 1 if len(gram) == 2 else min_count
        if n < threshold:
            continue
        contained = any(
            gram != other and gram in other and counter[other] >= n for other in counter
        )
        if contained:
            continue
        filtered[gram] = n
    return filtered


def explicit_pairs(text: str) -> dict[str, str]:
    """抽取原文里作者自己写的「中文（English）」对照，这是最可靠的术语来源。"""
    pairs: dict[str, str] = {}
    for zh, en in EXPLICIT_PAIR_RE.findall(text):
        pairs.setdefault(zh.strip(), en.strip())
    return pairs


def cmd_extract(args) -> int:
    texts = []
    for path in args.source:
        texts.append(bc.read_text(path))
    text = "\n\n".join(texts)

    candidates = extract_candidates(text, args.min_count, args.max_n)
    explicit = explicit_pairs(text)

    existing: dict[str, str] = {}
    if args.glossary and Path(args.glossary).exists():
        existing = {zh: en for zh, en in bc.load_glossary(args.glossary)}

    # 排序：显式对照优先 → 频次降序 → 长度降序（长的更可能是完整术语）
    rows = sorted(candidates.items(), key=lambda kv: (-kv[1], -len(kv[0])))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["# zh", "en", "count", "note"])
        for zh, en in explicit.items():
            writer.writerow([zh, en, candidates.get(zh, 0), "原文自带对照，已自动填入"])
        for zh, count in rows:
            if zh in explicit:
                continue
            writer.writerow([zh, existing.get(zh, ""), count, "已有译法" if zh in existing else ""])

    print(f"候选术语 {len(rows)} 个 + 原文自带对照 {len(explicit)} 个 → {out_path}")
    print(f"  （频次阈值 {args.min_count}；en 列为空的需要人工确认译法，确认后再跑 guard.py 验一致性）")
    for zh, count in rows[:10]:
        print(f"    {zh:<12} ×{count}")
    if len(rows) > 10:
        print(f"    … 另有 {len(rows) - 10} 个")
    return 0


def cmd_validate(args) -> int:
    """检查术语表自身的质量问题——表错了，后面的检查全是错的。"""
    path = Path(args.glossary)
    raw_lines = [
        ln for ln in path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    problems: list[str] = []

    seen: dict[str, str] = {}
    empty_en = 0
    for i, line in enumerate(raw_lines, 1):
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 2:
            problems.append(f"第 {i} 行字段不足（需 zh,en）：{line[:40]}")
            continue
        zh, en = parts[0], parts[1]
        if zh.lower() == "zh":  # 表头
            continue
        if not en:
            empty_en += 1
            continue
        if zh in seen and seen[zh] != en:
            problems.append(f"「{zh}」有两个不同译法：{seen[zh]} / {en}")
        seen[zh] = en

    pairs = bc.load_glossary(path)
    # 同一译法对应多个中文词 → 至少要有提示，英文里可能是同一个词但要确认
    en_to_zh: dict[str, list[str]] = {}
    for zh, en in pairs:
        en_to_zh.setdefault(en.lower(), []).append(zh)
    for en, zhs in en_to_zh.items():
        if len(zhs) > 1:
            problems.append(f"译法「{en}」被多个中文术语共用：{'、'.join(zhs)}（确认是否同一个概念）")

    print(f"术语表：{path}")
    print(f"  有效条目 {len(pairs)} 条｜待补译法 {empty_en} 条")
    if problems:
        print(f"  发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"    - {p}")
        return 1
    print("  校验通过：无重复冲突、无共用译法歧义")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="术语表抽取与校验")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ex = sub.add_parser("extract", help="从原稿抽取候选术语，生成待确认的 CSV")
    ex.add_argument("--source", nargs="+", required=True, help="原稿（可多个）")
    ex.add_argument("--out", required=True, help="输出 CSV 路径")
    ex.add_argument("--min-count", type=int, default=2, help="最低出现次数（默认 2）")
    ex.add_argument("--max-n", type=int, default=6, help="最长候选词字符数（默认 6）")
    ex.add_argument("--glossary", help="已有术语表：把已确认的译法带入输出")

    va = sub.add_parser("validate", help="校验术语表自身")
    va.add_argument("--glossary", required=True)

    args = ap.parse_args()
    require_license_or_exit("core")
    return cmd_extract(args) if args.cmd == "extract" else cmd_validate(args)


if __name__ == "__main__":
    sys.exit(main())
