# -*- coding: utf-8 -*-
"""PDF 压缩工具 —— 扫描件重采样 + JPEG 重编码；输出镜像原目录结构"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pypdfium2 as pdfium
from PIL import Image, ImageChops

FONT = ("Microsoft YaHei UI", 10)
FONT_B = ("Microsoft YaHei UI", 11, "bold")

PRESETS = {
    "清晰（200 dpi，推荐）": (200, 75),
    "标准（150 dpi）": (150, 70),
    "最小（120 dpi）": (120, 65),
}


def is_text_pdf(pdf, min_chars=120):
    chars = 0
    for i in range(len(pdf)):
        chars += len(pdf[i].get_textpage().get_text_range().strip())
        if chars >= min_chars:
            return True
    return False


def compress_pdf(src, dst, dpi=200, quality=75, force_text=False):
    pdf = pdfium.PdfDocument(src)
    if not force_text and is_text_pdf(pdf):
        raise ValueError("带文字层的PDF（含OCR扫描件），压缩会丢失文字层，已跳过；如需压缩请勾选“带文字层也压缩”")
    if len(pdf) == 0:
        raise ValueError("空 PDF")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    old = os.path.getsize(src)
    # 原文件可能本身已很省（低分辨率/黑白），按所选档位压反而变大；
    # 所以逐级降低分辨率、质量重试，直到明显变小
    ladder = [(dpi, quality), (min(dpi, 150), min(quality, 65)),
              (min(dpi, 120), min(quality, 55)), (min(dpi, 100), min(quality, 45)),
              (min(dpi, 80), min(quality, 40))]
    tried, best = set(), None
    tmp = dst + ".tmp"
    for d, q in ladder:
        if (d, q) in tried:
            continue
        tried.add((d, q))
        pages = [_to_gray_if_gray(pdf[i].render(scale=d / 72.0).to_pil()) for i in range(len(pdf))]
        pages[0].save(tmp, "PDF", resolution=float(d), save_all=True,
                      append_images=pages[1:], quality=q, optimize=True)
        new = os.path.getsize(tmp)
        if best is None or new < best[0]:
            best = (new, d, q)
        if new < old * 0.95:
            os.replace(tmp, dst)
            return old, new
    if os.path.exists(tmp):
        os.remove(tmp)
    raise ValueError("原文件已经很小，最低档（%d dpi）压后仍为 %.2f MB（原 %.2f MB），保留原文件"
                     % (best[1], best[0] / 1048576, old / 1048576))


def _to_gray_if_gray(im):
    """黑白/灰度扫描件存成灰度图，体积约为彩色的 1/3"""
    rgb = im.convert("RGB")
    small = rgb.resize((max(1, rgb.width // 8), max(1, rgb.height // 8)))
    r, g, b = small.split()
    if max(ImageChops.difference(r, g).getextrema()[1], ImageChops.difference(g, b).getextrema()[1]) < 24:
        return rgb.convert("L")
    return rgb


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF 压缩工具")
        self.geometry("900x560")
        self.files = []
        self.root_dir = ""    # 选文件夹时的根目录，用于计算相对结构
        self.out_root = ""    # 镜像输出根目录
        self._build()

    # ---------- 界面 ----------
    def _build(self):
        top = tk.Frame(self, padx=12, pady=10)
        top.pack(fill="x")
        tk.Button(top, text="① 选择 PDF 文件", font=FONT, command=self.pick_files).pack(side="left")
        tk.Button(top, text="选择文件夹", font=FONT, command=self.pick_dir).pack(side="left", padx=8)
        tk.Label(top, text="② 压缩质量：", font=FONT).pack(side="left", padx=(16, 0))
        self.quality = ttk.Combobox(top, width=22, state="readonly", font=FONT, values=list(PRESETS))
        self.quality.current(0)
        self.quality.pack(side="left")
        tk.Button(top, text="③ 开始压缩", font=FONT, command=self.start).pack(side="left", padx=12)
        tk.Button(top, text="移除选中", font=FONT, command=self.remove_selected).pack(side="left")
        self.force_text = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="带文字层也压缩", variable=self.force_text, font=FONT).pack(side="left", padx=8)

        mid = tk.Frame(self, padx=12)
        mid.pack(fill="x", pady=(0, 6))
        tk.Label(mid, text="输出到：", font=FONT).pack(side="left")
        self.lbl_out = tk.Label(mid, text="（未选择）", fg="#666", font=FONT, anchor="w")
        self.lbl_out.pack(side="left", fill="x", expand=True)
        tk.Button(mid, text="更改输出位置", font=FONT, command=self.choose_output).pack(side="left")

        self.lst = ttk.Treeview(self, columns=("name", "old", "new", "rate"), show="headings", height=14)
        for c, w, t in (("name", 300, "文件（相对源文件夹）"), ("old", 80, "原大小"),
                        ("new", 80, "压缩后"), ("rate", 330, "比例 / 跳过原因")):
            self.lst.heading(c, text=t)
            self.lst.column(c, width=w, anchor="w")
        self.lst.pack(fill="both", expand=True, padx=12)

        self.bar = ttk.Progressbar(self, mode="determinate")
        self.bar.pack(fill="x", padx=12, pady=(8, 0))
        self.status = tk.Label(self, text="选择文件后开始", anchor="w", padx=12, pady=6, fg="#555", font=FONT)
        self.status.pack(fill="x", side="bottom")
        tk.Label(self, text="说明：扫描件重采样为图片；文字版 PDF 自动跳过；原文件不会被修改或删除。",
                 anchor="w", padx=12, fg="#888", font=("Microsoft YaHei UI", 9)).pack(fill="x", side="bottom")

    # ---------- 选择 ----------
    def pick_files(self):
        fs = filedialog.askopenfilenames(title="选择 PDF", filetypes=[("PDF 文件", "*.pdf")])
        if not fs:
            return
        self.files = list(fs)
        self.root_dir = ""
        self.out_root = os.path.join(os.path.dirname(fs[0]), "压缩后")
        self._show_out()
        self._fill()

    def pick_dir(self):
        d = filedialog.askdirectory(title="选择包含 PDF 的文件夹（会扫描所有子文件夹）")
        if not d:
            return
        found = []
        for root, _, files in os.walk(d):
            for f in sorted(files):
                if f.lower().endswith(".pdf") and not f.endswith("_压缩.pdf"):
                    found.append(os.path.join(root, f))
        if not found:
            messagebox.showinfo("提示", "这个文件夹里没有找到 PDF 文件")
            return
        self.root_dir = d
        self.files = found
        self.out_root = os.path.join(os.path.dirname(d), os.path.basename(d) + "_压缩")
        self._show_out()
        self._fill()
        self.status.config(text="在 %d 个文件夹中找到 %d 个 PDF，输出结构与原文件夹一致"
                           % (len({os.path.dirname(f) for f in found}), len(found)))

    def choose_output(self):
        d = filedialog.askdirectory(title="选择输出文件夹")
        if d:
            self.out_root = d
            self._show_out()

    def _show_out(self):
        self.lbl_out.config(text=self.out_root or "（未选择）")

    def _fill(self):
        self.lst.delete(*self.lst.get_children())
        for f in self.files:
            name = os.path.basename(f)
            if self.root_dir:
                rel = os.path.relpath(os.path.dirname(f), self.root_dir)
                if rel not in (".", ""):
                    name = rel + "\\" + name
            self.lst.insert("", "end", values=(name, "%.2f MB" % (os.path.getsize(f) / 1048576), "", ""))
        self.status.config(text="已选择 %d 个文件（选中后点“移除选中”可去掉）" % len(self.files))

    def remove_selected(self):
        sel = sorted(self.lst.selection(), key=lambda i: self.lst.index(i), reverse=True)
        if not sel:
            messagebox.showinfo("提示", "先在列表里选中要去掉的文件（可按住 Ctrl 多选）")
            return
        for i in sel:
            self.files.pop(self.lst.index(i))
            self.lst.delete(i)
        self.status.config(text="已移除 %d 个，剩余 %d 个待压缩" % (len(sel), len(self.files)))

    # ---------- 压缩 ----------
    def start(self):
        if not self.files:
            messagebox.showinfo("提示", "请先选择 PDF 文件")
            return
        if not self.out_root:
            self.choose_output()
            if not self.out_root:
                return
        dpi, q = PRESETS[self.quality.get()]
        self.bar["maximum"] = len(self.files)
        self.bar["value"] = 0
        threading.Thread(target=self._run, args=(dpi, q, self.force_text.get()), daemon=True).start()

    def _dest(self, src):
        stem = os.path.basename(src)[:-4]
        base = (stem if stem.endswith("_压缩") else stem + "_压缩") + ".pdf"
        if self.root_dir:
            rel = os.path.relpath(os.path.dirname(src), self.root_dir)
            d = self.out_root if rel in (".", "") else os.path.join(self.out_root, rel)
        else:
            d = self.out_root
        return os.path.join(d, base)

    def _run(self, dpi, q, force_text=False):
        old_sum = new_sum = skipped = 0
        reasons = {}
        for i, f in enumerate(self.files):
            self.after(0, self.status.config, {"text": "正在压缩（%d/%d）：%s" % (i + 1, len(self.files), os.path.basename(f))})
            try:
                old, new = compress_pdf(f, self._dest(f), dpi, q, force_text)
                old_sum += old
                new_sum += new
                self.after(0, self._row, i, new, new / old * 100)
            except Exception as e:
                skipped += 1
                reason = str(e) or e.__class__.__name__
                reasons[reason] = reasons.get(reason, 0) + 1
                self.after(0, self._row, i, None, None, reason)
            self.after(0, self.bar.config, {"value": i + 1})
        self.after(0, self._finish, old_sum, new_sum, skipped, reasons)

    def _finish(self, old_sum, new_sum, skipped, reasons):
        ok = len(self.files) - skipped
        msg = "完成：成功 %d 个，跳过 %d 个" % (ok, skipped)
        if ok:
            msg += "；%.1f MB → %.1f MB（省 %.0f%%）" % (
                old_sum / 1048576, new_sum / 1048576, (1 - new_sum / old_sum) * 100)
        self.status.config(text=msg + "　输出：" + self.out_root)
        detail = "".join("\n· %d 个：%s" % (n, r) for r, n in reasons.items())
        messagebox.showinfo("压缩完成", msg + ("\n\n跳过原因：" + detail if detail else "")
                            + "\n\n输出位置：\n" + self.out_root)

    def _row(self, idx, new, rate, err=None):
        item = self.lst.get_children()[idx]
        vals = list(self.lst.item(item, "values"))
        if err:
            vals[2], vals[3] = "跳过", err
        else:
            vals[2] = "%.2f MB" % (new / 1048576)
            vals[3] = "%.0f%%" % rate
        self.lst.item(item, values=vals)


if __name__ == "__main__":
    App().mainloop()