/*
 * 工具清单 / Tool catalog
 * ------------------------------------------------------------
 * 新增工具：复制下面任意一个对象，改 id 和内容即可。
 * To add a tool: copy one object below, change the id and fields.
 *
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
    version: "0.0.0",
    updated: "2026-11-01",
    size: "—",
    platform: "Windows 10/11",
    offline: true,
    downloads: { primary: "", mirror: "" },
    sha256: "",
    changelog: [
      { version: "0.0.0", date: "2026-11-01", zh: "占位，尚未发布。", en: "Placeholder, not released yet." }
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
      zh: "导入银行流水和账面明细，按金额、日期、对方户名等条件自动匹配，列出未达账项和疑似差异，减少手工逐笔核对的时间。结果仅供辅助，请自行复核。",
      en: "Import a bank statement and ledger detail, auto-match by amount, date and counterparty, and list unmatched or suspicious items. Results are for assistance only; please review them yourself."
    },
    steps: {
      zh: ["下载并双击运行。", "导入银行流水和账面明细（Excel / CSV）。", "设置匹配条件，点击核对。", "查看差异清单，可导出为 Excel。"],
      en: ["Download and double-click to run.", "Import the bank statement and ledger detail (Excel / CSV).", "Set matching rules and run the check.", "Review the differences and export them to Excel."]
    },
    version: "0.0.0",
    updated: "2026-11-01",
    size: "—",
    platform: "Windows 10/11",
    offline: true,
    downloads: { primary: "", mirror: "" },
    sha256: "",
    changelog: [
      { version: "0.0.0", date: "2026-11-01", zh: "占位，尚未发布。", en: "Placeholder, not released yet." }
    ]
  }
];
