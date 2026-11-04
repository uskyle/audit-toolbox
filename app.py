# -*- coding: utf-8 -*-
"""银行流水核对工具 · 单户核对界面（tkinter，深色主题，配色与网站一致）

用法：python app.py
"""
import os, re, sys, traceback
import tkinter as tk
from tkinter import filedialog, ttk
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, loaders, exporter, ui
from ui import (BG, SURFACE, SURFACE_HI, TEXT, MUTED, LINE, ACCENT, OK, BAD, BAD_LINE, WARN,
                F, F_S, F_B, F_H1, F_H2, F_MONO, px, YAHEI)

messagebox = ui.MB          # 深色弹窗（接口与 tkinter.messagebox 相同）
D = Decimal
VERSION = "1.1.1"


def short(p, n=64):
    """路径太长时中间用…省略"""
    p = str(p or "")
    return p if len(p) <= n else p[: n // 2 - 1] + " … " + p[-(n // 2 - 2):]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        ui.init_scale(self)
        ui.apply_style(self)
        self.title("银行流水核对 · Bank Statement Checker")
        self.geometry("%dx%d" % (px(1100), px(740)))
        self.minsize(px(920), px(620))
        self.base = None
        self.balance = {}
        self.journal = []
        self.current = None
        self.map = []
        self.stmt_dirs = []
        self.manual = {}     # 手工指定的流水文件归属 {路径: 账户 或 ""=忽略}
        self.fmap = {}       # 自动对应结果 {路径: (候选账户, 依据)}
        self._build()
        self.after(60, lambda: ui.dark_titlebar(self))

    # ---------- 界面 ----------
    def _build(self):
        # 顶栏：渐变小图标 + 标题 + 离线标签
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=px(26), pady=(px(16), px(14)))
        ui.logo(head).pack(side="left")
        tk.Label(head, text="银行流水核对", bg=BG, fg=TEXT, font=F_H1).pack(side="left", padx=(px(10), 0))
        tk.Label(head, text="Bank Statement Checker  v%s" % VERSION, bg=BG, fg=MUTED,
                 font=F_S).pack(side="left", padx=(px(10), 0), pady=(px(5), 0))
        ui.badge(head, "✓ 完全离线运行，不上传任何数据", OK).pack(side="right")
        tk.Frame(self, bg=LINE, height=1).pack(fill="x")

        # 状态栏（先 pack，保证始终在最下面）
        sb = tk.Frame(self, bg=SURFACE)
        sb.pack(fill="x", side="bottom")
        tk.Frame(self, bg=LINE, height=1).pack(fill="x", side="bottom")
        self.dot = tk.Label(sb, text="●", bg=SURFACE, fg=MUTED, font=F_S)
        self.dot.pack(side="left", padx=(px(26), px(6)), pady=px(7))
        self.status = tk.Label(sb, text="选择文件夹后开始", anchor="w", bg=SURFACE, fg=MUTED, font=F_S)
        self.status.pack(side="left", fill="x", expand=True)

        # 工具条
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=px(26), pady=(px(16), px(10)))
        ui.Btn(bar, "选择客户文件夹", self.choose, kind="primary").pack(side="left")
        self.lbl_dir = tk.Label(bar, text="未选择文件夹", bg=BG, fg=MUTED, font=F, anchor="w")
        self.lbl_dir.pack(side="left", padx=(px(14), 0))
        self.lbl_stmt = tk.Label(bar, text="", bg=BG, fg=ACCENT, font=F_S)
        self.lbl_stmt.pack(side="left", padx=(px(10), 0))
        ui.Btn(bar, "流水文件对应…", self.assign_files).pack(side="right")
        ui.Btn(bar, "另加流水文件夹", self.choose_stmt_dir).pack(side="right", padx=(0, px(8)))

        # 账户选择 + 生成底稿
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=px(26), pady=(0, px(8)))
        tk.Label(row, text="银行账户", bg=BG, fg=MUTED, font=F_S).pack(side="left")
        self.cmb = ttk.Combobox(row, state="readonly", font=F)
        self.cmb.pack(side="left", fill="x", expand=True, padx=(px(12), px(12)), ipady=px(3))
        self.cmb.bind("<<ComboboxSelected>>", lambda e: self.run())
        self.btn_export = ui.Btn(row, "生成底稿", self.export, kind="primary", state="disabled")
        self.btn_export.pack(side="right")

        self.box = tk.Frame(self, bg=BG)
        self.box.pack(fill="both", expand=True, padx=px(26), pady=(px(4), 0))
        self._empty("选择客户文件夹，开始核对",
                    "文件夹里放序时账、余额表和银行流水即可，子文件夹叫什么都行\n"
                    "读取、核对都在本机完成，原始资料不会被修改")

    def _dot(self, level):
        self.dot.config(fg={"ok": OK, "warn": WARN, "bad": BAD}.get(level, MUTED))

    def _empty(self, title, hint="", color=MUTED, glyph="◌"):
        """中间区域的空状态 / 提示卡片"""
        for w in self.box.winfo_children():
            w.destroy()
        card = ui.Card(self.box, height=px(170))
        card.pack(fill="x", pady=(px(10), 0))
        b = card.body
        tk.Label(b, text=glyph, bg=SURFACE, fg=color, font=(YAHEI, 24)).pack(pady=(px(8), 0))
        tk.Label(b, text=title, bg=SURFACE, fg=TEXT, font=F_H2).pack(pady=(px(2), 0))
        if hint:
            tk.Label(b, text=hint, bg=SURFACE, fg=MUTED, font=F, justify="center").pack(pady=(px(6), 0))

    def _dlg(self, title, w, h):
        """深色子窗口，居中于主窗口"""
        dlg = tk.Toplevel(self)
        dlg.withdraw()
        dlg.title(title)
        dlg.configure(bg=BG)
        dlg.transient(self)
        x = self.winfo_rootx() + max(0, (self.winfo_width() - px(w)) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - px(h)) // 4)
        dlg.geometry("%dx%d+%d+%d" % (px(w), px(h), x, y))
        return dlg

    def _show_dlg(self, dlg):
        dlg.deiconify()
        ui.dark_titlebar(dlg)

    # ---------- 动作 ----------
    def choose(self):
        p = filedialog.askdirectory(title="选择客户文件夹（含序时账、余额表和银行流水，子文件夹名不限）")
        if not p:
            return
        self.base = p
        self.stmt_dirs = []
        self.manual = {}
        self.lbl_stmt.config(text="")
        self.lbl_dir.config(text=short(p), fg=TEXT)
        self._empty("正在读取…", "序时账较大时需要几秒钟", ACCENT, "⏳")
        self.update_idletasks()
        try:
            self._load_book()
        except Exception as e:
            self._empty("读取失败", "请确认文件夹里有序时账", BAD, "!")
            messagebox.showerror("读取失败", "读不了这个文件夹：\n%s" % e)
            return

    def _pick_file(self, title):
        return filedialog.askopenfilename(
            title=title, filetypes=[("Excel 工作簿", "*.xlsx *.xls"), ("所有文件", "*.*")]) or None

    def choose_stmt_dir(self):
        """可选：流水不在客户文件夹里时，额外指定流水所在文件夹"""
        p = filedialog.askdirectory(title="选择银行流水所在文件夹")
        if p:
            self.stmt_dirs.append(p)
            self.lbl_stmt.config(text="+ 另加流水文件夹 %d 个" % len(self.stmt_dirs))
            self._build_index()
            if self.cmb.get():
                self.run()

    def _find(self, *names):
        for root, _, files in os.walk(self.base):
            for f in files:
                for n in names:
                    if n in f:
                        return os.path.join(root, f)
        return None

    def _load_book(self):
        j = self._find("序时账") or self._pick_file("没找到文件名含“序时账”的文件，请手工选择序时账")
        if not j:
            raise ValueError("没有选择序时账")
        b = self._find("余额表", "明细账") or self._pick_file("没找到文件名含“余额表”的文件，请手工选择余额表（没有可取消）")
        try:
            self.journal = loaders.load_journal(j)
        except ValueError:
            # 自动识别失败 → 让用户手工指定列
            cm = self._ask_colmap(j)
            if not cm:
                raise
            self.journal = loaders.load_journal(j, colmap=cm[0], bank_subject=cm[1])
        self.balance = loaders.load_balance(b) if b else {}
        rp = self._find("关联方")
        if rp:
            try:
                engine.set_related(loaders.load_related(rp))
            except Exception:
                pass
        mp = self._find("账户对照表")
        self.map = []
        if mp:
            try:
                self.map = loaders.load_map(mp)
            except Exception:
                self.map = []
        # 余额表缺失或读不出时，账户取自序时账（期初/期末将显示“—”，不做勾稽）
        accts = sorted(self.balance) or sorted({x["account"] for x in self.journal if x.get("account")})
        used = {x.get("account") for x in self.journal}
        accts.sort(key=lambda a: (a not in used,))        # 有账面分录的户排前面（稳定排序，其余保持原顺序）
        self.cmb["values"] = accts
        self.status.config(text="已读取：%d 个银行账户，%d 笔银行分录" % (len(accts), len(self.journal)))
        self._dot("ok")
        self._build_index()
        if accts:
            self.cmb.current(0)
            self.run()
        else:
            self._empty("没有读到银行账户", "请检查序时账里的银行存款科目", WARN, "!")

    def _ask_colmap(self, path):
        """序时账列映射对话框：返回 ({字段: 列名}, 银行存款科目名) 或 None"""
        _, heads, guess = loaders.journal_headers(path)
        dlg = self._dlg("序时账列映射", 560, 560)
        tk.Label(dlg, text="序时账列映射", bg=BG, fg=TEXT, font=F_H2).pack(anchor="w", padx=px(24), pady=(px(20), 0))
        tk.Label(dlg, text="没能自动识别序时账的列，请手工指定（* 为必选）",
                 bg=BG, fg=MUTED, font=F_S).pack(anchor="w", padx=px(24), pady=(px(2), px(12)))
        form = tk.Frame(dlg, bg=BG)
        form.pack(fill="x", padx=px(24))
        boxes = {}
        for i, (key, label, req, _) in enumerate(loaders.JOURNAL_FIELDS):
            tk.Label(form, text=label + (" *" if req else ""), bg=BG, fg=TEXT if req else MUTED,
                     font=F, anchor="e", width=11).grid(row=i, column=0, sticky="e", padx=(0, px(10)), pady=px(4))
            cb = ttk.Combobox(form, values=([""] if not req else []) + heads, state="readonly", width=34, font=F)
            cb.set(guess.get(key, ""))
            cb.grid(row=i, column=1, sticky="ew", pady=px(4))
            boxes[key] = cb
        n = len(loaders.JOURNAL_FIELDS)
        tk.Label(form, text="银行存款科目", bg=BG, fg=TEXT, font=F, anchor="e", width=11).grid(
            row=n, column=0, sticky="e", padx=(0, px(10)), pady=px(4))
        ent = tk.Entry(form, font=F, bg=SURFACE_HI, fg=TEXT, insertbackground=TEXT, relief="flat",
                       highlightthickness=1, highlightbackground=ui.LINE_HI, highlightcolor=ACCENT)
        ent.insert(0, "银行存款")
        ent.grid(row=n, column=1, sticky="ew", pady=px(4), ipady=px(5))
        form.columnconfigure(1, weight=1)
        result = {}

        def ok():
            cm = {k: b.get() for k, b in boxes.items() if b.get()}
            miss = [lab for k, lab, req, _ in loaders.JOURNAL_FIELDS if req and k not in cm]
            if miss:
                messagebox.showwarning("还没选完", "必选列未指定：" + "、".join(miss), parent=dlg)
                return
            result["v"] = (cm, ent.get().strip() or "银行存款")
            dlg.destroy()
        foot = tk.Frame(dlg, bg=BG)
        foot.pack(fill="x", padx=px(24), pady=px(18))
        ui.Btn(foot, "确定", ok, kind="primary").pack(side="right")
        ui.Btn(foot, "取消", dlg.destroy).pack(side="right", padx=(0, px(8)))
        self._show_dlg(dlg)
        dlg.grab_set()
        self.wait_window(dlg)
        return result.get("v")

    # ---------- 流水文件 → 账户 ----------
    def _build_index(self):
        """扫描流水文件并对到账户：self.fmap = {路径: (候选账户列表, 依据)}"""
        accts = list(self.cmb["values"])
        self.fmap = {}
        for p in loaders.list_statement_files([self.base] + self.stmt_dirs):
            self.fmap[p] = loaders.match_accounts(p, accts, self.map)
            if not self.fmap[p][0]:
                self.fmap[p] = self._match_by_balance(p)
        self._show_unassigned()

    def _match_by_balance(self, p):
        """文件里没有账号时的最后办法：流水的期初或期末余额，正好等于余额表里某一个户的期初/期末"""
        if not p.lower().endswith((".xlsx", ".xls", ".csv")):
            return [], ""
        try:
            rows = (loaders.load_statement(loaders.convert_xls(p)) if p.lower().endswith(".xls")
                    else loaders.load_statement_csv(p) if p.lower().endswith(".csv")
                    else loaders.load_statement(p))
            t = engine.tie_out([], rows)
        except Exception:
            return [], ""
        finally:
            loaders.WARNINGS.clear()
        beg, end = t["beg"][1], t["end"][1]
        hits = [a for a, (b0, _, _, b1) in self.balance.items()
                if (end is not None and end != 0 and end == b1) or (beg is not None and beg != 0 and beg == b0)]
        return (hits, "余额吻合") if len(hits) == 1 else ([], "")

    def _owner(self, p):
        """文件最终归属：手工指定优先；自动对应唯一候选才采用；有歧义或没对上返回 None"""
        if p in self.manual:
            return self.manual[p] or None
        c = self.fmap.get(p, ([], ""))[0]
        return c[0] if len(c) == 1 else None

    def _show_unassigned(self):
        n = sum(1 for p in self.fmap if p not in self.manual and len(self.fmap[p][0]) != 1)
        if n:
            self.status.config(text="%s｜有 %d 个文件没能自动对应账户，可点“流水文件对应”处理" % (
                self.status.cget("text").split("｜")[0], n))
            self._dot("warn")

    def _statement_for(self, acct):
        rows = []
        self._pdf_rows = 0
        for p, _ in self.fmap.items():
            if self._owner(p) != acct:
                continue
            f, low = os.path.basename(p), p.lower()
            try:
                if low.endswith(".xls"):
                    rows += loaders.load_statement(loaders.convert_xls(p))
                elif low.endswith(".csv"):
                    rows += loaders.load_statement_csv(p)
                elif low.endswith(".pdf"):
                    got = loaders.load_statement_pdf(p)
                    self._pdf_rows += len(got)
                    rows += got
                else:
                    rows += loaders.load_statement(p)
            except Exception as e:
                self._load_errors.append("%s：%s" % (f, str(e)[:40]))
        return rows

    def assign_files(self):
        """窗口：查看每个流水文件对到哪个账户，可手工改"""
        if not self.fmap:
            messagebox.showinfo("还没有文件", "请先选择客户文件夹")
            return
        accts = list(self.cmb["values"])
        NONE = "（不属于任何账户，忽略）"
        dlg = self._dlg("流水文件对应", 1020, 580)
        tk.Label(dlg, text="流水文件对应", bg=BG, fg=TEXT, font=F_H2).pack(anchor="w", padx=px(22), pady=(px(18), 0))
        tk.Label(dlg, text="选中文件，在下方选账户后点“设为”。红色 = 没对上或有歧义。",
                 bg=BG, fg=MUTED, font=F_S).pack(anchor="w", padx=px(22), pady=(px(2), px(10)))
        card = ui.Card(dlg, height=px(380))
        card.pack(fill="both", expand=True, padx=px(22))
        wrap = tk.Frame(card.body, bg=SURFACE)
        wrap.pack(fill="both", expand=True)
        tb = ttk.Treeview(wrap, columns=("f", "a", "h"), show="headings", selectmode="extended")
        for c, w, t in (("f", 470, "文件（相对路径）"), ("a", 330, "对应账户"), ("h", 90, "依据")):
            tb.heading(c, text=t, anchor="w")
            tb.column(c, width=px(w), anchor="w")
        tb.tag_configure("bad", foreground=BAD)
        sc = ttk.Scrollbar(wrap, orient="vertical", command=tb.yview)
        tb.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")
        tb.pack(side="left", fill="both", expand=True)
        paths = list(self.fmap)

        def refresh():
            tb.delete(*tb.get_children())
            for i, p in enumerate(paths):
                if p in self.manual:
                    a, h = (self.manual[p] or NONE), "手工"
                else:
                    c, h = self.fmap[p]
                    a = c[0] if len(c) == 1 else ("、".join(x[-12:] for x in c) + "（歧义）" if c else "")
                bad = self._owner(p) is None and not (p in self.manual)
                base = self.base if p.startswith(self.base) else os.path.dirname(p)
                tb.insert("", "end", iid=str(i), values=(os.path.relpath(p, base), a, h),
                          tags=("bad",) if bad else ())
        refresh()
        bar = tk.Frame(dlg, bg=BG)
        bar.pack(fill="x", padx=px(22), pady=px(16))
        cb = ttk.Combobox(bar, values=accts + [NONE], state="readonly", width=52, font=F)
        cb.pack(side="left", ipady=px(3))

        def setit():
            v = cb.get()
            if not v:
                return
            for iid in tb.selection():
                self.manual[paths[int(iid)]] = "" if v == NONE else v
            refresh()

        def reset():
            for iid in tb.selection():
                self.manual.pop(paths[int(iid)], None)
            refresh()

        def done():
            dlg.destroy()
            self.status.config(text=self.status.cget("text").split("｜")[0])
            self._dot("ok")
            self._show_unassigned()
            if self.cmb.get():
                self.run()
        ui.Btn(bar, "设为", setit, kind="primary", padx=22).pack(side="left", padx=(px(10), px(6)))
        ui.Btn(bar, "恢复自动", reset).pack(side="left")
        ui.Btn(bar, "完成并重新核对", done, kind="primary").pack(side="right")
        self._show_dlg(dlg)

    def run(self):
        acct = self.cmb.get()
        if not acct:
            return
        for w in self.box.winfo_children():
            w.destroy()
        bk = [x for x in self.journal if x.get("account") == acct]
        self._load_errors = []
        loaders.WARNINGS.clear()
        try:
            st = self._statement_for(acct)
        except Exception as e:
            messagebox.showerror("读取流水失败", "账户：%s\n%s\n\n可尝试：确认该账户的流水文件能正常打开。" % (acct, e))
            return
        notes = list(loaders.WARNINGS) + list(self._load_errors)
        notes += ["%s 前后余额接不上（差 %s），流水可能缺了一笔" % (d, "{:,.2f}".format(g))
                  for d, g in engine.chain_breaks(st)]
        if notes:
            messagebox.showwarning("流水读取提示", "账户：%s\n%s%s" % (
                acct, "\n".join(notes[:8]), "\n…共 %d 条" % len(notes) if len(notes) > 8 else ""))
        if not st:
            self.btn_export.config(state="disabled")
            self._empty("这个账户没有可读的流水",
                        "可能没有对应的流水文件，或流水是扫描件 / PDF，需要向客户要电子版（Excel / CSV）\n"
                        "也可以点右上角“流水文件对应…”看文件有没有对上", WARN, "!")
            self.status.config(text="本户没有可读的流水")
            self._dot("warn")
            return
        # 自检：PDF 解析量明显偏少时提示，避免“残数据当真结果”
        if getattr(self, "_pdf_rows", 0) and bk:
            if len(st) < len(bk) * 0.5:
                if not messagebox.askokcancel(
                        "数据可能不完整",
                        "该账户流水来自 PDF，只解析出 %d 笔，账面有 %d 笔。\n\n"
                        "可能原因：扫描件或版式不支持。\n确定要继续核对吗？"
                        % (len(st), len(bk))):
                    return
            else:
                try:
                    b_amt = sum(abs(float(x.get("dr") or 0)) + abs(float(x.get("cr") or 0)) for x in bk)
                    s_amt = sum(abs(float(x.get("inn") or 0)) + abs(float(x.get("out") or 0)) for x in st)
                    if b_amt and abs(b_amt - s_amt) / b_amt > 0.5:
                        if not messagebox.askokcancel(
                                "金额差异过大",
                                "PDF 解析出的流水合计 %.0f，账面合计 %.0f，差异超过 50%%。\n\n"
                                "请确认 PDF 是否完整。继续核对吗？" % (s_amt, b_amt)):
                            return
                except Exception:
                    pass
        try:
            t = engine.tie_out(bk, st)
            g, ub, us = engine.match(bk, st)
            us = us + engine.netted_returns(g)       # 夹在汇总组里的同日退回，也要列示，差额才对得上
        except Exception as e:
            messagebox.showerror("核对失败", "账户：%s\n%s" % (acct, e))
            return
        self._last = dict(acct=acct, book=bk, stmt=st, tie=t, groups=g, ub=ub, us=us)
        self.btn_export.config(state="normal")
        self._render(acct, bk, st, t, g, ub, us)

    def export(self):
        d = getattr(self, "_last", None)
        if not d:
            return
        path = filedialog.asksaveasfilename(
            title="保存底稿", defaultextension=".xlsx",
            initialfile="ZA-013 流水核对.xlsx",
            filetypes=[("Excel 工作簿", "*.xlsx")])
        if not path:
            return
        try:
            exporter.export(path, os.path.basename(self.base or ""), d["acct"],
                            d["book"], d["stmt"], d["groups"], d["ub"], d["us"], d["tie"],
                            bal=self.balance.get(d["acct"]))
            messagebox.showinfo("已生成", "底稿已保存：\n%s" % path)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _render(self, acct, bk, st, t, g, ub, us):
        fm = "{:,.2f}".format
        beg_b, _, _, end_b = self.balance.get(acct, (None, None, None, None))
        items = [
            ("借方（收入）", t["dr"][0], t["dr"][1]),
            ("贷方（支出）", t["cr"][0], t["cr"][1]),
            ("期初", beg_b, t["beg"][1]),
            ("期末", end_b, t["end"][1]),
        ]
        diffs = [(b - s) if (b is not None and s is not None) else None for _, b, s in items]
        all_ok = all(d == 0 for d in diffs if d is not None)

        # 标题行：账户名 + 总体结论 + 匹配统计
        top = tk.Frame(self.box, bg=BG)
        top.pack(fill="x", pady=(px(6), px(12)))
        tk.Label(top, text=acct, bg=BG, fg=TEXT, font=F_H1).pack(side="left")
        ui.badge(top, "✓ 四项相符" if all_ok else "存在差异", OK if all_ok else BAD).pack(side="left", padx=(px(12), 0))
        tk.Label(top, text="匹配 %d 组（1:1 %d / 拆分 %d）" % (
            len(g), sum(1 for x in g if x[3] == "1:1"), sum(1 for x in g if x[3] != "1:1")),
            bg=BG, fg=MUTED, font=F_S).pack(side="right")

        # 四项勾稽：四张卡片
        grid = tk.Frame(self.box, bg=BG)
        grid.pack(fill="x")
        for i, ((name, b, s), diff) in enumerate(zip(items, diffs)):
            ok = (diff == 0) if diff is not None else None
            card = ui.Card(grid, height=px(122), outline=(BAD_LINE if ok is False else LINE))
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else px(10), 0))
            grid.columnconfigure(i, weight=1, uniform="kpi")
            bd = card.body
            tk.Label(bd, text=name, bg=SURFACE, fg=MUTED, font=F_S).pack(anchor="w")
            for lab, val in (("账面", b), ("流水", s)):
                r = tk.Frame(bd, bg=SURFACE)
                r.pack(fill="x", pady=(px(3), 0))
                tk.Label(r, text=lab, bg=SURFACE, fg=MUTED, font=F_S).pack(side="left")
                tk.Label(r, text=fm(val) if val is not None else "—", bg=SURFACE,
                         fg=TEXT if val is not None else MUTED, font=F_MONO).pack(side="right")
            if ok:
                tk.Label(bd, text="✓ 相符", bg=SURFACE, fg=OK, font=F_B).pack(anchor="w", pady=(px(4), 0))
            elif ok is False:
                tk.Label(bd, text="✗ 差 %s" % fm(diff), bg=SURFACE, fg=BAD, font=F_B).pack(anchor="w", pady=(px(4), 0))
            else:
                tk.Label(bd, text="— 不勾稽", bg=SURFACE, fg=MUTED, font=F_S).pack(anchor="w", pady=(px(5), 0))

        # 差额说明：借方、贷方分开，看列示的差异能不能解释差额
        expl = tk.Frame(self.box, bg=BG)
        expl.pack(fill="x", pady=(px(14), px(2)))
        try:
            for name, bi, si, bk_, sk_ in (("借方（收入）", t["dr"][0], t["dr"][1], "dr", "inn"),
                                           ("贷方（支出）", t["cr"][0], t["cr"][1], "cr", "out")):
                diff = bi - si                                   # 账面 − 流水
                a = sum((y[bk_] for y in ub), D(0))              # 账面有流水无
                b = sum((y[sk_] for y in us), D(0))              # 流水有账面无
                left = diff - (a - b)
                if diff == 0 and a == 0 and b == 0:
                    txt, fg = "%s：账面与流水一致" % name, OK
                elif left == 0:
                    txt, fg = ("%s：差额 %s = 账面有流水无 %s − 流水有账面无 %s，差异已全部列示"
                               % (name, fm(diff), fm(a), fm(b))), WARN
                else:
                    txt, fg = ("%s：差额 %s，列示的差异只解释 %s，另有 %s 未列示"
                               % (name, fm(diff), fm(a - b), fm(left))), BAD
                line = tk.Frame(expl, bg=BG)
                line.pack(fill="x", pady=px(1))
                tk.Label(line, text="●", bg=BG, fg=fg, font=F_S).pack(side="left")
                tk.Label(line, text=txt, bg=BG, fg=TEXT, font=F, anchor="w").pack(side="left", padx=(px(8), 0))
        except Exception:
            pass

        # 差异明细
        card = ui.Card(self.box)
        card.pack(fill="both", expand=True, pady=(px(10), px(12)))
        bd = card.body
        if us or ub:
            hdr = tk.Frame(bd, bg=SURFACE)
            hdr.pack(fill="x", pady=(0, px(8)))
            tk.Label(hdr, text="差异明细", bg=SURFACE, fg=TEXT, font=F_H2).pack(side="left")
            tk.Label(hdr, text="账面有流水无 %d 笔 · 流水有账面无 %d 笔" % (len(ub), len(us)),
                     bg=SURFACE, fg=MUTED, font=F_S).pack(side="left", padx=(px(12), 0), pady=(px(3), 0))
            wrap = tk.Frame(bd, bg=SURFACE)
            wrap.pack(fill="both", expand=True)
            tb = ttk.Treeview(wrap, columns=("side", "d", "amt", "cp", "kind"), show="headings", selectmode="browse")
            for c, w, txt, an in (("side", 120, "类别", "w"), ("d", 100, "日期", "w"),
                                  ("amt", 170, "金额（收入+ / 支出-）", "e"),
                                  ("cp", 380, "对方 / 摘要", "w"), ("kind", 170, "归类", "w")):
                tb.heading(c, text=txt, anchor=an)
                tb.column(c, width=px(w), anchor=an, stretch=(c == "cp"))
            sc = ttk.Scrollbar(wrap, orient="vertical", command=tb.yview)
            tb.configure(yscrollcommand=sc.set)
            sc.pack(side="right", fill="y")
            tb.pack(side="left", fill="both", expand=True)
            tb.tag_configure("book", foreground=BAD)
            tb.tag_configure("odd", background="#1a1a20")
            n = [0]

            def add(vals, tag=None):
                tags = ((tag,) if tag else ()) + (("odd",) if n[0] % 2 else ())
                tb.insert("", "end", values=vals, tags=tags)
                n[0] += 1
            for x in ub:                      # 账面有、流水无：差异的主要来源，排在最前面
                amt = x["dr"] if x["dr"] > 0 else -x["cr"]
                add(("账面有流水无", str(x["date"]), fm(amt),
                     "%s %s" % (x.get("vou", ""), str(x.get("memo", ""))[:30]), engine.classify(x, is_book=True)), "book")
            # 同额双向进出 → 过账/内部划转
            thru = set()
            for i in range(len(us)):
                for j in range(i + 1, len(us)):
                    a, b = us[i], us[j]
                    if (a["date"] == b["date"] and a["inn"] > 0 and b["out"] > 0
                            and a["inn"] == b["out"]):
                        thru.add(i); thru.add(j)
            for k, y in enumerate(us[:500]):
                amt = y["inn"] if y["inn"] > 0 else -y["out"]
                kind = y.get("note") or ("过账/内部划转" if k in thru else engine.classify(y, is_book=False))
                add(("流水有账面无", str(y["date"]), fm(amt), y.get("cp", "") or y.get("memo", ""), kind))
        else:
            tk.Label(bd, text="✓", bg=SURFACE, fg=OK, font=(YAHEI, 22, "bold")).pack(pady=(px(14), 0))
            tk.Label(bd, text="没有差异", bg=SURFACE, fg=TEXT, font=F_H2).pack()
            tk.Label(bd, text="账面分录和流水逐笔都对上了", bg=SURFACE, fg=MUTED, font=F).pack(pady=(px(4), 0))
        self.status.config(text="本户核对完成：%s" % ("四项相符" if all_ok else "存在差异"))
        self._dot("ok" if all_ok else "bad")


if __name__ == "__main__":
    ui.enable_dpi()
    App().mainloop()
