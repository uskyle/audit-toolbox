# -*- coding: utf-8 -*-
"""界面主题与控件。配色、字体取自网站（Obsidian 风：近黑底、单一紫色强调色、大圆角）。"""
import ctypes
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# ---------- 配色（与网站 style.css 一致） ----------
BG = "#0e0e11"
SURFACE = "#16161b"
SURFACE_HI = "#1c1c23"
TEXT = "#f0f0f4"
MUTED = "#9a9aa8"
LINE = "#26262f"
LINE_HI = "#3a3a46"
ACCENT = "#8b6cf6"
ACCENT_HI = "#9d83f8"
ACCENT_DEEP = "#5b3fd6"
ACCENT_SOFT = "#2a2347"      # 紫色 14% 叠在深色底上的实色
OK = "#5fd08a"
BAD = "#ff7b7b"
BAD_LINE = "#5a2a30"
WARN = "#e6b43c"

YAHEI = "Microsoft YaHei UI"
F = (YAHEI, 10)
F_S = (YAHEI, 9)
F_B = (YAHEI, 10, "bold")
F_H1 = (YAHEI, 15, "bold")
F_H2 = (YAHEI, 11, "bold")
F_MONO = ("Consolas", 12, "bold")
F_MONO_S = ("Consolas", 10)

SCALE = 1.0


def px(n):
    return max(1, int(round(n * SCALE)))


def enable_dpi():
    """让 Windows 不要把窗口放大后再模糊，文字更清晰（必须在创建窗口之前调用）"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def init_scale(root):
    global SCALE
    try:
        SCALE = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except Exception:
        SCALE = 1.0


def dark_titlebar(win):
    """Windows 10/11 深色标题栏"""
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        val = ctypes.c_int(1)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def apply_style(root):
    """ttk 控件（下拉框、表格、滚动条）的深色样式"""
    root.configure(bg=BG)
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    st.configure("TCombobox", fieldbackground=SURFACE_HI, background=SURFACE_HI, foreground=TEXT,
                 arrowcolor=MUTED, bordercolor=LINE_HI, lightcolor=LINE_HI, darkcolor=LINE_HI,
                 selectbackground=SURFACE_HI, selectforeground=TEXT, padding=px(6), arrowsize=px(14))
    st.map("TCombobox",
           fieldbackground=[("readonly", SURFACE_HI), ("disabled", SURFACE)],
           foreground=[("readonly", TEXT), ("disabled", MUTED)],
           bordercolor=[("focus", ACCENT), ("hover", MUTED)],
           arrowcolor=[("hover", TEXT)])
    root.option_add("*TCombobox*Listbox.background", SURFACE_HI)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", F)
    root.option_add("*TCombobox*Listbox.borderWidth", 0)

    st.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                 bordercolor=SURFACE, borderwidth=0, rowheight=px(30), font=F, relief="flat")
    st.map("Treeview", background=[("selected", ACCENT_SOFT)], foreground=[("selected", "#ffffff")])
    st.configure("Treeview.Heading", background=SURFACE_HI, foreground=MUTED, relief="flat",
                 borderwidth=0, font=F_B, padding=(px(8), px(7)))
    st.map("Treeview.Heading", background=[("active", LINE)], foreground=[("active", TEXT)])
    st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    st.configure("Vertical.TScrollbar", troughcolor=SURFACE, background=LINE_HI, bordercolor=SURFACE,
                 arrowcolor=MUTED, lightcolor=LINE_HI, darkcolor=LINE_HI, gripcount=0, arrowsize=px(12),
                 relief="flat")
    st.map("Vertical.TScrollbar", background=[("active", MUTED)])


def round_rect(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


# ---------- 圆角按钮 ----------
class Btn(tk.Canvas):
    KINDS = {
        # 填充, 悬停填充, 文字, 边框, 悬停边框
        "primary": (ACCENT, ACCENT_HI, "#ffffff", ACCENT, ACCENT_HI),
        "ghost": (SURFACE, SURFACE_HI, TEXT, LINE_HI, MUTED),
    }

    def __init__(self, master, text, command=None, kind="ghost", state="normal", bg=BG,
                 font=F_B, padx=18, height=34):
        self._text, self._cmd, self._kind, self._state = text, command, kind, state
        self._font = font
        self._tf = tkfont.Font(font=font)
        self._h = px(height)
        self._padx = px(padx)
        super().__init__(master, width=self._tf.measure(text) + 2 * self._padx, height=self._h,
                         bg=bg, highlightthickness=0, bd=0)
        self._hover = False
        self._down = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = int(self.cget("width")), self._h
        fill, hfill, fg, line, hline = self.KINDS[self._kind]
        if self._state == "disabled":
            fill, line, fg = SURFACE, LINE, "#5d5d6b"
            self.configure(cursor="arrow")
        else:
            self.configure(cursor="hand2")
            if self._hover:
                fill, line = hfill, hline
            if self._down:
                fill = ACCENT_DEEP if self._kind == "primary" else LINE
        round_rect(self, 1, 1, w - 1, h - 1, px(9), fill=fill, outline=line)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)

    def _enter(self, _):
        self._hover = True
        self._draw()

    def _leave(self, _):
        self._hover = False
        self._down = False
        self._draw()

    def _press(self, _):
        if self._state != "disabled":
            self._down = True
            self._draw()

    def _release(self, e):
        was = self._down
        self._down = False
        self._draw()
        if was and self._state != "disabled" and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            if self._cmd:
                self._cmd()

    def configure(self, cnf=None, **kw):
        redraw = False
        if "state" in kw:
            self._state = kw.pop("state")
            redraw = True
        if "text" in kw:
            self._text = kw.pop("text")
            kw["width"] = self._tf.measure(self._text) + 2 * self._padx
            redraw = True
        if "command" in kw:
            self._cmd = kw.pop("command")
        r = super().configure(cnf, **kw) if (kw or cnf) else None
        if redraw:
            self._draw()
        return r

    config = configure


# ---------- 圆角卡片 ----------
class Card(tk.Canvas):
    """圆角卡片：内容放进 .body（一个 Frame）"""

    def __init__(self, master, bg=BG, fill=SURFACE, outline=LINE, radius=14, pad=14, **kw):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, **kw)
        self._fill, self._outline, self._r, self._pad = fill, outline, px(radius), px(pad)
        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(self._pad, self._pad, window=self.body, anchor="nw")
        self.bind("<Configure>", self._redraw)

    def _redraw(self, e=None):
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("bg")
        round_rect(self, 1, 1, w - 1, h - 1, self._r, fill=self._fill, outline=self._outline, tags="bg")
        self.tag_lower("bg")
        self.itemconfigure(self._win, width=max(1, w - 2 * self._pad), height=max(1, h - 2 * self._pad))

    def set_outline(self, color):
        self._outline = color
        self._redraw()


def badge(master, text, color, bg=BG, font=F_S):
    """胶囊标签：细边框 + 彩色文字"""
    tf = tkfont.Font(font=font)
    w, h = tf.measure(text) + px(22), px(24)
    cv = tk.Canvas(master, width=w, height=h, bg=bg, highlightthickness=0, bd=0)
    round_rect(cv, 1, 1, w - 1, h - 1, h // 2, fill=bg, outline=color)
    cv.create_text(w / 2, h / 2, text=text, fill=color, font=font)
    return cv


def logo(master, size=26, bg=BG):
    """与网站左上角一致的渐变圆角方块"""
    s = px(size)
    cv = tk.Canvas(master, width=s, height=s, bg=bg, highlightthickness=0, bd=0)
    r = int(s * 0.3)
    round_rect(cv, 0, 0, s - 1, s - 1, r, fill=ACCENT_DEEP, outline=ACCENT_DEEP)
    round_rect(cv, 1, 1, s - 3, s - 3, r, fill=ACCENT, outline=ACCENT)
    round_rect(cv, 3, 3, int(s * 0.62), int(s * 0.62), int(r * 0.7), fill=ACCENT_HI, outline=ACCENT_HI)
    return cv


# ---------- 深色弹窗（替代系统白色弹窗，接口与 tkinter.messagebox 一致） ----------
class _MB:
    ICONS = {"info": (ACCENT, "i"), "warn": (WARN, "!"), "error": (BAD, "×"), "ask": (ACCENT, "?")}

    def _show(self, title, message, kind, parent=None, ask=False):
        root = parent or tk._default_root
        dlg = tk.Toplevel(root)
        dlg.withdraw()
        dlg.title(title)
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        try:
            dlg.transient(root)
        except Exception:
            pass
        result = {"v": None if not ask else False}

        def close(v):
            result["v"] = v
            dlg.destroy()
        body = tk.Frame(dlg, bg=BG)
        body.pack(fill="both", expand=True, padx=px(22), pady=(px(20), px(8)))
        color, glyph = self.ICONS[kind]
        ic = tk.Canvas(body, width=px(34), height=px(34), bg=BG, highlightthickness=0, bd=0)
        ic.create_oval(1, 1, px(34) - 1, px(34) - 1, fill=SURFACE_HI, outline=color)
        ic.create_text(px(17), px(17), text=glyph, fill=color, font=(YAHEI, 13, "bold"))
        ic.pack(side="left", anchor="n", padx=(0, px(14)))
        col = tk.Frame(body, bg=BG)
        col.pack(side="left", fill="both", expand=True)
        tk.Label(col, text=title, bg=BG, fg=TEXT, font=F_H2, anchor="w").pack(anchor="w")
        tk.Label(col, text=message, bg=BG, fg=MUTED, font=F, justify="left", anchor="w",
                 wraplength=px(460)).pack(anchor="w", pady=(px(8), 0))
        bar = tk.Frame(dlg, bg=BG)
        bar.pack(fill="x", padx=px(22), pady=(px(10), px(18)))
        if ask:
            Btn(bar, "取消", lambda: close(False), kind="ghost").pack(side="right", padx=(px(8), 0))
            Btn(bar, "确定", lambda: close(True), kind="primary").pack(side="right")
        else:
            Btn(bar, "确定", lambda: close(None), kind="primary").pack(side="right")
        dlg.protocol("WM_DELETE_WINDOW", lambda: close(False if ask else None))
        dlg.bind("<Escape>", lambda e: close(False if ask else None))
        dlg.update_idletasks()
        try:
            x = root.winfo_rootx() + (root.winfo_width() - dlg.winfo_reqwidth()) // 2
            y = root.winfo_rooty() + (root.winfo_height() - dlg.winfo_reqheight()) // 3
            dlg.geometry("+%d+%d" % (max(0, x), max(0, y)))
        except Exception:
            pass
        dlg.deiconify()
        dark_titlebar(dlg)
        try:
            dlg.grab_set()
            dlg.focus_force()
        except Exception:
            pass
        dlg.wait_window()
        return result["v"]

    def showinfo(self, title, message, parent=None, **kw):
        return self._show(title, message, "info", parent)

    def showwarning(self, title, message, parent=None, **kw):
        return self._show(title, message, "warn", parent)

    def showerror(self, title, message, parent=None, **kw):
        return self._show(title, message, "error", parent)

    def askokcancel(self, title, message, parent=None, **kw):
        return self._show(title, message, "ask", parent, ask=True)


MB = _MB()
