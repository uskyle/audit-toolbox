# -*- coding: utf-8 -*-
"""数据读取层：序时账 / 余额表 / 各银行流水"""
import os, re, csv
from datetime import datetime, date
from decimal import Decimal
import openpyxl

D = Decimal
ZERO = D("0")

# 个别银行导出的 xlsx 会在“数字格”里放文字（如“借贷方向：全部”），openpyxl 默认直接抛错。
# 改成读不成数字就原样当文字返回。
try:
    from openpyxl.worksheet import _reader as _oxr
    _orig_cast = _oxr._cast_number

    def _safe_cast(v):
        try:
            return _orig_cast(v)
        except ValueError:
            return v
    _oxr._cast_number = _safe_cast
except Exception:
    pass


def _d(v):
    if v is None:
        return ZERO
    s = str(v).strip().replace(",", "").replace("，", "")
    if s in ("", "-", "--", "None"):
        return ZERO
    try:
        return D(s)
    except Exception:
        return ZERO


def _date(v):
    if v is None:
        return None
    # Excel 日期序列号（如 46028）→ 日期
    if isinstance(v, (int, float)) and 20000 < float(v) < 80000:
        from datetime import timedelta
        return (datetime(1899, 12, 30) + timedelta(days=float(v))).date()
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if s in ("", "None", "nan", "NaT", "-"):
        return None
    if re.fullmatch(r"\d{5}(\.0)?", s):          # 纯数字也当序列号
        from datetime import timedelta
        return (datetime(1899, 12, 30) + timedelta(days=float(s))).date()
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)          # 2026年01月01日
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    if re.match(r"\d{8}(?!\d)", s):                                # 20260113 或 20260113 10:54:26
        try:
            return datetime.strptime(s[:8], "%Y%m%d").date()
        except ValueError:
            return None
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:19] if "H" in f else s[:10], f).date()
        except Exception:
            pass
    return None


WARNINGS = []   # 读流水时的提示（如缺金额被跳过的行），界面读取后展示并清空


def _rows_xls(path):
    """旧格式 .xls（openpyxl 读不了）：用 xlrd 读第一张表；日期格转成真正的日期"""
    import xlrd
    book = xlrd.open_workbook(path)
    sh = book.sheet_by_index(0)
    rows = []
    for r in range(sh.nrows):
        row = []
        for c in range(sh.ncols):
            v = sh.cell_value(r, c)
            t = sh.cell_type(r, c)
            if t in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK) or v == "":
                v = None
            elif t == xlrd.XL_CELL_DATE:
                try:
                    v = xlrd.xldate_as_datetime(v, book.datemode)
                except Exception:
                    pass
            elif t == xlrd.XL_CELL_BOOLEAN:
                v = bool(v)
            row.append(v)
        rows.append(row)
    return rows


def _rows_text(path):
    """扩展名是 .xls/.xlsx、其实是文字（制表符或逗号分隔）的导出文件"""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("gb18030", errors="replace")
    lines = text.splitlines()
    delim = "\t" if sum(l.count("\t") for l in lines[:5]) >= sum(l.count(",") for l in lines[:5]) else ","
    out = []
    for r in csv.reader(lines, delimiter=delim):
        out.append([(c.strip() if c.strip() != "" else None) for c in r])
    return out


def _sniff(path):
    """按文件开头判断真实格式：ole2(真 xls) / zip(真 xlsx) / text"""
    with open(path, "rb") as f:
        head = f.read(8)
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "ole2"
    if head.startswith(b"PK"):
        return "zip"
    return "text"


def _rows(path):
    kind = _sniff(path)
    if kind == "ole2":
        return _rows_xls(path)
    if kind == "text":
        return _rows_text(path)
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


_SKIP_UNIT = ("外部", "内部", "联营与其他", "集团", "13%-专票", "6%-专票", "9%-专票", "专票", "普票")


def units_from_aux(aux):
    """从辅助核算串里取单位名：支持
       【业务伙伴:xxx】
       [ZTT_23-1]外部|[0009-K0010729]国网江苏省电力有限公司
    """
    s = str(aux or "")
    out = []
    m = re.search(r"【业务伙伴[:：]([^】]+)】", s)
    if m:
        return [m.group(1).strip()]
    cand = []
    for seg in s.split("|"):
        t = re.sub(r"^\[[^\]]*\]", "", seg.strip()).strip()
        if not t or t in _SKIP_UNIT or t.startswith("现金流量项目"):    # 现金流量项目不是对方单位
            continue
        if re.fullmatch(r"[\d.\-%]+", t):
            continue
        cand.append(t)
    # 优先取“像公司”的名称（带公司/集团/银行等后缀），再按长度降序
    _corp = re.compile(r"(有限责任公司|股份有限公司|有限公司|分公司|集团|银行|厂|中心|局)$")
    corp = [c for c in cand if _corp.search(c)]
    rest = [c for c in cand if c not in corp]
    corp.sort(key=len, reverse=True)
    rest.sort(key=len, reverse=True)
    return corp + rest


JOURNAL_FIELDS = [
    # (字段, 界面显示名, 是否必选, 自动识别用的常见列名)
    ("name", "科目名称", True, ["科目名称", "会计科目", "科目"]),
    ("date", "日期", True, ["制单日期", "凭证日期", "业务日期", "记账日期", "日期"]),
    ("vou", "凭证号", True, ["凭证号", "凭证编号", "凭证字号"]),
    ("memo", "摘要", True, ["摘要", "说明", "业务说明"]),
    ("dr", "借方金额", True, ["借方本币", "借方金额", "借方", "借"]),
    ("cr", "贷方金额", True, ["贷方本币", "贷方金额", "贷方", "贷"]),
    ("aux", "辅助核算", False, ["辅助核算"]),
    ("acct", "银行账户列", False, ["银行账户", "银行账号", "账号"]),
    ("opp", "对方科目", False, ["对方科目"]),
    ("type", "凭证类型", False, ["类型", "凭证类型", "凭证字"]),
]


def journal_headers(path):
    """返回 (表头行号, 表头列表, 自动识别结果 {字段: 列名})，供界面做列映射"""
    rows = _rows(path)
    hi = next((i for i, r in enumerate(rows[:30])
               if sum(1 for c in r if isinstance(c, str) and c.strip()) >= 4), 0)
    heads = [str(c).strip() for c in rows[hi] if c is not None and str(c).strip()]
    guess = {}
    for key, _, _, cands in JOURNAL_FIELDS:
        for n in cands:
            if n in heads:
                guess[key] = n
                break
    return hi, heads, guess


def load_journal(path, colmap=None, bank_subject="银行存款"):
    """序时账：返回银行分录用 dict

    colmap: {字段: 表头列名}，由界面“列映射”提供；不给则按常见列名自动识别。
    bank_subject: 银行存款科目的名称，默认“银行存款”。
    银行账户优先取 colmap["acct"] 指定的列，其次从辅助核算里提取。
    """
    colmap = colmap or {}
    rows = _rows(path)
    name_hdr = colmap.get("name", "科目名称")
    hi = next((i for i, r in enumerate(rows[:30])
               if any(str(c).strip() == name_hdr for c in r if c is not None)), None)
    if hi is None:
        raise ValueError("这张表找不到“%s”列，可能不是序时账" % name_hdr)
    head = {str(c).strip(): j for j, c in enumerate(rows[hi]) if c is not None}

    def pick(key, *names, required=True):
        if colmap.get(key) in head:
            return head[colmap[key]]
        for n in names:
            if n in head:
                return head[n]
        if not required:
            return None
        raise ValueError("序时账缺少列：%s（现有列：%s）"
                         % ("/".join(names), "、".join(list(head)[:12])))
    c_date = pick("date", "制单日期", "凭证日期", "业务日期", "记账日期", "记账时间")
    c_vou = pick("vou", "凭证号", "凭证编号", "凭证字号")
    c_memo = pick("memo", "摘要", "业务说明", "说明")
    c_name = pick("name", "科目名称")
    c_parent = pick("parent", "上级科目名称", required=False)     # 有的账套把“银行存款”放在上级科目列
    c_aux = pick("aux", "辅助核算", "核算项目名称", required=False)
    c_dr = pick("dr", "借方本币", "借方金额", "借方发生额")
    c_cr = pick("cr", "贷方本币", "贷方金额", "贷方发生额")
    c_opp = pick("opp", "对方科目", "对方科目名称", required=False)
    c_type = pick("type", "类型", "凭证种类", required=False)
    c_acctcol = colmap.get("acct") and head.get(colmap["acct"])

    # 先按凭证归集对方单位与关联标识（业务伙伴/内外部在对方科目行上）
    from collections import defaultdict
    _dcol = c_date
    _vcol = c_vou
    _tcol = c_type          # 暂/现/记，同一凭证号可能重复，必须一起做键
    _acol = c_aux
    _ocol = c_opp
    ctx = defaultdict(lambda: {"partner": "", "rel": None, "lines": []})
    for r in rows[hi + 1:]:
        if not r:
            continue
        aux = str(r[_acol] or "") if _acol is not None else ""
        key = (r[_dcol], (r[_tcol] if _tcol is not None else ""), r[_vcol])
        p = re.search(r"【业务伙伴:([^】]+)】", aux)
        i = re.search(r"【内外部:([^】]+)】", aux)
        if p and not ctx[key]["partner"]:
            ctx[key]["partner"] = p.group(1).strip()
        if i and ctx[key]["rel"] is None:
            ctx[key]["rel"] = (i.group(1).strip() not in ("外部", ""))
        # 记录每条分录，用于后续按“对方分录”拆出对方单位
        _us = units_from_aux(aux)
        ctx[key]["lines"].append(dict(
            name=str(r[c_name] or "").strip(),
            aux=aux,
            partner=(_us[0] if _us else ""),
            dr=_d(r[c_dr]), cr=_d(r[c_cr])))

    out = []
    for r in rows[hi + 1:]:
        if not r:
            continue
        subj = str(r[c_name] or "").strip()
        # 银行存款本身，或分级科目“银行存款\户名”（账户写在科目名称里）
        sub_acct = None
        if subj != bank_subject:
            if subj.startswith(bank_subject + "\\"):
                sub_acct = subj.split("\\")[-1].strip()
            else:
                # 账户名在科目名称里、“银行存款”在上级科目列（如“\银行存款\定期存款”）
                par = str(r[c_parent] or "").strip().strip("\\") if c_parent is not None else ""
                if par.split("\\")[0] != bank_subject or not subj:
                    continue
                sub_acct = subj
        aux = str(r[c_aux] or "") if c_aux is not None else ""
        m = re.search(r"【银行账户[:：]([^】]+)】", aux)
        if not m:                       # 另一种导出：[0013-账号]开户行名称|…
            m = re.search(r"\[[^\]]*\]([^|\]]+)", aux)
        acct_txt = (str(r[c_acctcol]).strip() if c_acctcol and r[c_acctcol] else None)
        c = ctx[(r[c_date], (r[c_type] if c_type is not None else ""), r[c_vou])]
        dr_v, cr_v = _d(r[c_dr]), _d(r[c_cr])
        # 同凭证内、方向相反的其他分录 = 对方分录，据此拆出对方单位。
        # 一张凭证可能有多笔银行分录（如三笔定期存款同时到期）：每笔只分到“金额正好合得上”的那几条对方分录，
        # 合不上就不拆（底稿按这笔银行分录自己的金额列示），不能把整张凭证的对方分录重复挂给每一笔。
        target = dr_v if dr_v > 0 else cr_v
        if dr_v > 0:
            cand = [(x, x["cr"] - x["dr"]) for x in c["lines"] if x["name"] != bank_subject and x["cr"] - x["dr"] > 0]
        else:
            cand = [(x, x["dr"] - x["cr"]) for x in c["lines"] if x["name"] != bank_subject and x["dr"] - x["cr"] > 0]
        used = c.setdefault("used", set())
        avail = [(x, a) for x, a in cand if id(x) not in used]
        chosen = []
        if target > 0 and avail:
            if sum((a for _, a in avail), ZERO) == target:
                chosen = avail
            elif len(avail) <= 14:
                from itertools import combinations
                for k in range(1, min(len(avail), 6) + 1):
                    hit = next((cb for cb in combinations(avail, k) if sum((a for _, a in cb), ZERO) == target), None)
                    if hit:
                        chosen = list(hit)
                        break
        used.update(id(x) for x, _ in chosen)
        _memo = str(r[c_memo] or "")
        _mu = re.search(r"[\u4e00-\u9fa5A-Za-z0-9（）()]{2,30}?(?:有限责任公司|股份有限公司|有限公司|分公司|集团|局|银行|供电公司|电力公司)", _memo)
        _memo_unit = _mu.group(0) if _mu else ""
        splits = [dict(unit=(x["partner"] or _memo_unit or x["name"].split("\\")[-1]), amt=a) for x, a in chosen]
        out.append(dict(
            account=acct_txt or sub_acct or (m.group(1).strip() if m else None),
            date=_date(r[c_date]), vou=r[c_vou],
            memo=str(r[c_memo] or ""),
            dr=dr_v, cr=cr_v,
            partner=c["partner"],
            rel=c["rel"], opp=(str(r[c_opp] or "") if c_opp is not None else ""),
            splits=splits, aux=aux))
    return out


def load_related(path):
    """关联方清单：返回 {名称: 关系}，含公司名称与简称"""
    rows = _rows(path)
    hi = next((i for i, r in enumerate(rows[:10])
               if any(str(c).strip() == "公司名称" for c in r if c is not None)), None)
    if hi is None:
        return {}
    head = {str(c).strip(): j for j, c in enumerate(rows[hi]) if c is not None}
    ci, cs, cr = head.get("公司名称"), head.get("公司简称"), head.get("关联方关系")
    out = {}
    for r in rows[hi + 1:]:
        if not r or ci is None or ci >= len(r) or not r[ci]:
            continue
        name = str(r[ci]).strip()
        rel = str(r[cr]).strip() if (cr is not None and cr < len(r) and r[cr]) else ""
        out[name] = rel
        if cs is not None and cs < len(r) and r[cs]:
            out[str(r[cs]).strip()] = rel
    if out and all(x["date"] is None for x in out):
        raise ValueError("序时账的日期列无法识别（%d 笔全部为空）。请检查该列是否为日期格式，"
                         "或在 Excel 中把该列转为日期后另存。" % len(out))
    return out


def load_balance(path):
    """余额表：返回 {账户名: (期初, 借方, 贷方, 期末)}，仅银行存款子户"""
    rows = _rows(path)
    out, started = {}, False
    seq = []                                  # (缩进, 名称)，用来剔除“下面还有子级”的汇总行（如“定期存款”）
    for r in rows:
        name = r[0] if r and r[0] else ""
        if not isinstance(name, str):
            continue
        if name.strip() == "银行存款":
            started = True
            continue
        if started:
            if not name.startswith(" "):
                break
            key = name.strip()
            if key in ("银行账户", "存放同业"):   # 汇总行，不是账户
                continue
            out[key] = (_d(r[2]), _d(r[3]), _d(r[4]), _d(r[5]))
            seq.append((len(name) - len(name.lstrip()), key))
    for (ind, key), (nxt, _) in zip(seq, seq[1:]):
        if nxt > ind:
            out.pop(key, None)
    if out:
        return out

    # 兜底：辅助核算式余额表（行首为【银行账户：…】，后接 期初借/期初贷/本期借/本期贷/期末借/期末贷）
    for r in rows:
        if not r or not isinstance(r[0], str):
            continue
        m = re.match(r"【银行账户[:：]\s*(.+?)】", r[0].strip())
        if not m:
            continue
        nums = [(_d(x) if x not in (None, "") else ZERO) for x in r[1:7]]
        while len(nums) < 6:
            nums.append(ZERO)
        out[m.group(1).strip()] = (nums[0] - nums[1], nums[2], nums[3], nums[4] - nums[5])
    return out


_HDR_WORDS = ("日期", "时间", "金额", "发生额", "余额", "摘要", "对方", "借贷", "收入", "支出",
              "借方", "贷方", "户名", "账号", "凭证", "币种", "类型")


def _find_header(rows):
    """找表头行：一行里至少 4 个“像列名”的短格子（带冒号的是表头上方的说明行，不算），且含日期/时间列"""
    for i, r in enumerate(rows[:40]):
        cells = [str(c).strip() for c in r if c is not None and str(c).strip()]
        good = [t for t in cells if len(t) <= 60 and ":" not in t and "：" not in t
                and any(w in t for w in _HDR_WORDS)]
        if len(good) >= 4 and any(("日期" in t or "时间" in t) for t in good):
            return i
    for i, r in enumerate(rows[:10]):                       # 兜底：旧规则
        if any("交易时间" in str(c) or "交易日期" in str(c) for c in r if c is not None):
            return i
    return None


def _clock(v):
    """从单元格取时分秒 'HH:MM:SS'，取不到返回空串（用于同一天多笔的先后排序）"""
    s = str(v if v is not None else "").strip()
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        return "%02d:%s:%s" % (int(m.group(1)), m.group(2), m.group(3) or "00")
    if re.fullmatch(r"\d{6}", s):                           # 143006 → 14:30:06
        return "%s:%s:%s" % (s[:2], s[2:4], s[4:])
    if isinstance(v, datetime):
        return v.strftime("%H:%M:%S")
    return ""


def _fname(path):
    """提示里用的文件名（去掉 xls 转换时加的内部后缀）"""
    n = os.path.basename(path)
    return re.sub(r"_[0-9a-f]{8}_conv\.xlsx$", ".xls", n)


def load_statement(path):
    """流水：按表头关键词自动识别各银行版式（借/贷分列、单列金额+借贷标记、单列带正负号、
    单列无符号+摘要里写借方/贷方 等）"""
    rows = _rows(path)
    hi = _find_header(rows)
    if hi is None:
        raise ValueError("无法识别流水表头：%s" % _fname(path))
    cols = {str(c).strip(): j for j, c in enumerate(rows[hi]) if c is not None}

    def col(*names):
        for n in names:
            for k, j in cols.items():
                if n in k:
                    return j
        return None

    c_d1, c_d2 = col("交易日期", "记账日期", "日期"), col("交易时间")
    c_amt, c_flag = col("交易金额"), col("借贷标记", "借贷标志", "收支标识")
    c_in = col("贷方发生额", "收入金额", "贷方金额", "转入金额", "收入")
    c_out = col("借方发生额", "支出金额", "借方金额", "转出金额", "支出")
    c_bal = col("账户余额", "交易后余额", "余额")
    c_cp = col("对方户名", "对方名称", "对方单位")
    c_acct = col("对方账号")
    c_memo = col("摘要")
    c_payer, c_payee = col("付款人名称"), col("收款人名称")      # 中行：没有“对方户名”，按收付方向取
    c_payer_a, c_payee_a = col("付款人账号"), col("收款人账号")
    c_txt = [j for k, j in cols.items() if any(w in k for w in ("摘要", "交易类型", "业务类型", "备注", "用途"))]

    # 没有任何金额列：只能从“回单个性化信息/附言”文字里取“实收金额/利息”，取不到的行跳过并留警告
    no_amt = c_amt is None and c_in is None and c_out is None
    c_info = col("回单个性化信息", "附言") if no_amt else None
    _amt_re = re.compile(r"(?:实收金额|利息)[:：]\s*([\d,]+\.?\d*)")
    if no_amt and (c_info is None or c_flag is None):
        raise ValueError("流水里没有金额列，也没有可提取金额的说明列，无法核对：%s" % _fname(path))

    def cell(r, j):
        return r[j] if (j is not None and j < len(r)) else None

    recs = []
    for r in rows[hi + 1:]:
        if not r or all(c is None for c in r):
            continue
        d = None
        for c in (c_d1, c_d2):
            if c is not None and c < len(r):
                d = _date(r[c])
                if d:
                    break
        if not d:
            continue
        ts = _clock(cell(r, c_d2)) or _clock(cell(r, c_d1))
        direction = None                         # +1 收入 / -1 支出 / None 待定
        if no_amt:
            mm = _amt_re.search(str(r[c_info] or "")) if c_info < len(r) else None
            if not mm:
                WARNINGS.append("%s：%s %s 一笔没有金额（说明里也没写），已跳过，需人工补录"
                                % (_fname(path), d, str(r[c_memo] or "")[:10] if c_memo is not None else ""))
                continue
            amt = _d(mm.group(1))
            direction = 1 if str(r[c_flag]).strip() == "贷" else -1
        elif c_amt is not None and c_flag is not None:
            amt = abs(_d(r[c_amt]))
            direction = 1 if str(r[c_flag]).strip() in ("贷", "收入") else -1
        elif c_in is not None or c_out is not None:
            inn = _d(cell(r, c_in))
            o = _d(cell(r, c_out))
            amt, direction = (inn, 1) if inn > 0 else (o, -1)
        else:                                    # 只有一列金额，方向另行判断
            raw = _d(r[c_amt])
            amt = abs(raw)
            if raw < 0:
                direction = -1
            else:
                txt = " ".join(str(cell(r, j) or "") for j in c_txt)
                if "贷方" in txt or "入账" in txt or "收入" in txt or "来账" in txt:
                    direction = 1
                elif "借方" in txt or "支出" in txt or "往账" in txt:
                    direction = -1
        recs.append(dict(d=d, ts=ts, amt=amt, dir=direction,
                         bal=_d(cell(r, c_bal)) if (c_bal is not None and cell(r, c_bal) not in (None, "")) else None,
                         r=r))
    if not recs:
        return []

    # 时间顺序：文件里日期是降序就整体倒过来，用来按余额变化补判方向、以及期初/期末取值
    asc = recs[0]["d"] <= recs[-1]["d"]
    chron = recs if asc else recs[::-1]
    for k, x in enumerate(chron):
        x["seq"] = k
    for k, x in enumerate(chron):
        if x["dir"] is None:
            if k > 0 and x["bal"] is not None and chron[k - 1]["bal"] is not None:
                delta = x["bal"] - chron[k - 1]["bal"]
                if abs(delta - x["amt"]) < D("0.01"):
                    x["dir"] = 1
                elif abs(delta + x["amt"]) < D("0.01"):
                    x["dir"] = -1
            if x["dir"] is None and x["amt"] > 0:
                WARNINGS.append("%s：%s %s 一笔判断不出收入还是支出，已跳过，需人工补录"
                                % (_fname(path), x["d"], x["amt"]))

    out = []
    for x in recs:
        if x["dir"] is None:
            continue
        r = x["r"]
        inn, o = (x["amt"], ZERO) if x["dir"] > 0 else (ZERO, x["amt"])
        cp = str(cell(r, c_cp) or "") if c_cp is not None else ""
        cpacct = str(cell(r, c_acct) or "") if c_acct is not None else ""
        if c_cp is None and c_payer is not None and c_payee is not None:
            cp = str(cell(r, c_payer if x["dir"] > 0 else c_payee) or "")
            cpacct = str(cell(r, c_payer_a if x["dir"] > 0 else c_payee_a) or "")
        out.append(dict(date=x["d"], inn=inn, out=o, bal=x["bal"], ts=x["ts"], seq=x["seq"],
                        cp=cp.strip(), cpacct=cpacct.strip(),
                        memo=str(cell(r, c_memo) or "") if c_memo is not None else ""))
    return out


def load_map(path):
    """读取账户对照表：返回 [{acct, name, book}]，book 为对应的账面科目名"""
    rows = _rows(path)
    hi = next((i for i, r in enumerate(rows[:10])
               if any(str(c).strip() == "账号" for c in r if c is not None)), None)
    if hi is None:
        raise ValueError("对照表里找不到“账号”列")
    head = {str(c).strip(): j for j, c in enumerate(rows[hi]) if c is not None}
    c_acct = head.get("账号")
    c_name = head.get("账户名称")
    c_book = head.get("账面科目")
    out = []
    for r in rows[hi + 1:]:
        if not r or c_acct is None or not r[c_acct]:
            continue
        out.append(dict(acct=str(r[c_acct]).strip(),
                        name=str(r[c_name] or "").strip() if c_name is not None else "",
                        book=str(r[c_book] or "").strip() if c_book is not None else ""))
    return out


def book_for_file(filename, mapping):
    """按账号尾号 / 户名，把流水文件对到账面科目"""
    digits = re.sub(r"\D", "", filename)
    for m in mapping:
        tail = re.sub(r"\D", "", m["acct"])[-4:]
        if tail and tail in filename:
            return m["book"] or m["name"]
    for m in mapping:
        n = m["name"]
        if n and len(n) >= 6 and n[:8] in filename:
            return m["book"] or n
    return None


# ---------- 流水文件 → 账户 对应 ----------
STMT_EXT = (".xlsx", ".xls", ".csv", ".pdf")
STMT_SKIP = ("序时账", "余额表", "明细账", "账户对照表", "关联方", "流水核对", "已开立")


def list_statement_files(dirs):
    """递归列出可能是流水的文件（跳过序时账、余额表、对照表、本工具生成的底稿等）"""
    seen, out = set(), []
    for d in dirs:
        for root, _, files in os.walk(d):
            for f in files:
                if (not f.lower().endswith(STMT_EXT) or f.startswith("~$")
                        or any(k in f for k in STMT_SKIP) or f.endswith("_conv.xlsx")):
                    continue
                p = os.path.join(root, f)
                key = os.path.normcase(os.path.abspath(p))
                if key not in seen:
                    seen.add(key)
                    out.append(os.path.abspath(p))
    return sorted(out)


def _tail(acct):
    """账户名里最后一串 3 位以上数字（账号尾号）"""
    runs = re.findall(r"\d{3,}", acct or "")
    return runs[-1] if runs else ""


def _cell_text(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return "" if v is None else str(v)


def head_text(path, nrows=60):
    """文件开头几行的文字（用来找账号）；读不了返回空串"""
    low = path.lower()
    try:
        if low.endswith(".csv"):
            with open(path, "r", encoding="gbk", errors="replace") as f:
                return " ".join(next(f, "") for _ in range(nrows))
        if low.endswith((".xls", ".xlsx")) and _sniff(path) == "text":      # 扩展名是 Excel、内容其实是文字
            return " ".join(_cell_text(c) for row in _rows_text(path)[:nrows] for c in row)
        if low.endswith(".xls"):
            import xlrd
            sh = xlrd.open_workbook(path).sheet_by_index(0)
            return " ".join(_cell_text(sh.cell_value(r, c)) for r in range(min(nrows, sh.nrows)) for c in range(sh.ncols))
        if low.endswith(".xlsx"):
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                return " ".join(_cell_text(c) for row in wb.active.iter_rows(max_row=nrows, values_only=True) for c in row)
            finally:
                wb.close()
        if low.endswith(".pdf"):
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(path)
            return pdf[0].get_textpage().get_text_range() if len(pdf) else ""
    except Exception:
        return ""
    return ""


def match_accounts(path, accounts, mapping=None):
    """把一个流水文件对到账户。返回 (候选账户列表, 依据)。
    依据按可靠度：对照表 > 文件名尾号 > 文件夹名尾号 > 文件内账号。候选多于 1 个表示有歧义。"""
    f = os.path.basename(path)
    if mapping:
        t = book_for_file(f, mapping)
        if t in accounts:
            return [t], "对照表"
    folders = os.path.dirname(path).replace("/", "\\").split("\\")[-3:]
    hint = f + " " + " ".join(folders)

    # 1) 文件里的账号：本户账号在每一行都会出现，对方账号只出现在部分行，按出现次数投票
    hits = _vote_by_content(path, accounts, hint)
    if hits:
        return hits, "文件内账号"
    # 2) 文件名 / 文件夹名里的账号尾号
    hits = [a for a in accounts if _tail(a) and _tail(a)[-4:] in f]
    if hits:
        return hits, "文件名"
    hits = [a for a in accounts if _tail(a) and any(_tail(a)[-4:] in x for x in folders)]
    return hits, ("文件夹名" if hits else "")


_BANK_GROUPS = [("中国银行", "中行"), ("工商银行", "工行"), ("农业银行", "农行"), ("建设银行", "建行"),
                ("交通银行", "交行"), ("邮储", "邮政"), ("兴业",), ("光大",), ("河北银行",), ("张家口",),
                ("廊坊银行",), ("招商",), ("民生",), ("浦发",), ("华夏",), ("江苏",), ("农信", "农商")]


def _same_bank(acct, text):
    return any(any(k in acct for k in g) and any(k in text for k in g) for g in _BANK_GROUPS)


def _vote_by_content(path, accounts, hint=""):
    """按文件开头出现的长数字（≥10 位）给账户投票，返回得票最高且唯一的账户（并列时用银行名/文件名再分）"""
    txt = head_text(path)
    if not txt:
        return []
    from collections import Counter
    labeled = re.findall(r"[账帐]号\W{0,8}(\d{10,})", txt)
    if labeled:                      # 表头明确写了“账号：xxx”，就只认它（数据行里的是对方账号，不能参与）
        cnt = Counter(labeled)
    else:                            # 账号在数据列里：本户每行都有，按出现次数投票
        cnt = Counter(re.findall(r"(?<!\d)\d{10,}(?!\d)", txt))
    if not cnt:
        return []

    def score(a, fuzzy):
        t = _tail(a)
        if len(t) < 4:
            return 0
        if fuzzy:                                               # 个别导出把长账号末位吃掉，容许少一位
            t = t[:-1] if len(t) >= 5 else ""
        return sum(c for n, c in cnt.items() if t and n.endswith(t))
    for fuzzy in (False, True):
        sc = {a: score(a, fuzzy) for a in accounts}
        top = max(sc.values(), default=0)
        if top <= 0:
            continue
        best = [a for a, v in sc.items() if v == top]
        if len(best) > 1:
            by_bank = [a for a in best if _same_bank(a, hint)]
            best = by_bank or best
        return best
    return []


def load_statement_csv(path):
    """工行网银 CSV：GBK 编码，前几行是账号户名信息，表头含'日期'与'借方发生额'"""
    with open(path, "r", encoding="gbk", errors="replace") as f:
        rows = list(csv.reader(f))
    hi = None
    for i, r in enumerate(rows[:15]):
        t = " ".join(r)
        if "日期" in t and ("借方发生额" in t or "支出" in t):
            hi = i
            break
    if hi is None:
        raise ValueError("无法识别 CSV 表头：%s" % os.path.basename(path))
    head = rows[hi]
    idx = {h.strip(): j for j, h in enumerate(head)}

    def col(*names):
        for n in names:
            for k, j in idx.items():
                if n in k:
                    return j
        return None

    c_d = col("日期", "交易时间")
    c_out = col("借方发生额", "支出")
    c_in = col("贷方发生额", "收入")
    c_bal = col("余额")
    c_cp = col("对方户名")
    c_acct = col("对方账号")
    c_memo = col("摘要")

    out = []
    for r in rows[hi + 1:]:
        if not r or not r[c_d].strip():
            continue
        d = _date(r[c_d])
        if not d:
            continue
        out.append(dict(date=d,
                        inn=_d(r[c_in]) if c_in is not None else ZERO,
                        out=_d(r[c_out]) if c_out is not None else ZERO,
                        bal=_d(r[c_bal]) if c_bal is not None else None,
                        cp=r[c_cp].strip() if c_cp is not None else "",
                        cpacct=r[c_acct].strip() if c_acct is not None else "",
                        memo=r[c_memo].strip() if c_memo is not None else ""))
    return out


def convert_xls(path, outdir=None):
    """用 xlrd 读 .xls 并转存为临时 .xlsx（不依赖 Excel）"""
    import tempfile
    import xlrd
    outdir = outdir or tempfile.gettempdir()
    import hashlib
    tag = hashlib.md5(("%s|%s" % (os.path.abspath(path), os.path.getmtime(path))).encode("utf-8")).hexdigest()[:8]
    dst = os.path.join(outdir, "%s_%s_conv.xlsx" % (os.path.splitext(os.path.basename(path))[0], tag))
    if os.path.exists(dst):
        return dst
    if _sniff(path) != "ole2":                       # 不是真正的 xls（文字或其实是 xlsx）：按真实格式读，再存成 xlsx
        wb = openpyxl.Workbook()
        ws = wb.active
        for i, row in enumerate(_rows(path), start=1):
            for j, v in enumerate(row, start=1):
                if v is not None:
                    ws.cell(row=i, column=j, value=v)
        wb.save(dst)
        return dst
    book = xlrd.open_workbook(path)
    sh = book.sheet_by_index(0)
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in range(sh.nrows):
        for c in range(sh.ncols):
            v = sh.cell_value(r, c)
            if v == "":
                continue
            if sh.cell_type(r, c) == xlrd.XL_CELL_NUMBER:
                v = v
            ws.cell(row=r + 1, column=c + 1, value=v)
    wb.save(dst)
    return dst


def load_statement_pdf(path):
    """PDF 文字层：支持工行'借/贷 金额 对方账号 摘要 日期 凭证号'版式；扫描件返回空列表"""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []
    pdf = pdfium.PdfDocument(path)
    text = "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
    if not text.strip():
        return []                       # 扫描件，无文字层
    import re as _re
    pat = _re.compile(r"(借|贷)\s+([\d,]+\.\d{2})\s+(\S+)\s+(\S+)\s+(\d{4}-\d{2}-\d{2})\s+(\S+)\s*([^\n]*)")
    out = []
    for m in pat.finditer(text):
        flag, amt, cpacct, memo, d, vou, cp = m.groups()
        a = _d(amt)
        out.append(dict(date=_date(d), inn=(a if flag == "贷" else ZERO), out=(a if flag == "借" else ZERO),
                        bal=None, cp=cp.strip(), cpacct=cpacct, memo=memo))
    return out


def load_statement_any(path):
    """按扩展名分派；.xls 需先转 xlsx（见 convert_xls）"""
    low = path.lower()
    if low.endswith(".csv"):
        return load_statement_csv(path)
    if low.endswith(".xls"):
        return load_statement(convert_xls(path))
    return load_statement(path)

