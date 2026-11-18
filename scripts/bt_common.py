"""共享工具：段落切分、受保护 token 抽取、文本统计、文件读入。

设计约束（决定了这些函数长什么样）：

1. **分段必须确定性**——同一份文件在任何机器、任何次运行都切出完全相同的段。
   否则「逐段对齐」「报告可复现」「差异可定位到段号」全部失效。
2. **受保护 token 用正则抽，不用 LLM**——只有确定性检查才配叫「闸」。
   LLM 的语义判断留给 SKILL.md 的比对环节，脚本只负责「机械可判」的部分。
3. **抽取顺序敏感**：先 KEEP 占位符 → 再行间公式 → 再行内公式 → 再引用 → 最后数字。
   每抽一类就把该区间掩成空格，避免数字在公式里被重复计数
   （`$O(n^2)$` 里的 `2` 不该再进数字清单，否则公式和数字两处都会误报）。
"""

from __future__ import annotations

import re
from pathlib import Path

# --------------------------------------------------------------------------
# 正则：顺序敏感，勿随意重排
# --------------------------------------------------------------------------

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
EN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\u2019\-]*")

KEEP_RE = re.compile(r"<KEEP:([A-Za-z]+):(\d+)>")

# 行间公式必须在行内之前抽，否则 $$...$$ 会被行内规则吃掉
DISPLAY_MATH_RE = re.compile(
    r"\$\$[\s\S]+?\$\$"
    r"|\\\[[\s\S]+?\\\]"
    r"|\\begin\{(equation|align|eqnarray|cases|gather)\*?\}[\s\S]+?\\end\{\1\*?\}"
)
INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)[^$\n]+?\$|\\\([\s\S]+?\\\)")

CITE_RE = re.compile(r"\[\s*\d+(?:\s*[-\u2013,\uff0c]\s*\d+)*\s*\]")

# 前后不允许紧贴字母数字/下划线/点，避免把 v2、第3.5节 里的碎片切成怪数
NUM_RE = re.compile(r"(?<![A-Za-z0-9_.])[-+]?\d+(?:[.,]\d+)*%?")

FULLWIDTH_MAP = str.maketrans(
    "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19\uff0e\uff05\uff0b\uff0d",
    "0123456789.%+-",
)

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".tex", ".rst"}
DOCX_SUFFIXES = {".docx"}


# --------------------------------------------------------------------------
# 读入
# --------------------------------------------------------------------------


def read_text(path: str | Path) -> str:
    """读入 .md/.txt/.tex/.docx。

    docx 走 python-docx 只取段落文本（表格单元格也拼进来），
    公式的 OMML 不进文本（由 docx_stats 单独计数）。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到文件：{p}")

    suffix = p.suffix.lower()
    if suffix in DOCX_SUFFIXES:
        return _read_docx(p)
    if suffix in TEXT_SUFFIXES or suffix == "":
        # utf-8-sig：Windows 记事本 / Excel 导出的文件常带 BOM，
        # 不剥掉会让首行「# 注释」失效、首段还多出一个不可见字符
        return p.read_text(encoding="utf-8-sig", errors="replace")
    raise ValueError(f"不支持的文件类型：{suffix}（支持 {sorted(TEXT_SUFFIXES | DOCX_SUFFIXES)}）")


def _read_docx(p: Path) -> str:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover - 依赖缺失时给出可执行指引
        raise RuntimeError("读取 .docx 需要 python-docx：pip install python-docx") from exc

    document = docx.Document(str(p))
    blocks: list[str] = []
    for para in document.paragraphs:
        text = para.text.strip()
        if text:
            blocks.append(text)
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                blocks.append(" | ".join(cells))
    return "\n\n".join(blocks)


def docx_stats(path: str | Path) -> dict:
    """docx 的结构统计：段落数、表格数、OMML 公式数、图片数。

    公式数与公式对象是关键——回译精修最容易的事故就是
    「英文换完了，公式变成图片或干脆丢了」。
    """
    p = Path(path)
    stats = {"paragraphs": 0, "tables": 0, "equations": 0, "images": 0}
    if p.suffix.lower() not in DOCX_SUFFIXES:
        return stats
    try:
        import docx
    except ImportError:  # pragma: no cover
        return stats

    document = docx.Document(str(p))
    stats["paragraphs"] = len([x for x in document.paragraphs if x.text.strip()])
    stats["tables"] = len(document.tables)
    xml = document.element.xml
    # m:oMath = 行内/行间公式对象；m:oMathPara = 行间公式段落容器
    stats["equations"] = xml.count("<m:oMath") + xml.count(":oMathPara")
    stats["images"] = xml.count("<pic:pic")
    return stats


# --------------------------------------------------------------------------
# 分段
# --------------------------------------------------------------------------


def segment(text: str, mode: str = "auto") -> list[str]:
    """把文本切成段。

    auto：有空行 → 按空行切（Markdown 语义）；
          没有空行 → 按行切（纯文本常见形态）。
    返回的段已 strip 并去空，顺序即原文顺序（段号 = 下标 + 1）。
    """
    if mode not in ("auto", "blank-line", "line"):
        raise ValueError(f"未知分段模式：{mode}")

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if mode == "auto":
        mode = "blank-line" if re.search(r"\n[ \t]*\n", text) else "line"

    if mode == "blank-line":
        parts = re.split(r"\n[ \t]*\n+", text)
    else:
        parts = text.split("\n")

    return [p.strip() for p in parts if p.strip()]


# --------------------------------------------------------------------------
# 受保护 token 抽取
# --------------------------------------------------------------------------


def normalize_digits(text: str) -> str:
    """全角数字/符号转半角。

    中文稿里 `１２Ｍ`、`５０％` 与英译里的 `12M`、`50%` 必须能对上，
    否则每一次比较都会假报「数字丢失」。
    """
    return text.translate(FULLWIDTH_MAP)


def normalize_number(token: str) -> str:
    """数字归一：去掉前后空白与正号，便于多重集比较。"""
    return token.strip().lstrip("+")


def protected(text: str) -> dict[str, list]:
    """抽取受保护 token，返回 dict：

    - ``keep``:  [(type, id)]  —— KEEP 占位符（结构化元素）
    - ``math``:  [原始字符串]  —— 行间 + 行内公式
    - ``cite``:  [原始字符串]  —— 文献引用标记
    - ``num``:   [归一化字符串] —— 数字（含百分号）

    抽取后对应区间被掩成空格，因此数字不会在公式里被重复统计。
    """
    work = normalize_digits(text)

    keep: list[tuple[str, int]] = []
    for m in KEEP_RE.finditer(work):
        keep.append((m.group(1).lower(), int(m.group(2))))
    work = KEEP_RE.sub(" ", work)

    math: list[str] = []
    for pattern in (DISPLAY_MATH_RE, INLINE_MATH_RE):
        for m in pattern.finditer(work):
            math.append(" ".join(m.group(0).split()))
        work = pattern.sub(" ", work)

    cite: list[str] = []
    for m in CITE_RE.finditer(work):
        cite.append(" ".join(m.group(0).split()))
    work = CITE_RE.sub(" ", work)

    num = [normalize_number(x) for x in NUM_RE.findall(work)]

    return {"keep": keep, "math": math, "cite": cite, "num": num}


# --------------------------------------------------------------------------
# 统计
# --------------------------------------------------------------------------


def cjk_chars(text: str) -> int:
    return len(CJK_RE.findall(text))


def en_words(text: str) -> int:
    return len(EN_WORD_RE.findall(text))


def strip_kee_math(text: str) -> str:
    """去掉受保护 token，只留「需要翻译的正文」，用于长度比校验。"""
    work = KEEP_RE.sub(" ", text)
    work = DISPLAY_MATH_RE.sub(" ", work)
    work = INLINE_MATH_RE.sub(" ", work)
    work = CITE_RE.sub(" ", work)
    return work


def length_ratio(src: str, tr: str) -> float:
    """英文字数 / 中文字符数。

    技术文本的合理带大致 0.35–1.10（1 个汉字约对应 0.5–0.8 个英文词）。
    超出这个带通常意味着漏译（偏低）或扩写/解释性翻译（偏高）。
    两边都没有可比较内容时返回 0.0，由调用方跳过。
    """
    zh = cjk_chars(strip_kee_math(src))
    en = en_words(strip_kee_math(tr))
    if zh == 0 or en == 0:
        return 0.0
    return en / zh


def cjk_ratio(text: str) -> float:
    """汉字占「文字字符」的比例：CJK / (CJK + 拉丁字母)。

    刻意把数字、标点、公式符号排除在分母外——它们既不是中文也不是英文，
    算进来会让「实验在 8 块 GPU 上进行，批量 4096」这种纯中文技术段落
    被判成中英混排，从而产生一堆假警报。
    """
    zh = len(CJK_RE.findall(text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = zh + latin
    if total == 0:
        return 0.0
    return zh / total


# --------------------------------------------------------------------------
# 术语表
# --------------------------------------------------------------------------


def load_glossary(path: str | Path) -> list[tuple[str, str]]:
    """读取术语表 CSV：``zh,en[,note]``，允许 # 注释行与空行。

    返回 [(zh, en)]，en 为空的行跳过（尚未确定译法的候选词）。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到术语表：{p}")

    pairs: list[tuple[str, str]] = []
    for raw in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 2:
            continue
        zh, en = parts[0], parts[1]
        if zh and en and zh.lower() != "zh":  # 跳过表头
            pairs.append((zh, en))
    return pairs


def en_variants(en: str) -> list[str]:
    """一个术语的多个可接受译法：``attention mechanism; attention model``。"""
    parts = re.split(r"[;；]|\s/\s", en)
    return [p.strip() for p in parts if p.strip()]


# --------------------------------------------------------------------------
# 对齐
# --------------------------------------------------------------------------


def align(src_blocks: list[str], tr_blocks: list[str]) -> list[tuple[int, str | None, str | None]]:
    """按下标对齐，短的一侧补 None。

    返回 [(段号, 原文 or None, 译文 or None)]，段号从 1 开始。
    这里**故意不做智能对齐**——段号错位本身就是必须报告的问题；
    悄悄按内容相似度重排会让「漏译第 7 段」这种错误消失在报告里。
    """
    n = max(len(src_blocks), len(tr_blocks))
    out: list[tuple[int, str | None, str | None]] = []
    for i in range(n):
        src = src_blocks[i] if i < len(src_blocks) else None
        tr = tr_blocks[i] if i < len(tr_blocks) else None
        out.append((i + 1, src, tr))
    return out


if __name__ == "__main__":  # 极简自检
    demo = "第 3 节讨论注意力机制，见[1]。复杂度 $O(n^2)$，如 <KEEP:figure:1> 所示。共 12M 参数，占 50%。"
    tok = protected(demo)
    assert tok["keep"] == [("figure", 1)], tok["keep"]
    assert tok["math"] == ["$O(n^2)$"], tok["math"]
    assert tok["cite"] == ["[1]"], tok["cite"]
    # 关键回归：公式里的 2 不能被当成数字统计，否则每次比较都假报「数字丢失」
    assert tok["num"] == ["3", "12", "50%"], tok["num"]

    # 全角 → 半角：中文稿写 ５０％、英译写 50%，必须能对上
    assert protected("共５０％的数据，第３章")["num"] == ["50%", "3"]

    # 行间公式的两种写法都要识别，且内部数字不进数字清单
    display = protected("见下：$$E=mc^2$$ 与 \\begin{equation}a=1\\end{equation}")
    assert display["math"] == ["$$E=mc^2$$", "\\begin{equation}a=1\\end{equation}"], display["math"]
    assert display["num"] == [], display["num"]

    assert cjk_chars("中文abc") == 2
    assert en_words("hello world 你好") == 2
    assert segment("a\n\nb\n\nc") == ["a", "b", "c"]
    assert segment("a\nb\nc", "line") == ["a", "b", "c"]
    assert load_glossary.__doc__ is not None  # 占位，避免 lint 误判未使用

    print("bt_common self-check: PASS")
    print("  keep/math/cite/num 抽取顺序正确；公式内数字不重复计数；全角数字已归一")
