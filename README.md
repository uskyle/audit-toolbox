# 审计小工具箱 / Audit Toolbox（占位版）

纯静态双语站，**所有文件都在同一层，没有子文件夹**。双击 `index.html` 即可本地预览。

## 文件
- `index.html`   根据浏览器语言跳转到 zh.html 或 en.html
- `zh.html` `zh-tool.html` `zh-about.html`   中文：列表 / 详情 / 声明
- `en.html` `en-tool.html` `en-about.html`   English: list / detail / about
- `tools.js`     **工具清单，新增或修改工具只改这一个文件**
- `style.css` `app.js`   样式与页面逻辑

## 新增一个工具
1. 打开 `tools.js`，复制一个工具对象，改 `id`、名称、简介、步骤、`file`（exe 文件名）。
2. 把 exe 上传到 GitHub Releases，把下载链接填进 `downloads.primary`。
3. SHA256：Releases 页面会显示，或在 cmd 运行 `certutil -hashfile 文件名.exe SHA256`，填进 `sha256`。
4. 链接留空时，页面自动显示“即将上线”。

## 改站名
在 html 文件里搜索“审计小工具箱”和“Audit Toolbox”替换。
