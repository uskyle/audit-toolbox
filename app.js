(function () {
  "use strict";

  var lang = document.documentElement.lang.indexOf("zh") === 0 ? "zh" : "en";
  var tools = window.TOOLS || [];

  var T = {
    zh: {
      soon: "即将上线", details: "查看详情", download: "下载", primary: "主线路下载", mirror: "备用线路下载",
      version: "版本", updated: "更新于", size: "大小", platform: "系统",
      offline: "完全离线运行，不上传任何数据",
      steps: "使用步骤", changelog: "更新记录", verify: "校验文件",
      verifyHint: "下载后，在命令提示符（cmd）里运行下面的命令，对比结果是否与这里的校验值一致：",
      sha: "SHA256", pending: "待发布时填写",
      warnTitle: "首次运行被 Windows 拦截？",
      warnBody: "个人开发的小工具没有商业代码签名，Windows SmartScreen 可能提示“已保护你的电脑”。核对上面的校验值无误后，点击“更多信息”→“仍要运行”即可。",
      notFound: "没有找到这个工具。", back: "← 返回工具列表", colVersion: "版本", colDate: "日期", colNote: "说明", none: "暂无工具。"
    },
    en: {
      soon: "Coming soon", details: "Details", download: "Download", primary: "Download (main)", mirror: "Download (mirror)",
      version: "Version", updated: "Updated", size: "Size", platform: "OS",
      offline: "Runs fully offline. No data is uploaded.",
      steps: "How to use", changelog: "Changelog", verify: "Verify the file",
      verifyHint: "After downloading, run this command in Command Prompt (cmd) and compare the result with the checksum here:",
      sha: "SHA256", pending: "Will be filled in at release",
      warnTitle: "Blocked by Windows on first run?",
      warnBody: "Small tools from individual developers are not commercially code-signed, so Windows SmartScreen may show “Windows protected your PC”. After confirming the checksum above matches, click “More info” → “Run anyway”.",
      notFound: "Tool not found.", back: "← Back to all tools", colVersion: "Version", colDate: "Date", colNote: "Notes", none: "No tools yet."
    }
  }[lang];

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "class") node.className = attrs[k];
      else if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      if (c) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function released(tool) {
    return !!(tool.downloads && (tool.downloads.primary || tool.downloads.mirror));
  }

  // 语言切换链接：保留当前页面和查询参数（文件名形如 zh.html / zh-tool.html / zh-about.html）
  var sw = document.getElementById("lang-switch");
  if (sw) {
    var other = lang === "zh" ? "en" : "zh";
    var file = location.pathname.split("/").pop() || (lang + ".html");
    if (file.indexOf(lang) !== 0) file = lang + ".html";
    sw.setAttribute("href", file.replace(/^(zh|en)/, other) + location.search);
  }

  // ---------- 列表页 ----------
  var listBox = document.getElementById("tool-list");
  if (listBox) {
    if (!tools.length) listBox.appendChild(el("p", { class: "empty", text: T.none }));
    tools.forEach(function (tool) {
      var meta = el("div", { class: "meta" }, [
        el("span", { text: T.version + " " + tool.version }),
        el("span", { text: tool.platform })
      ]);
      var badges = el("div", {}, [
        tool.offline ? el("span", { class: "badge ok", text: lang === "zh" ? "离线运行" : "Offline" }) : null
      ]);
      var card = el("div", { class: "card" }, [
        el("div", { class: "icon", text: tool.name[lang].charAt(0) }),
        el("h2", { text: tool.name[lang] }),
        el("p", { text: tool.summary[lang] }),
        badges,
        meta,
        el("a", { class: "btn" + (released(tool) ? "" : " secondary"), href: lang + "-tool.html?id=" + encodeURIComponent(tool.id),
          text: released(tool) ? T.details : T.soon + " · " + T.details })
      ]);
      listBox.appendChild(card);
    });
  }

  // ---------- 详情页 ----------
  var detailBox = document.getElementById("tool-detail");
  if (detailBox) {
    var id = new URLSearchParams(location.search).get("id");
    var tool = tools.filter(function (t) { return t.id === id; })[0];

    detailBox.appendChild(el("a", { href: lang + ".html", text: T.back }));

    if (!tool) {
      detailBox.appendChild(el("p", { class: "empty", text: T.notFound }));
    } else {
      document.title = tool.name[lang] + " · " + document.title.split("·").pop().trim();

      detailBox.appendChild(el("h1", { text: tool.name[lang] }));
      detailBox.appendChild(el("p", { class: "lead", text: tool.intro[lang] }));

      var facts = el("div", { class: "facts" }, [
        el("span", {}, [T.version + " ", el("b", { text: tool.version })]),
        el("span", {}, [T.updated + " ", el("b", { text: tool.updated })]),
        el("span", {}, [T.size + " ", el("b", { text: tool.size })]),
        el("span", {}, [T.platform + " ", el("b", { text: tool.platform })])
      ]);
      detailBox.appendChild(facts);

      if (tool.offline) detailBox.appendChild(el("span", { class: "badge ok", text: T.offline }));

      var row = el("div", { class: "btn-row" });
      if (released(tool)) {
        if (tool.downloads.primary) row.appendChild(el("a", { class: "btn", href: tool.downloads.primary, rel: "noopener", text: T.primary }));
        if (tool.downloads.mirror) row.appendChild(el("a", { class: "btn secondary", href: tool.downloads.mirror, rel: "noopener", text: T.mirror }));
      } else {
        row.appendChild(el("span", { class: "btn disabled", text: T.soon }));
      }
      detailBox.appendChild(row);

      // 备用线路版本标注（例如备用线路仍为旧版时提示）
      if (tool.downloads.mirror && tool.mirrorNote && tool.mirrorNote[lang]) {
        detailBox.appendChild(el("p", { style: "color:#888;font-size:14px;margin-top:8px", text: tool.mirrorNote[lang] }));
      }

      // 使用步骤
      detailBox.appendChild(el("h2", { text: T.steps }));
      var ol = el("ol");
      (tool.steps[lang] || []).forEach(function (s) { ol.appendChild(el("li", { text: s })); });
      detailBox.appendChild(ol);

      // 校验
      detailBox.appendChild(el("h2", { text: T.verify }));
      var fileName = tool.file || (tool.id + ".exe");
      detailBox.appendChild(el("div", { class: "panel" }, [
        el("p", { text: T.verifyHint }),
        el("pre", { text: "certutil -hashfile " + fileName + " SHA256" }),
        el("p", {}, [T.sha + ": "]),
        el("pre", { text: tool.sha256 || T.pending })
      ]));

      detailBox.appendChild(el("div", { class: "warn", style: "margin-top:16px" }, [
        el("strong", { text: T.warnTitle }),
        T.warnBody
      ]));

      // 更新记录
      detailBox.appendChild(el("h2", { text: T.changelog }));
      var thead = el("thead", {}, [el("tr", {}, [
        el("th", { text: T.colVersion }), el("th", { text: T.colDate }), el("th", { text: T.colNote })
      ])]);
      var tbody = el("tbody");
      (tool.changelog || []).forEach(function (c) {
        tbody.appendChild(el("tr", {}, [
          el("td", { text: c.version }), el("td", { text: c.date }), el("td", { text: c[lang] })
        ]));
      });
      detailBox.appendChild(el("table", {}, [thead, tbody]));
    }
  }
})();
