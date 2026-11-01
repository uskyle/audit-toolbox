# 审计小工具箱 / Audit Toolbox（占位版）

纯静态双语站，不需要安装任何东西。双击 `index.html` 就能本地预览。

## 目录
- `index.html`      根据浏览器语言跳转到 zh/ 或 en/
- `zh/` `en/`       中文 / 英文页面（列表、详情、声明）
- `assets/tools.js` **工具清单，新增或修改工具只改这一个文件**
- `assets/style.css` `assets/app.js`  样式与页面逻辑

## 新增一个工具
1. 打开 `assets/tools.js`，复制一个工具对象，改 `id`、名称、简介、步骤。
2. 把 exe 上传到 GitHub Releases，拿到文件链接，填进 `downloads.primary`。
3. 算 SHA256（Windows 命令提示符）：`certutil -hashfile 文件名.exe SHA256`，填进 `sha256`。
4. 链接留空时，页面自动显示“即将上线”。

## 发布到网上（匿名）
- 推荐 Cloudflare Pages 或 GitHub Pages：新建仓库，上传本文件夹全部内容，开启托管即可。
- 域名注册时开启 WHOIS 隐私保护，用单独邮箱。
- 上传前请检查 exe 属性里的作者/公司名，以及打包路径是否包含你的 Windows 用户名。

## 改站名
在 `zh/*.html`、`en/*.html`、`index.html` 里搜索“审计小工具箱”和“Audit Toolbox”替换即可。
