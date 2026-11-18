"""把 guard.py 的 JSON 渲染成可转发的质检报告（Markdown + 自包含 HTML）。

为什么报告本身是产品的一部分：

回译精修的使用者通常是课题组里「替全组把关的那个人」——导师、一作、编辑部联络人。
他在乎的不是工具，而是**能不能直接把一份东西转给别人看**：
「这一版我核过了，7 段里 6 段有硬错误，第 4 段公式丢了，第 6 段数字被改。」
所以报告要有结论、要有数字、要能复现（附命令与输入哈希），且 HTML 单文件可直接发邮件。

用法：
    python scripts/report.py out.json                 # 生成 out_report.md / .html
    python scripts/report.py out.json --out-dir dist  # 指定目录
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from license_check import require_license_or_exit

STATUS_STYLE = {
    "PASS": ("通过", "#0f8a4d", "#e8f6ee"),
    "WARN": ("需复核", "#a86a00", "#fdf3e0"),
    "FAIL": ("未通过", "#c0392b", "#fdecea"),
}

LEVEL_LABEL = {"error": "必须修正", "warn": "建议复核"}


def sha256_short(path: str) -> str:
    """输入文件短哈希——让报告可复现：同一份输入必然得到同一份结论。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:12]
    except OSError:
        return "n/a"


def collect(report: dict) -> dict:
    inputs = report["inputs"]
    files = {
        "原稿": (inputs["source"], sha256_short(inputs["source"])),
        "译稿": (inputs["translation"], sha256_short(inputs["translation"])),
    }
    if inputs.get("back_translation"):
        files["回译稿"] = (inputs["back_translation"], sha256_short(inputs["back_translation"]))
    if inputs.get("glossary"):
        files["术语表"] = (inputs["glossary"], sha256_short(inputs["glossary"]))

    errors = [c for c in report["checks"] if c["level"] == "error" and not c["passed"]]
    warns = [c for c in report["checks"] if c["level"] == "warn" and not c["passed"]]
    return {"files": files, "errors": errors, "warns": warns}


def render_md(report: dict) -> str:
    st = report["stats"]
    c = collect(report)
    label, _fg, _bg = STATUS_STYLE[report["verdict"]]
    lines: list[str] = []

    lines.append("# 回译精修 · 质检报告")
    lines.append("")
    lines.append(f"**结论：{report['verdict']}（{label}）** ｜ 生成于 {report['generated_at']} ｜ {report['tool']} v{report['version']}")
    lines.append("")
    lines.append(f"- 硬错误 **{report['counts']['error']}** 项｜建议复核 **{report['counts']['warn']}** 项｜共 {report['counts']['checks']} 项检查")
    lines.append("")

    lines.append("## 一、关键指标")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| 原稿 | {st['blocks_source']} 段 / {st['cjk_source']} 汉字 |")
    lines.append(f"| 译稿 | {st['blocks_translation']} 段 / {st['en_words_translation']} 英文词 |")
    lines.append(f"| 整体长度比 | {st['overall_ratio']}（英文词/汉字） |")
    lines.append(
        f"| 受保护元素 | 占位符 {st['keep_tokens']} / 公式 {st['math_tokens']} / 引用 {st['cite_tokens']} / 数字 {st['num_tokens']} |"
    )
    if st.get("back"):
        b = st["back"]
        lines.append(f"| 回译 | {b['blocks']} 段 / {b['cjk']} 汉字（相对原稿 {b['ratio_to_source']}） |")
    if report["inputs"].get("glossary"):
        lines.append(f"| 术语表 | {report['inputs']['glossary_terms']} 条 |")
    lines.append("")

    lines.append("## 二、检查项一览")
    lines.append("")
    lines.append("| 检查项 | 级别 | 结果 | 问题数 |")
    lines.append("|---|---|---|---|")
    for chk in report["checks"]:
        mark = "✅ 通过" if chk["passed"] else ("❌ 未过" if chk["level"] == "error" else "⚠️ 复核")
        # 通过的检查没有严重级别可言，标 — 即可；否则「必须修正 + 通过」读起来自相矛盾
        level_cell = LEVEL_LABEL[chk["level"]] if not chk["passed"] else "—"
        lines.append(f"| {chk['title']} | {level_cell} | {mark} | {chk['count']} |")
    lines.append("")

    def section(title: str, checks: list[dict], fatal: bool) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not checks:
            lines.append("无。" if fatal else "无——机械项未发现可疑点。")
            lines.append("")
            return
        for chk in checks:
            lines.append(f"### {chk['title']}（{chk['count']} 项）")
            lines.append("")
            if chk.get("desc"):
                lines.append(f"> {chk['desc']}")
                lines.append("")
            for item in chk["items"]:
                loc = f"第 {item['block']} 段" if item["block"] else "整体"
                lines.append(f"- **{loc}**：{item['detail']}")
            lines.append("")

    section("三、必须修正（硬错误）", c["errors"], fatal=True)
    section("四、建议复核（可疑项）", c["warns"], fatal=False)

    lines.append("## 五、逐段状态")
    lines.append("")
    lines.append("| 段 | 汉字 | 英文词 | 比值 | 状态 | 问题 |")
    lines.append("|---:|---:|---:|---:|---|---|")
    for b in report["blocks"]:
        ratio = "—" if b["ratio"] in (None, 0.0) else f"{b['ratio']:.2f}"
        mark = {"ok": "✅", "warn": "⚠️", "error": "❌"}[b["status"]]
        issue = "；".join(b["issues"])[:80] if b["issues"] else "—"
        lines.append(f"| {b['block']} | {b['cjk']} | {b['words']} | {ratio} | {mark} | {issue} |")
    lines.append("")

    lines.append("## 六、可复现信息")
    lines.append("")
    for name, (path, digest) in c["files"].items():
        lines.append(f"- {name}：`{path}`（sha256: {digest}）")
    lines.append("")
    lines.append("```bash")
    lines.append(
        "python scripts/guard.py \\\n"
        f"  --source \"{report['inputs']['source']}\" \\\n"
        f"  --translation \"{report['inputs']['translation']}\""
        + (f" \\\n  --back \"{report['inputs']['back_translation']}\"" if report["inputs"].get("back_translation") else "")
        + (f" \\\n  --glossary \"{report['inputs']['glossary']}\"" if report["inputs"].get("glossary") else "")
        + " \\\n  --json out.json"
    )
    lines.append("```")
    lines.append("")

    lines.append("## 七、本报告的边界")
    lines.append("")
    lines.append("- 覆盖：段落覆盖、结构化占位符、公式、数字、文献引用、译稿残留中文、术语一致性、长度异常、相邻重复、回译往返。")
    lines.append("- **不覆盖语义**：本报告是*机械可判项*的闸。语义是否走样（缺失/添加/扭曲）须按 `SKILL.md` Step 3 逐段比对，结论不可由本报告替代。")
    lines.append("- 长度比与术语项为启发式：越界只代表「值得看一眼」，不等于错误。")
    lines.append("")
    return "\n".join(lines)


def render_html(report: dict) -> str:
    st = report["stats"]
    c = collect(report)
    verdict = report["verdict"]
    label, fg, bg = STATUS_STYLE[verdict]
    e = escape

    def chip(level: str) -> str:
        color = "#c0392b" if level == "error" else "#a86a00"
        return f'<span class="chip" style="color:{color};border-color:{color}">{LEVEL_LABEL[level]}</span>'

    checks_rows: list[str] = []
    for chk in report["checks"]:
        level_cell = chip(chk["level"]) if not chk["passed"] else "<span class='muted'>—</span>"
        result_cell = "<span class='ok'>通过</span>" if chk["passed"] else "<span class='bad'>未过</span>"
        checks_rows.append(
            f"<tr><td>{escape(chk['title'])}</td><td>{level_cell}</td>"
            f"<td>{result_cell}</td><td class='num'>{chk['count']}</td></tr>"
        )
    rows_checks = "\n".join(checks_rows)

    def block_list(checks: list[dict]) -> str:
        if not checks:
            return "<p class='muted'>无。</p>"
        out = []
        for chk in checks:
            out.append(f"<h3>{e(chk['title'])} <span class='muted'>（{chk['count']} 项）</span></h3>")
            if chk.get("desc"):
                out.append(f"<p class='muted small'>{e(chk['desc'])}</p>")
            out.append("<ul>")
            for item in chk["items"]:
                loc = f"<b>第 {item['block']} 段</b>：" if item["block"] else "<b>整体</b>："
                out.append(f"<li>{loc}{e(item['detail'])}</li>")
            out.append("</ul>")
        return "\n".join(out)

    status_label = {"ok": "正常", "warn": "复核", "error": "有错"}
    status_class = {"ok": "ok", "warn": "warn", "error": "bad"}
    rows_blocks_list: list[str] = []
    for b in report["blocks"]:
        ratio = "—" if b["ratio"] in (None, 0.0) else f"{b['ratio']:.2f}"
        issues = escape("；".join(b["issues"])[:120]) if b["issues"] else "—"
        rows_blocks_list.append(
            f"<tr><td class='num'>{b['block']}</td>"
            f"<td class='num'>{b['cjk']}</td>"
            f"<td class='num'>{b['words']}</td>"
            f"<td class='num'>{ratio}</td>"
            f"<td class='{status_class[b['status']]}'>{status_label[b['status']]}</td>"
            f"<td class='small'>{issues}</td></tr>"
        )
    rows_blocks = "\n".join(rows_blocks_list)

    files_html = "\n".join(
        f"<li>{e(name)}：<code>{e(path)}</code><br><span class='muted small'>sha256: {digest}</span></li>"
        for name, (path, digest) in c["files"].items()
    )

    back = ""
    if st.get("back"):
        b = st["back"]
        back = f"<tr><td>回译</td><td>{b['blocks']} 段 / {b['cjk']} 汉字（相对原稿 {b['ratio_to_source']}）</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>回译精修质检报告 · {verdict}</title>
<style>
  :root {{ --ink:#1c1c1e; --muted:#6b7280; --line:#e5e7eb; --bg:#fafaf9; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:40px 20px; background:var(--bg); color:var(--ink);
         font:15px/1.7 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }}
  .wrap {{ max-width:900px; margin:0 auto; background:#fff; border:1px solid var(--line);
           border-radius:14px; padding:38px 42px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
  h1 {{ font-size:24px; margin:0 0 6px; letter-spacing:-.01em; }}
  h2 {{ font-size:17px; margin:34px 0 12px; padding-bottom:8px; border-bottom:1px solid var(--line); }}
  h3 {{ font-size:15px; margin:20px 0 8px; }}
  .banner {{ display:flex; align-items:center; gap:14px; background:{bg}; color:{fg};
             border:1px solid {fg}33; border-radius:10px; padding:14px 18px; margin:18px 0 4px; }}
  .banner .verdict {{ font-size:22px; font-weight:700; letter-spacing:.02em; }}
  .banner .sub {{ color:var(--muted); font-size:13px; margin-left:auto; }}
  table {{ width:100%; border-collapse:collapse; margin:10px 0; font-size:14px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ font-weight:600; color:var(--muted); font-size:13px; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .chip {{ font-size:11px; border:1px solid; border-radius:999px; padding:1px 8px; white-space:nowrap; }}
  .ok {{ color:#0f8a4d; }} .bad {{ color:#c0392b; }} .warn {{ color:#a86a00; }}
  .muted {{ color:var(--muted); }} .small {{ font-size:13px; }}
  code {{ background:#f3f4f6; padding:1px 6px; border-radius:5px; font-size:13px;
          font-family:ui-monospace,Consolas,monospace; word-break:break-all; }}
  ul {{ margin:6px 0 14px; padding-left:22px; }} li {{ margin:4px 0; }}
  .note {{ background:#f8fafc; border-left:3px solid #cbd5e1; padding:12px 16px; border-radius:0 8px 8px 0;
           font-size:14px; color:#374151; }}
  footer {{ margin-top:32px; padding-top:14px; border-top:1px solid var(--line);
            color:var(--muted); font-size:12px; }}
</style></head>
<body><div class="wrap">
  <h1>回译精修 · 质检报告</h1>
  <div class="muted small">{e(report['tool'])} v{e(report['version'])} · {e(report['generated_at'])}</div>

  <div class="banner">
    <span class="verdict">{verdict}</span><span>{label}</span>
    <span class="sub">硬错误 {report['counts']['error']} · 建议复核 {report['counts']['warn']} · 检查项 {report['counts']['checks']}</span>
  </div>

  <h2>一、关键指标</h2>
  <table>
    <tr><td>原稿</td><td>{st['blocks_source']} 段 / {st['cjk_source']} 汉字</td></tr>
    <tr><td>译稿</td><td>{st['blocks_translation']} 段 / {st['en_words_translation']} 英文词</td></tr>
    <tr><td>整体长度比</td><td>{st['overall_ratio']}（英文词/汉字）</td></tr>
    <tr><td>受保护元素</td><td>占位符 {st['keep_tokens']} / 公式 {st['math_tokens']} / 引用 {st['cite_tokens']} / 数字 {st['num_tokens']}</td></tr>
    {back}
  </table>

  <h2>二、检查项一览</h2>
  <table><thead><tr><th>检查项</th><th>级别</th><th>结果</th><th class="num">问题数</th></tr></thead>
  <tbody>{rows_checks}</tbody></table>

  <h2>三、必须修正（硬错误）</h2>
  {block_list(c['errors'])}

  <h2>四、建议复核（可疑项）</h2>
  {block_list(c['warns'])}

  <h2>五、逐段状态</h2>
  <table><thead><tr><th class="num">段</th><th class="num">汉字</th><th class="num">英文词</th>
  <th class="num">比值</th><th>状态</th><th>问题</th></tr></thead>
  <tbody>{rows_blocks}</tbody></table>

  <h2>六、可复现信息</h2>
  <ul>{files_html}</ul>

  <h2>七、本报告的边界</h2>
  <div class="note">
    本报告覆盖<strong>机械可判项</strong>：段落覆盖、结构化占位符、公式、数字、文献引用、译稿残留中文、
    术语一致性、长度异常、相邻重复、回译往返。<br>
    <strong>不覆盖语义</strong>：语义是否走样（缺失 / 添加 / 扭曲）须按 <code>SKILL.md</code> Step 3 逐段比对，
    本报告不能替代语义复核。长度比与术语项为启发式提示，越界不等于错误。
  </div>

  <footer>由 back-translate-refinement 生成 · 同一输入必然得到同一结论（见 sha256 与命令）</footer>
</div></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="把 guard.py 的 JSON 渲染成可转发的质检报告")
    ap.add_argument("report_json", help="guard.py --json 输出的文件")
    ap.add_argument("--out-dir", default=None, help="输出目录（默认与 JSON 同目录）")
    ap.add_argument("--stem", default=None, help="输出文件名前缀（默认取 JSON 文件名去扩展名）")
    args = ap.parse_args()

    require_license_or_exit("core")

    src = Path(args.report_json)
    if not src.exists():
        print(f"error：找不到 {src}", file=sys.stderr)
        return 2
    report = json.loads(src.read_text(encoding="utf-8-sig"))

    out_dir = Path(args.out_dir) if args.out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.stem or src.stem.replace("_report", "") or "report"

    md_path = out_dir / f"{stem}_report.md"
    html_path = out_dir / f"{stem}_report.html"
    md_path.write_text(render_md(report), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")

    print(f"结论：{report['verdict']}（error {report['counts']['error']} / warn {report['counts']['warn']}）")
    print(f"  Markdown：{md_path}")
    print(f"  HTML    ：{html_path}  ← 单文件，可直接发给合作者")
    return 0


if __name__ == "__main__":
    sys.exit(main())
