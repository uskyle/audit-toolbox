/*
 * 工具清单 / Tool catalog
 * ------------------------------------------------------------
 * 新增工具：复制下面任意一个对象，改 id 和内容即可。
 * To add a tool: copy one object below, change the id and fields.
 *
 * file               exe 的文件名（用于校验命令里显示）
 * downloads.primary  主线路（GitHub Releases 的文件链接）
 * downloads.mirror   备用线路（Cloudflare R2 / 网盘直链），没有就留空 ""
 * sha256             exe 的 SHA256 校验值，留空则页面显示"待发布时填写"
 * 链接留空 "" 时，页面显示"即将上线"，按钮不可点击。
 */
window.TOOLS = [
  {
    id: "pdf-compress",
    name: { zh: "PDF 压缩", en: "PDF Compressor" },
    summary: {
      zh: "把体积很大的 PDF 底稿、扫描件压小，方便邮件发送和归档。",
      en: "Shrink large PDF workpapers and scans for easier emailing and archiving."
    },
    intro: {
      zh: "审计底稿里常有几十 MB 的扫描件，邮箱附件发不出去。这个工具在尽量保持清晰度的前提下压缩 PDF，全程在本机完成。",
      en: "Audit workpapers often include scans that are too big to email. This tool compresses PDFs while keeping them readable, entirely on your own computer."
    },
    steps: {
      zh: ["下载并解压（如有压缩包），双击运行。", "选择要压缩的 PDF 文件。", "选择压缩强度，点击开始。", "在原文件旁边得到压缩后的新文件，原文件不会被改动。"],
      en: ["Download and double-click to run.", "Choose the PDF file(s) to compress.", "Pick a compression level and start.", "The compressed copy is saved next to the original; the original is never modified."]
    },
    file: "PDF-Compressor.exe",
    version: "1.0.1",
    updated: "2026-11-02",
    size: "29.6 MB",
    platform: "Windows 10/11",
    offline: true,
    downloads: { primary: "https://github.com/uskyle/audit-toolbox/releases/download/v1.0.0/PDF-Compressor.exe", mirror: "https://gitee.com/midnight-sky/audit-toolbox/releases/download/v1.0.1/PDF-Compressor.exe" },
    sha256: "590e1128036f29b4ed29fbcce7cd1cc54d0daf81a372070b0229583eb0ec1969",
    changelog: [
      { version: "1.0.1", date: "2026-11-02", zh: "压缩后变大时自动降低分辨率重试；黑白扫描件存成灰度图；新增“带文字层也压缩”选项；跳过的文件显示完整原因。", en: "Retries at lower resolution when the result would be larger; greyscale scans are stored as greyscale; new option to also compress PDFs with a text layer; skipped files now show the full reason." },
      { version: "1.0.0", date: "2026-11-01", zh: "首次发布。", en: "Initial release." }
    ]
  },
  {
    id: "bank-statement-check",
    name: { zh: "银行流水核对", en: "Bank Statement Checker" },
    summary: {
      zh: "把银行流水与账面记录逐笔比对，快速列出差异项。",
      en: "Match bank statement lines against ledger records and list the differences."
    },
    intro: {
      zh: "选择客户文件夹（序时账、余额表、银行流水），自动把流水对到各银行账户，做期初、借方、贷方、期末四项勾稽，逐笔匹配，并把“账面有流水无”“流水有账面无”的笔列为差异，一键导出底稿 Excel。流水中间缺行时会提示。结果仅供辅助，请自行复核。",
      en: "Pick a client folder (ledger, trial balance and bank statements). The tool maps each statement to its bank account, ties out opening, debit, credit and closing balances, matches line by line, and lists items found only in the ledger or only in the statement as differences, with one-click Excel export. It warns when a statement has missing lines. Results are for assistance only; please review them yourself."
    },
    steps: {
      zh: ["下载并双击运行。", "选择客户文件夹（含序时账、余额表和银行流水，子文件夹名不限）。", "在下拉里选择银行账户，自动核对；流水对不上账户时，在“流水文件对应…”里手工指定。", "查看差异明细，点“生成底稿”导出为 Excel。"],
      en: ["Download and double-click to run.", "Choose the client folder (ledger, trial balance and bank statements; sub-folder names don't matter).", "Pick a bank account from the list to run the check; if a statement is not mapped to an account, assign it by hand in “Statement mapping…”.", "Review the differences and click Export to save an Excel workpaper."]
    },
    file: "Bank-Statement-Checker.exe",
    version: "1.1.0",
    updated: "2026-11-02",
    size: "24.3 MB",
    platform: "Windows 10/11",
    offline: true,
    downloads: { primary: "https://github.com/uskyle/audit-toolbox/releases/download/Bank-check-v1.1.0/Bank-Statement-Checker.exe", mirror: "https://gitee.com/midnight-sky/audit-toolbox/releases/download/Bank-check-v1.1.0/Bank-check.exe" },
    sha256: "0d3b1c0cc2e0b340925164336b66bfb6a8c5b25edce2b12c9fee8fdfe0909730",
    changelog: [
      { version: "1.1.0", date: "2026-11-02", zh: "序时账列名识别不了时可手工映射，分级科目“银行存款\\户名”也能读；流水自动对应账户（账号、文件名、余额），对不上可手工指定；新增多家银行流水版式；差异清单列出账面有流水无/流水有账面无；流水缺行时提示；体积更小。", en: "Manual column mapping when the ledger can't be recognised; sub-account names like “Bank\\Account” are supported. Statements are auto-mapped to accounts (account number, file name, balance), with manual override. More bank statement layouts. A differences list shows ledger-only and statement-only items. Warns when a statement has missing lines. Smaller file size." },
      { version: "1.0.0", date: "2026-11-01", zh: "首次发布。", en: "Initial release." }
    ]
  }
];
