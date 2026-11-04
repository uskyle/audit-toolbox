# -*- coding: utf-8 -*-
"""底稿导出：按 ZA-013 版式生成单户核对结果"""
import os
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side

from engine import judge_five, guess_unit, scope_tag
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.page import PageMargins

D = Decimal
FN = "Arial Narrow"
THIN = Side(style="thin")
HAIR = Side(style="hair")
F_T = Font(name="宋体", size=14, bold=True)
F_H = Font(name=FN, size=10, bold=True)
F_B = Font(name=FN, size=10)
MONEY = '#,##0.00;[Red]-#,##0.00'


def _frame(ws, r1, c1, r2, c2):
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            ws.cell(row=r, column=c).border = Border(
                left=THIN if c == c1 else HAIR, right=THIN if c == c2 else HAIR,
                top=THIN if r == r1 else HAIR, bottom=THIN if r == r2 else HAIR)


def _setup(ws, title_rows, area, paper=8):
    ws.sheet_view.view = "normal"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = paper
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = title_rows
    ws.print_options.horizontalCentered = True
    ws.page_margins = PageMargins(left=0.25, right=0.25, top=0.4, bottom=0.4, header=0.2, footer=0.2)
    ws.oddFooter.right.text = "第 &P 页 / 共 &N 页"
    ws.oddFooter.right.size = 8
    ws.print_area = area


def export(out_path, entity, acct, book, stmt, groups, ub, us, tie, period="2026年1-9月", bal=None):
    """bal: 余额表 (期初, 借方, 贷方, 期末)，可空"""
    wb = openpyxl.Workbook()

    # ---------- 首页 ----------
    ws = wb.active
    ws.title = "首页"
    ws.merge_cells("A1:J1")
    c = ws["A1"]
    c.value = "%s %s 银行存款流水核对汇总表" % (entity, period)
    c.font = F_T
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26
    hdr = ["序号", "账户", "账面期初", "账面借方", "流水收入", "账面贷方", "流水支出",
           "账面期末", "流水期末", "核对结论"]
    for i, h in enumerate(hdr, 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.font = F_H
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    dr_b, dr_s = tie["dr"]
    cr_b, cr_s = tie["cr"]
    end_s = tie["end"][1]
    ok = (dr_b == dr_s) and (cr_b == cr_s)
    beg_book = float(bal[0]) if bal and bal[0] is not None else None
    end_book = float(bal[3]) if bal and bal[3] is not None else None
    vals = [1, acct, beg_book, float(dr_b), float(dr_s), float(cr_b), float(cr_s), end_book,
            float(end_s) if end_s is not None else None,
            "四项勾稽相符" if ok else "存在差异，见差异清单"]
    for j, v in enumerate(vals, 1):
        cell = ws.cell(row=3, column=j, value=v)
        cell.font = F_B
        if 3 <= j <= 9 and isinstance(v, (int, float)):
            cell.number_format = MONEY
        if j == 2:
            cell.alignment = Alignment(wrap_text=True, vertical="center")
    _frame(ws, 2, 1, 3, 10)
    for k, w in {"A": 5, "B": 52, "C": 15, "D": 15, "E": 15, "F": 15, "G": 15, "H": 15, "I": 15, "J": 26}.items():
        ws.column_dimensions[k].width = w
    _setup(ws, "2:2", "A1:J3")

    # ---------- 分户底稿 ----------
    ws = wb.create_sheet("核查底稿")
    ws.merge_cells("A1:N1")
    t = ws["A1"]
    t.value = "大额银行存款收支核查底稿"
    t.font = F_T
    t.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26
    ws.merge_cells("A2:N2")
    ws["A2"] = "被核查单位：%s    核查期间：%s    账户：%s" % (entity, period, acct)
    ws["A2"].font = F_B
    h2 = ["序号", "账面日期", "凭证号", "账面摘要", "账面对方单位", "借方", "贷方", "流水日期", "流水摘要",
          "流水借方", "流水贷方", "对方户名", "匹配", "备注",
          "①凭证与流水一致", "②对方单位核对", "③经济内容真实", "④会计期间", "⑤关联交易", "抽样归类"]
    for i, h in enumerate(h2, 1):
        cell = ws.cell(row=3, column=i, value=h)
        cell.font = F_H
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    r = 4
    stat = {}          # {标签: [笔数, 金额]}
    defects = 0
    for idx, (kind, bl, sl, typ) in enumerate(groups, 1):
        x = bl[0]
        y = sl[0]
        m_in = sum((D(str(k["out"])) for k in sl), D(0))
        m_out = sum((D(str(k["inn"])) for k in sl), D(0))
        note = "" if typ == "1:1" else ("账面1笔对应流水%d笔" % len(sl) if typ == "1:N" else typ)
        sp = x.get("splits") or []
        # 拆行金额合不上这笔银行分录时不拆，避免把对方分录的金额当成银行金额列示
        if sp and sum((D(str(s["amt"])) for s in sp), D(0)) != (D(str(x["dr"])) or D(str(x["cr"]))):
            sp = []
        unit = (str(sp[0]["unit"]) if sp else
                guess_unit(x.get("memo", ""), x.get("partner", ""), x.get("opp", "")))
        tag, rule = scope_tag(x, y, unit)
        five = judge_five(x, y, rel=x.get("rel"), book_name=unit or x.get("memo", ""),
                          stmt_name=y.get("cp", ""), date_gap=None)
        b_tot = sum((D(str(i.get("dr") or 0)) + D(str(i.get("cr") or 0)) for i in bl), D(0))
        s_tot = sum((D(str(i.get("inn") or 0)) + D(str(i.get("out") or 0)) for i in sl), D(0))
        if b_tot == s_tot:
            five["c1"] = "是"
        amt_all = float(D(str(x["dr"])) or D(str(x["cr"])))
        st = stat.setdefault(tag, [0, 0.0])
        st[0] += 1
        st[1] += amt_all
        if tag == "纳入抽样" and five["c2"] == "不一致":
            defects += 1

        parts = sp if len(sp) > 1 else [None]
        for k, part in enumerate(parts):
            first = (k == 0)
            if part:                                   # 按对方分录拆行
                amt = float(part["amt"])
                dr_cell = amt if float(x["dr"] or 0) > 0 else None
                cr_cell = amt if float(x["cr"] or 0) > 0 else None
                u = str(part["unit"])
                note_k = "同一凭证拆分：%s %s" % (u, "{:,.2f}".format(amt))
            else:
                dr_cell = float(x["dr"]) if x["dr"] else None
                cr_cell = float(x["cr"]) if x["cr"] else None
                u = unit
                note_k = note
            vals = [idx if first else "", str(x["date"]), x["vou"], str(x["memo"])[:50], u,
                    dr_cell, cr_cell,
                    (str(y["date"]) if first else None), (str(y["memo"])[:40] if first else None),
                    (float(m_in) if (first and m_in) else None), (float(m_out) if (first and m_out) else None),
                    (y.get("cp", "")[:30] if first else None), (typ if first else ""),
                    note_k, (five["c1"] if first else "同上"), (five["c2"] if first else "同上"),
                    (five["c3"] if first else "同上"), (five["c4"] if first else "同上"),
                    (five["c5"] if first else "同上"), tag]
            for j, v in enumerate(vals, 1):
                cell = ws.cell(row=r, column=j, value=v)
                cell.font = F_B
                if j in (6, 7, 10, 11) and isinstance(v, (int, float)):
                    cell.number_format = MONEY
            r += 1
    _frame(ws, 3, 1, r - 1, 20)
    ws.freeze_panes = "A4"
    for k, w in {"A": 5, "B": 11, "C": 9, "D": 38, "E": 26, "F": 14, "G": 14, "H": 11, "I": 28,
                 "J": 13, "K": 13, "J2": 1, "L": 26, "M": 8, "N": 24, "O": 11, "P": 13,
                 "Q": 11, "R": 11, "S": 11, "T": 16}.items():
        if k in ("J2",):
            continue
        ws.column_dimensions[k].width = w
    _setup(ws, "3:3", "A1:T%d" % (r - 1))

    # ---------- 未达 ----------
    ws = wb.create_sheet("差异清单")
    h3 = ["序号", "类别", "收支", "日期", "凭证号/对方", "摘要", "金额", "归类"]
    for i, h in enumerate(h3, 1):
        cell = ws.cell(row=1, column=i, value=h)
        cell.font = F_H
        cell.alignment = Alignment(horizontal="center")
    r = 2
    for x in ub:                                   # 账面有、流水无
        is_in = D(str(x["dr"])) > 0
        ws.cell(row=r, column=1, value=r - 1).font = F_B
        ws.cell(row=r, column=2, value="账面有流水无").font = F_B
        ws.cell(row=r, column=3, value="收入" if is_in else "支出").font = F_B
        ws.cell(row=r, column=4, value=str(x["date"])).font = F_B
        ws.cell(row=r, column=5, value=x["vou"]).font = F_B
        ws.cell(row=r, column=6, value=str(x["memo"])[:40]).font = F_B
        cell = ws.cell(row=r, column=7, value=float(D(str(x["dr"])) if is_in else D(str(x["cr"]))))
        cell.number_format = MONEY
        ws.cell(row=r, column=8, value="待确认").font = F_B
        r += 1
    for y in us:                                   # 流水有、账面无
        is_in = D(str(y["inn"])) > 0
        ws.cell(row=r, column=1, value=r - 1).font = F_B
        ws.cell(row=r, column=2, value="流水有账面无").font = F_B
        ws.cell(row=r, column=3, value="收入" if is_in else "支出").font = F_B
        ws.cell(row=r, column=4, value=str(y["date"])).font = F_B
        ws.cell(row=r, column=5, value=y.get("cp", "")).font = F_B
        ws.cell(row=r, column=6, value=str(y["memo"])[:40]).font = F_B
        cell = ws.cell(row=r, column=7, value=float(D(str(y["inn"])) if is_in else D(str(y["out"]))))
        cell.number_format = MONEY
        ws.cell(row=r, column=8, value=y.get("note", "")).font = F_B
        r += 1
    if r > 2:
        _frame(ws, 1, 1, r - 1, 8)
    # 合计：两类差异各自的收入/支出小计，对照借方/贷方差额
    r += 1
    sums = [("账面有流水无 · 收入", sum((D(str(x["dr"])) for x in ub), D(0))),
            ("账面有流水无 · 支出", sum((D(str(x["cr"])) for x in ub), D(0))),
            ("流水有账面无 · 收入", sum((D(str(y["inn"])) for y in us), D(0))),
            ("流水有账面无 · 支出", sum((D(str(y["out"])) for y in us), D(0))),
            ("借方（收入）差额 = 账面借方 − 流水收入", D(str(tie["dr"][0])) - D(str(tie["dr"][1]))),
            ("贷方（支出）差额 = 账面贷方 − 流水支出", D(str(tie["cr"][0])) - D(str(tie["cr"][1])))]
    for name, v in sums:
        ws.cell(row=r, column=2, value=name).font = F_B
        cell = ws.cell(row=r, column=7, value=float(v))
        cell.number_format = MONEY
        cell.font = F_B
        r += 1
    for k, w in {"A": 5, "B": 14, "C": 7, "D": 11, "E": 26, "F": 40, "G": 14, "H": 12}.items():
        ws.column_dimensions[k].width = w
    _setup(ws, "1:1", "A1:H%d" % max(r - 1, 1), paper=9)

    # ---------- 抽样说明 ----------
    ws = wb.create_sheet("抽样说明")
    ws.merge_cells("A1:D1")
    c = ws["A1"]
    c.value = "抽样总体与排除说明"
    c.font = F_T
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 24
    for i, h in enumerate(["项目", "笔数", "金额（元）", "说明"], 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.font = F_H
        cell.alignment = Alignment(horizontal="center", vertical="center")

    total_n = sum(v[0] for v in stat.values())
    total_a = sum(v[1] for v in stat.values())
    rows = [("核对总体（全部匹配组）", total_n, total_a, "银行存款收付全部笔次")]
    order = ["排除-银行内部户", "排除-税费社保", "排除-非往来业务", "排除-辅助核算无往来单位",
             "排除-流水无对方户名", "纳入抽样"]
    note_map = {
        "排除-流水无对方户名": "排除1：流水无对方户名，无从比对",
        "排除-银行内部户": "排除1：利息/手续费/待报解等银行内部户",
        "排除-税费社保": "排除2：税费、社保、医保、公积金，无企业对手方",
        "排除-非往来业务": "排除2：费用、税金、薪酬类，无往来对手方",
        "排除-辅助核算无往来单位": "排除2：辅助核算仅到部门，无往来单位",
        "纳入抽样": "往来款收付，构成抽样总体",
    }
    r2 = 3
    for k in order:
        if k not in stat:
            continue
        n, a = stat[k]
        rows.append((k, n, a, note_map.get(k, "")))
    for name, n, a, memo in rows:
        ws.cell(row=r2, column=1, value=name).font = F_B
        cell = ws.cell(row=r2, column=2, value=n); cell.font = F_B
        cell.alignment = Alignment(horizontal="center")
        cell = ws.cell(row=r2, column=3, value=round(a, 2)); cell.font = F_B
        cell.number_format = MONEY
        ws.cell(row=r2, column=4, value=memo).font = F_B
        r2 += 1
    ws.cell(row=r2, column=1, value="其中：对方单位名称不符").font = F_B
    cell = ws.cell(row=r2, column=2, value=defects); cell.font = F_B
    cell.alignment = Alignment(horizontal="center")
    ws.cell(row=r2, column=4, value="抽样总体中需逐笔核实是否存在第三方回款/付款").font = F_B
    r2 += 2
    ws.cell(row=r2, column=1, value="说明：排除项按规则自动识别，规则见上表“说明”列；名称不符的笔次不做抽样，一律全查。").font = F_B
    ws.merge_cells(start_row=r2, start_column=1, end_row=r2, end_column=4)
    _frame(ws, 2, 1, r2 - 3, 4)
    for k, w in {"A": 34, "B": 8, "C": 18, "D": 52}.items():
        ws.column_dimensions[k].width = w
    _setup(ws, "2:2", "A1:D%d" % (r2 - 1), paper=9)

    wb.save(out_path)
    return out_path