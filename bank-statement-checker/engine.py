# -*- coding: utf-8 -*-
"""流水核对引擎（核心算法）——江东光能 / 中天科技工程两例验证通过

输入：账户的账面分录列表 + 银行流水列表（由 loaders.py 提供）
输出：四项勾稽、匹配组、未达清单及分类
"""
from decimal import Decimal
from datetime import datetime
from collections import defaultdict
from itertools import combinations

D = Decimal
ZERO = D("0")


def _d(s):
    if s is None:
        return ZERO
    t = str(s).strip().replace(",", "")
    return ZERO if t in ("", "-", "None") else D(t)


def _date(s):
    """容错：None/空/非法值返回 None，不抛异常"""
    if s is None:
        return None
    t = str(s).strip()
    if t in ("", "None", "nan", "NaT"):
        return None
    try:
        return datetime.strptime(t[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _gap(a, b):
    """两个日期相差天数；任一为空返回 9999（视为不匹配）"""
    da, db = _date(a), _date(b)
    if da is None or db is None:
        return 9999
    return abs((da - db).days)


def tie_out(book, stmt):
    """四项勾稽：期初(流水反推)、借方/收入、贷方/支出、期末"""
    rs = [x for x in stmt if x.get("bal") is not None and _date(x.get("date")) is not None]
    # 同一天多笔：按交易时间、再按文件里的时间顺序（seq）排，保证取到真正的最早/最晚一笔
    rs.sort(key=lambda x: (_date(x["date"]), x.get("ts") or "", x.get("seq") or 0))
    # 流水没有余额列时期初/期末为 None（界面显示“—”，不参与勾稽）
    beg_s = (_d(rs[0]["bal"]) + _d(rs[0]["out"]) - _d(rs[0]["inn"])) if rs else None
    end_s = _d(rs[-1]["bal"]) if rs else None
    dr = sum((_d(x["dr"]) for x in book), ZERO)
    cr = sum((_d(x["cr"]) for x in book), ZERO)
    inn = sum((_d(x["inn"]) for x in stmt), ZERO)
    out = sum((_d(x["out"]) for x in stmt), ZERO)
    return {
        "dr": (dr, inn), "cr": (cr, out), "beg": (None, beg_s), "end": (None, end_s),
        "diff": {"dr": dr - inn, "cr": cr - out},
    }


def chain_breaks(stmt, limit=3):
    """余额链检查：上一笔余额 + 收入 − 支出 应等于本笔余额。接不上说明流水缺了行
    （含两个文件交界处缺的）；返回 [(日期, 差额)]"""
    rs = [x for x in stmt if x.get("bal") is not None and _date(x.get("date")) is not None]
    rs.sort(key=lambda x: (_date(x["date"]), x.get("ts") or "", x.get("seq") or 0))
    out, prev = [], None
    for x in rs:
        if prev is not None:
            gap = _d(x["bal"]) - (prev + _d(x["inn"]) - _d(x["out"]))
            if abs(gap) >= D("0.01"):
                out.append((_date(x["date"]), gap))
        prev = _d(x["bal"])
    return out[:limit]


def netted_returns(groups):
    """批量汇总按“净额”配上的组里，夹着的反方向流水（如工资代发时的同日退回）已被冲抵，
    不在未达清单里，但它们仍是借/贷方差额的一部分。把它们单独拿出来列示（复制一份并加备注）。"""
    out = []
    for d, bks, sts, kind in groups:
        if kind != "1:N" or d not in ("收入", "支出"):
            continue
        main, opp = ("inn", "out") if d == "收入" else ("out", "inn")
        for y in sts:
            if _d(y[opp]) > 0 and _d(y[main]) == 0:
                c = dict(y)
                c["note"] = "同日退回（已冲抵入账面汇总）"
                out.append(c)
                # 与退回对应的那部分原付款：账面汇总金额是净额，流水原付款比账面多出的正是这笔
                p = dict(y)
                p[main], p[opp] = y[opp], ZERO
                p["memo"] = "（被上笔退回冲抵的原付款）" + str(y.get("memo", ""))
                p["note"] = "原付款被退回冲抵（已入账面汇总净额）"
                out.append(p)
    return out


def match(book, stmt, tol=15, maxk=8):
    """1:1 → 1:N → N:1 → N:N 兜底，返回 (groups, ub, us)"""
    groups = []
    for bk, sk, d in (("dr", "inn", "收入"), ("cr", "out", "支出")):
        bl = [x for x in book if _d(x[bk]) > 0]
        sl = [x for x in stmt if _d(x[sk]) > 0]
        idx = defaultdict(list)
        for i, x in enumerate(sl):
            idx[_d(x[sk])].append(i)
        used = set()
        for x in bl:
            best = bd = None
            for j in idx.get(_d(x[bk]), []):
                if j in used:
                    continue
                gap = _gap(sl[j]["date"], x["date"])
                if gap <= tol and (bd is None or gap < bd):
                    best, bd = j, gap
            if best is not None:
                used.add(best)
                groups.append((d, [x], [sl[best]], "1:1"))
    mb = {id(g[1][0]) for g in groups}
    ms = {id(g[2][0]) for g in groups}

    for bk, sk, d in (("dr", "inn", "收入"), ("cr", "out", "支出")):
        for x in [y for y in book if _d(y[bk]) > 0 and id(y) not in mb]:
            cand = [y for y in stmt if id(y) not in ms and _d(y[sk]) > 0
                    and _gap(y["date"], x["date"]) <= tol][:40]
            f = None
            for k in range(2, min(maxk, len(cand)) + 1):
                for combo in combinations(cand, k):
                    if sum((_d(c[sk]) for c in combo), ZERO) == _d(x[bk]):
                        f = list(combo)
                        break
                if f:
                    break
            if f:
                for c in f:
                    ms.add(id(c))
                mb.add(id(x))
                groups.append((d, [x], f, "1:N"))
        for y in [z for z in stmt if id(z) not in ms and _d(z[sk]) > 0]:
            cand = [x for x in book if id(x) not in mb and _d(x[bk]) > 0
                    and _gap(y["date"], x["date"]) <= tol][:20]
            f = None
            for k in range(2, min(4, len(cand)) + 1):
                for combo in combinations(cand, k):
                    if sum((_d(c[bk]) for c in combo), ZERO) == _d(y[sk]):
                        f = list(combo)
                        break
                if f:
                    break
            if f:
                for c in f:
                    mb.add(id(c))
                ms.add(id(y))
                groups.append((d, f, [y], "N:1"))

    # 批量汇总：账面一笔汇总（如工资），流水同一天按人拆成很多笔（可能夹带同日退回）。
    # 同一天的未匹配流水，同方向合计 或 净额（本方向 − 反方向退回）等于账面金额才认。
    for bk, sk, d in (("dr", "inn", "收入"), ("cr", "out", "支出")):
        ok = "out" if sk == "inn" else "inn"
        for x in [y for y in book if _d(y[bk]) > 0 and id(y) not in mb]:
            amt = _d(x[bk])
            byday = defaultdict(list)
            for y in stmt:
                if id(y) not in ms and (_d(y[sk]) + _d(y[ok])) > 0 and _gap(y["date"], x["date"]) <= tol:
                    byday[_date(y["date"])].append(y)
            best = None
            for day, items in byday.items():
                if len([i for i in items if _d(i[sk]) > 0]) < 2:
                    continue
                tot = sum((_d(i[sk]) for i in items), ZERO)
                net = tot - sum((_d(i[ok]) for i in items), ZERO)
                if amt in (tot, net):
                    gap = _gap(day, x["date"])
                    if best is None or gap < best[0]:
                        best = (gap, items)
            if best:
                for c in best[1]:
                    ms.add(id(c))
                mb.add(id(x))
                groups.append((d, [x], best[1], "1:N"))

    # 同月汇总：账面一笔（如月末手续费），流水同一自然月内多笔（日期差可超过容差），合计相等才认。
    for bk, sk, d in (("dr", "inn", "收入"), ("cr", "out", "支出")):
        for x in [y for y in book if _d(y[bk]) > 0 and id(y) not in mb]:
            dx = _date(x["date"])
            if dx is None:
                continue
            cand = [y for y in stmt if id(y) not in ms and _d(y[sk]) > 0
                    and _date(y["date"]) is not None
                    and (_date(y["date"]).year, _date(y["date"]).month) == (dx.year, dx.month)]
            if len(cand) < 2:
                continue
            f = None
            if sum((_d(c[sk]) for c in cand), ZERO) == _d(x[bk]):
                f = cand
            else:
                cand = cand[:40]
                for k in range(2, min(maxk, len(cand)) + 1):
                    for combo in combinations(cand, k):
                        if sum((_d(c[sk]) for c in combo), ZERO) == _d(x[bk]):
                            f = list(combo)
                            break
                    if f:
                        break
            if f:
                for c in f:
                    ms.add(id(c))
                mb.add(id(x))
                groups.append((d, [x], f, "1:N"))

    ub = [x for x in book if id(x) not in mb and (_d(x["dr"]) + _d(x["cr"])) > 0]
    us = [y for y in stmt if id(y) not in ms and (_d(y["inn"]) + _d(y["out"])) > 0]
    if ub and us:
        tb = sum((_d(x["dr"]) + _d(x["cr"]) for x in ub), ZERO)
        ts = sum((_d(y["inn"]) + _d(y["out"]) for y in us), ZERO)
        if tb == ts:  # 双边总额相等，视为拆分口径不同
            groups.append(("拆分", ub, us, "N:N"))
            ub, us = [], []
    return groups, ub, us


import re as _re

_SUFFIX = ("股份有限公司", "有限责任公司", "有限公司", "集团", "公司", "科技", "工程", "贸易", "实业", "发展")


def norm_name(s):
    t = _re.sub(r"[（(].*?[)）]", "", str(s or ""))
    t = _re.sub(r"[\s、，,。.]", "", t)
    for w in _SUFFIX:
        t = t.replace(w, "")
    return t


def name_status(book_name, stmt_name, memo=""):
    """对方单位核对：一致 / 一致(经办人代付) / 不一致 / 无法比对"""
    if not stmt_name or not str(stmt_name).strip():
        return "无法比对"
    if any(k in str(stmt_name) for k in ("待报解", "利息", "手续费", "暂收", "待清算")):
        return "无法比对"
    a, b = norm_name(book_name), norm_name(stmt_name)
    if not a or not b:
        return "无法比对"
    if a == b or a in b or b in a:
        return "一致"
    # 简称与全称：取前 4 字互相包含（如“光伏技术” vs “中天光伏技术”）
    if len(a) >= 4 and len(b) >= 4 and (a[:4] in b or b[:4] in a):
        return "一致"
    # 账面摘要里出现流水对方名称 → 视为经办人代付/代收，可解释
    if memo and b and b in norm_name(memo) * 8:
        return "一致(经办人代付)"
    if memo and a and a in norm_name(memo) * 8 and len(a) >= 2:
        return "一致(经办人代付)"
    # 票据到期：账面写出票人，流水对方是承兑行
    if memo and ("承兑" in memo or "到期款" in memo) and "银行" in str(stmt_name):
        return "一致(承兑行代付)"
    # 保证金：第三方代收代付，需查保证金台账，不判为不一致
    if memo and "保证金" in memo:
        return "待核(保证金台账)"
    return "不一致"


_RELATED = []
_RELATED_REL = {}


def set_related(mapping):
    """mapping: {名称: 关系}，来自关联方清单"""
    global _RELATED, _RELATED_REL
    _RELATED_REL = dict(mapping or {})
    _RELATED = [n for n in _RELATED_REL if n]


def is_related(*names):
    """查关联方清单；清单为空返回 None（未知）"""
    if not _RELATED:
        return None
    for c in names:
        cn = norm_name(c or "")
        if not cn or len(cn) < 4:
            continue
        for n in _RELATED:
            nn = norm_name(n)
            if not nn:
                continue
            if cn == nn or cn in nn or nn in cn:
                return True
    return False


def judge_five(b, s, rel=None, book_name="", stmt_name="", date_gap=None):
    """五项核查结果。rel: True=关联方 / False=外部 / None=未知"""
    from datetime import datetime
    if date_gap is None:
        try:
            date_gap = abs((datetime.strptime(str(s["date"])[:10], "%Y-%m-%d")
                            - datetime.strptime(str(b["date"])[:10], "%Y-%m-%d")).days)
        except Exception:
            date_gap = 999
    if rel is None:                       # 优先查关联方清单，其次退化为名称关键词
        rel = is_related(book_name, stmt_name)   # 无关联方清单时为 None，该项留空由人工判断
    amt_ok = (_d(b.get("dr")) == _d(s.get("inn"))) and (_d(b.get("cr")) == _d(s.get("out")))
    return {
        "c1": "是" if (amt_ok and date_gap <= 30) else "否",      # 凭证/原始凭证/流水内容一致
        "c2": name_status(book_name, stmt_name, b.get("memo", "")),  # 对方单位核对
        "c3": None,                                                # 经济内容真实——留空待人工
        "c4": "是" if date_gap <= 30 else "否",                    # 会计期间
        "c5": ("是" if rel else ("否" if rel is False else None)),  # 关联交易
        "gap": date_gap,
    }


def flag_clues(b, s):
    """③ 经济内容可疑线索（只提示，不下结论）"""
    clues = []
    memo = str(b.get("memo") or s.get("memo") or "")
    cp = str(s.get("cp") or "")
    amt = max(_d(b.get("dr")), _d(b.get("cr")), _d(s.get("inn")), _d(s.get("out")))
    if memo.strip() in ("", "付款", "转账", "收款"):
        clues.append("摘要为空或过于笼统")
    if cp and len(cp) <= 4 and amt >= 50000:
        clues.append("个人收付且金额较大")
    if amt and amt % 10000 == 0 and amt >= 100000:
        clues.append("整数大额")
    return clues


import re as _re2

_UNIT = _re2.compile(r"[\u4e00-\u9fa5A-Za-z0-9（）()]{2,30}?(?:有限责任公司|股份有限公司|有限公司|分公司|集团|厂|中心|局|银行|供电公司|电力公司|建设集团)")


def guess_unit(memo, partner="", opp=""):
    """账面侧对方单位：业务伙伴 > 摘要中提取的单位名 > 对方科目"""
    p = str(partner or "").strip()
    if p and "\\" not in p and not p.startswith(("应付", "应收", "银行存款", "其他")):
        return p
    m = _UNIT.search(str(memo or ""))
    if m:
        return m.group(0)
    o = str(opp or "").strip()
    return o[:30] if (o and "\\" not in o) else ""

_INTERNAL_KW = ("待报解", "利息", "结息", "手续费", "工本费", "税费", "国库", "社保",
                "公积金", "工资代发", "代发", "退费", "扣费")
_EXPENSE_KW = ("财务费用", "管理费用", "销售费用", "税金及附加", "应付职工薪酬",
               "所得税费用", "其他收益", "合同履约成本_间接费用")
_DEPT_KW = ("财务部", "运维部", "综合部", "办公室", "市场部", "人事部", "工程部", "采购部")
_TAX_KW = ("缴税", "税费", "社会保险", "社保", "医保", "医疗", "养老", "公积金", "个人所得税", "个税", "完税")


def scope_tag(book, stmt, unit=""):
    """抽样归类：可核对 / 排除（含规则编号与原因）"""
    memo = str(book.get("memo") or "")
    if any(k in memo for k in _TAX_KW):
        return "排除-税费社保", "排除2"
    cp = str(stmt.get("cp") or "").strip()
    if not cp:
        return "排除-流水无对方户名", "排除1"
    if any(k in cp for k in _INTERNAL_KW):
        return "排除-银行内部户", "排除1"
    opp = str(book.get("opp") or "") + "|" + str(book.get("memo") or "")
    if any(k in opp for k in _EXPENSE_KW):
        return "排除-非往来业务", "排除2"
    u = str(unit or "").strip()
    if not u or u in _DEPT_KW:
        return "排除-辅助核算无往来单位", "排除2"
    return "纳入抽样", ""

def classify(item, is_book=True):
    """未达归因：个人代发 / 保证金划转 / 待确认"""
    cp = item.get("cp", "") if not is_book else ""
    memo = item.get("memo", "")
    if "保证金" in cp or "保证金" in memo:
        return "保证金划转"
    if cp and len(cp) <= 4:
        return "个人代发/报销"
    if "工资" in memo or "代发" in memo:
        return "代发工资"
    return "待确认"