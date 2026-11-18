# 结构化元素保留规范（Structured-Element Preservation）

原稿的非文本元素在回译精修全程必须原样保留。本文件规定识别方法、占位标记与两种排版约定，供 SKILL.md Step 2/3/7 引用。

## 占位标记格式

统一使用 `<KEEP:type:id>`，`type ∈ {figure, table, cite, eq, math}`：

| 元素类型 | 占位标记 | 说明 |
|----------|----------|------|
| 插图 | `<KEEP:figure:1>` | 图片连同 caption 视为同一元素 |
| 表格 | `<KEEP:table:1>` | 整表（表头+内容）一个占位，不逐格翻译 |
| 文献引用 | `<KEEP:cite:1>` | 单个引用标记（`[1]`、`\cite{key}`） |
| 行间公式 | `<KEEP:eq:1>` | display equation |
| 行内数学 | `<KEEP:math:1>` | 正文中的行内符号或公式 |

规则：

- ID 按元素在**全篇文档**中的出现顺序递增（分批处理时不得按批重编）。
- 同一元素在正译、回译、比对、修正、还原全程使用相同 ID。
- 占位标记本身不翻译、不改动、不删除。
- `guard.py` 会把 KEEP 序列当多重集校验：多一个、少一个、顺序错乱都算 error。

## 两种排版约定

### A. 内联占位（推荐）

元素在文中被**引用**处放置占位符，元素本体由 Step 7 还原：

> 本节讨论注意力机制。如图 1 所示，模型在 $O(n^2)$ 复杂度下运行。
>
> 正译/回译时 → This section discusses the attention mechanism. As shown in <KEEP:figure:1>, the model runs at <KEEP:math:1> complexity.

适合元素独立成块（图片、表格通常如此），段数保持一一对应。

### B. 整块替换

若元素本体**必须占据正文位置**（如 Markdown 图片行 `![图1](fig1.png)`），则用占位符**独占该块**，原块两侧各保留一次占位（引用处 + 本体处），两侧使用同一 ID。此时段数仍不变——占位块就是那个块。

> 引用处：The experimental setup is given in <KEEP:table:1>.
>
> 本体块：`<KEEP:table:1>`（独占一段，替换原表格）
>
> guard 会看到同一 ID 出现两次，这是预期行为；Step 7 还原时只把「本体块」换回原表，引用处替换回图号文字。

**不要**把占位符和正文混在一个 markdown 块里又让元素本体独立成段——那会让段数对不上，guard 直接 FAIL。

## 识别要点

### 插图（figure/image）

- Markdown：`![caption](path)`
- LaTeX：`\begin{figure}...\end{figure}`、`\includegraphics{...}`、`\caption{...}`
- Word：图片 + 紧邻的 caption 段落视为同一元素

### 表格（table）

- Markdown 表格、`\begin{table}...\end{table}`、`\begin{tabular}...\end{tabular}`
- Word：`docx.Document(...).tables` 中的每个表
- 整表一个占位单元；表内文字确实需要翻译时，另建「表格译文对照」，不占用正文段号

### 文献引用（citation）

- 编号制：`[1]`、`[2-3]`、`[1,2]`
- 作者-年份制：`(Zhang et al., 2023)` —— **建议也占位**：作者名与年份极易被回译改写
- LaTeX：`\cite{key}`、`\citep{}`、`\citet{}`、`\bibitem{}`
- 文末参考文献列表整节占位，不翻译、不重排

### 方程与数学符号（equation / math）

- 行内：`$...$`、`\(...\)`、Word OMML 对象
- 行间：`$$...$$`、`\[...\]`、`\begin{equation|align|cases|gather}...\end{...}`
- 希腊字母、上下标、运算符原样保留，不翻译、不转写
- `guard.py` 的公式多重集校验是**逐字**的：`$O(n^2)$` 被写成 `$O(n2)$` 或 `$O(n²)$` 都算 error

## 还原（Step 7）与验收

替换正文后，按 ID 把占位符还原为原始元素，并校验：

- 元素数量与原稿一致（guard：keep 多重集）
- 每个元素内容未被改动（guard：公式逐字；表格/图片由 docx 对比或人工）
- 元素位置与原文一致（guard：keep-order 顺序单调）

任何一项不过，交付不成立。
