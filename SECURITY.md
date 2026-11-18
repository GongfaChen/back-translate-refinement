# 安全策略 / Security Policy

## 支持的版本

| 版本 | 状态 |
|---|---|
| `main` 分支 | ✅ 接受安全修复 |
| v0.x | ✅ 接受安全修复 |

## 如何报告漏洞

**请不要开公开 issue。** 用 GitHub 的私密渠道：

1. 打开仓库 → **Security** → **Report a vulnerability**（GitHub Security Advisories）；
2. 在 Advisory 中附 PoC 与影响版本。

会在 7 天内确认、30 天内给出修复或缓解；修复发布后在 release notes 致谢（可要求匿名）。

## 重点关注的面

- **许可绕过**：`scripts/license_check.py` 验签逻辑、`PAID_FEATURES` 闸门能否被绕过；
- **密钥泄漏**：私钥种子（`ed25519_seed.hex`）、签发的 `license.json` 被提交或写入日志；
- **报告注入**：`report.py` 渲染 HTML 时对正文做了 escape，但**术语表 / 原稿内容是用户可控输入**——若把报告公开部署（如 Web 服务），需重新评估 XSS 面；
- **路径写入**：`glossary.py extract --out`、`guard.py --json`、`report.py --out-dir` 的输出路径；
- **依赖供应链**：本工具链刻意少依赖（纯文本流程零第三方依赖），新增依赖需说明理由。

## 已知的设计取舍（不是漏洞）

- **离线许可天然可绕过**：用户改系统时间或打补丁跳过校验，离线方案无法阻止；本项目只保证「不改代码就绕不过」。
- **不做验签缓存**：每次调用多花约 0.16 s，换取「缓存文件不可被伪造」。
- **环境变量公钥仅开发模式生效**（`BTR_DEV=1`）：发布构建忽略 `BTR_PUBKEY`，否则自签即可绕过付费闸。
- **确定性检查的边界**：guard 的术语/长度项是启发式，越界 ≠ 错误；语义判定明确不做（见 report-spec.md）。

## 不在范围内

- 译文的语义正确性（属功能正确性，请走普通 issue）；
- 用户自有文档的版权与授权。
