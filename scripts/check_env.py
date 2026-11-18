"""前置环境闸：干活之前确认「这台机器能不能跑完整流程」。只读，不修改任何文件。

检查项（按重要性）：
  1. Python 版本（>= 3.10；f-string / 数据类 / 现代类型标注都在用）
  2. 核心依赖（本工具链刻意做到零第三方硬依赖——纯文本流程只靠标准库）
  3. 可选依赖（python-docx：处理 .docx 才需要）
  4. 许可钩子自检（license_check --self-test 的快速版）
  5. 脚本完整性（四个 CLI 都能 import 且有 main）

为什么没有 PowerPoint COM 检查：这个 skill 不做文档渲染，
docx 的读写由 python-docx 完成，与 Office 安装无关——和 pdf-to-pptx-omml 不同。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from license_check import require_license_or_exit

MIN_PYTHON = (3, 10)

REQUIRED = []          # 纯文本流程（.md/.txt）零第三方依赖
OPTIONAL = {           # 按需安装，缺失不阻断纯文本流程
    "docx": "python-docx（处理 .docx 原稿/译稿时需要）",
}
SCRIPTS = ["bt_common", "bt_probe", "guard", "glossary", "report", "license_check"]


def check_python() -> tuple[bool, str]:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    return ok, f"Python {v.major}.{v.minor}.{v.micro}（要求 >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}）"


def check_module(name: str) -> tuple[bool, str]:
    found = importlib.util.find_spec(name) is not None
    return found, (f"已安装" if found else "未安装")


def check_scripts() -> tuple[bool, list[str]]:
    """四个 CLI 能否被 import（语法错误、依赖缺失都会在这里暴露）。"""
    problems: list[str] = []
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    for name in SCRIPTS:
        try:
            __import__(name)
        except Exception as exc:  # noqa: BLE001 - 任何 import 失败都要报
            problems.append(f"{name}: {type(exc).__name__}: {exc}")
    return not problems, problems


def main() -> int:
    require_license_or_exit("probe")

    print("=" * 58)
    print("back-translate-refinement · 环境闸（只读）")
    print("=" * 58)

    ok_all = True

    ok, msg = check_python()
    print(f"[{'OK ' if ok else 'FAIL'}] Python      ：{msg}")
    ok_all &= ok

    for name in REQUIRED:
        found, msg = check_module(name)
        print(f"[{'OK ' if found else 'FAIL'}] 依赖        ：{name} {msg}")
        ok_all &= found

    for name, desc in OPTIONAL.items():
        found, msg = check_module(name)
        mark = "OK " if found else "SKIP"
        print(f"[{mark}] 可选依赖    ：{name} {msg} —— {desc}")

    ok, problems = check_scripts()
    print(f"[{'OK ' if ok else 'FAIL'}] 脚本完整性  ：{len(SCRIPTS)} 个模块")
    for p in problems:
        print(f"       - {p}")
    ok_all &= ok

    try:
        from license_check import ed25519_keygen, ed25519_sign, ed25519_verify

        seed, pub = ed25519_keygen()
        sig = ed25519_sign(seed, b"self-check")
        assert ed25519_verify(pub, b"self-check", sig)
        assert not ed25519_verify(pub, b"tampered", sig)
        print("[OK ] 许可钩子    ：Ed25519 签名/验签/防篡改 正常")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] 许可钩子    ：{type(exc).__name__}: {exc}")
        ok_all = False

    print("-" * 58)
    print("结论：" + ("环境就绪，可以开始回译精修流程。" if ok_all else "存在阻断项，请先修复上面的 FAIL。"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
