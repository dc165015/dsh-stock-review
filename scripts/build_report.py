#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股深度股评 · 单文件 HTML 生成器
==================================

用法：
    python build_report.py data.json
    python build_report.py data.json -o 600519_股评_2026-11-26.html
    python build_report.py sample_data.json --open

输入：一份 JSON（字段见 SKILL.md 与 sample_data.json），输出：自包含单文件 HTML。
无第三方依赖，仅用标准库；ECharts 通过 CDN 引入，离线时图表位置优雅降级为表格数值。

设计约束（来自股评模板）：
  - 深色财经主题：底色 #0b1628，金色强调 #f5c063，红涨绿跌
  - 卡片圆角 + 阴影 + hover 微动效，可展开/收起
  - 顶部 sticky 导航锚点跳转
  - 近60日无涨停 / 近半年无并购 / 近60日无研报 时自动隐藏对应章节
"""

import argparse
import datetime
import html
import json
import os
import sys

CN_NUM = "一二三四五六七八九十"

# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def esc(value):
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def pick(obj, *keys, default=None):
    """按路径取值：pick(d, 'market', 'price')。缺失返回 default。"""
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return default
        if key not in cur or cur[key] is None:
            return default
        cur = cur[key]
    return cur


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v not in (None, "")]
    return [value]


def to_num(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def fmt(value, nd=2, plus=False, unit=""):
    """数值格式化；无法解析时原样返回字符串，缺失返回 '—'。"""
    num = to_num(value)
    if num is None:
        if value is None or value == "":
            return "—"
        return esc(value)
    if nd == 0:
        text = "{:.0f}".format(num)
    else:
        text = "{:,.{nd}f}".format(num, nd=nd)
    if plus and num > 0:
        text = "+" + text
    return text + unit


def pct_text(value, nd=2, plus=True):
    num = to_num(value)
    if num is None:
        if value is None or value == "":
            return "—"
        return esc(value)
    prefix = "+" if (plus and num > 0) else ""
    return "{}{:.{nd}f}%".format(prefix, num, nd=nd)


def dir_class(value):
    num = to_num(value)
    if num is None:
        return "flat"
    if num > 0:
        return "up"
    if num < 0:
        return "down"
    return "flat"


def yi(value, nd=2):
    """亿元数字：数值原样，缺失为 —。"""
    return fmt(value, nd=nd)


# ---------------------------------------------------------------------------
# 章节 HTML 片段
# ---------------------------------------------------------------------------


def card(section_id, index, title, body, subtitle=""):
    sub = '<span class="card-sub">{}</span>'.format(esc(subtitle)) if subtitle else ""
    return """
<section class="card" id="{sid}">
  <header class="card-head">
    <span class="idx">{idx}</span>
    <h2>{title}</h2>{sub}
    <button class="toggle" type="button" aria-expanded="true" aria-controls="{sid}-body">
      <span class="toggle-label">收起</span><span class="chev"></span>
    </button>
  </header>
  <div class="card-body" id="{sid}-body"><div class="card-inner">
{body}
  </div></div>
</section>
""".format(sid=section_id, idx=index, title=esc(title), sub=sub, body=body)


def kv_table(rows):
    """两列键值表格。rows: [(k, v_html)]"""
    body = "".join(
        '<tr><th>{}</th><td>{}</td></tr>'.format(esc(k), v) for k, v in rows
    )
    return '<table class="kv-table">{}</table>'.format(body)


def data_table(headers, rows, align=None, cls=""):
    align = align or ["left"] * len(headers)
    head = "".join(
        '<th class="{}">{}</th>'.format(a, esc(h)) for h, a in zip(headers, align)
    )
    body = []
    for row in rows:
        cells = []
        for cell, a in zip(row, align):
            cells.append('<td class="{}">{}</td>'.format(a, cell))
        body.append("<tr>{}</tr>".format("".join(cells)))
    return '<div class="table-wrap"><table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'.format(
        cls=cls, head=head, body="".join(body)
    )


def tag_list(items, tone="gold"):
    if not items:
        return ""
    return '<div class="tags">' + "".join(
        '<span class="tag tag-{tone}">{text}</span>'.format(tone=tone, text=esc(t))
        for t in items
    ) + "</div>"


def bullets(items, cls="bullet-list"):
    items = as_list(items)
    if not items:
        return ""
    return '<ul class="{}">{}</ul>'.format(
        cls, "".join("<li>{}</li>".format(esc(i)) for i in items)
    )


# ---------------------------------------------------------------------------
# 各章节
# ---------------------------------------------------------------------------


def build_hero(data):
    market = pick(data, "market", default={}) or {}
    code = esc(data.get("code", ""))
    name = esc(data.get("name", ""))
    full = esc(data.get("full_name") or data.get("name", ""))
    date = esc(data.get("date", datetime.date.today().isoformat()))
    industry = esc(data.get("industry", ""))
    exchange = esc(data.get("exchange", ""))

    price = fmt(pick(market, "price"), 2)
    change = pick(market, "change_pct")
    change_html = '<span class="chg {c}">{t}</span>'.format(
        c=dir_class(change), t=pct_text(change)
    )
    free_cap = yi(pick(market, "free_float_cap"))
    total_cap = yi(pick(market, "total_cap"))
    pe = fmt(pick(market, "pe_ttm"), 2)
    ytd = pick(market, "ytd_pct")
    ytd_html = '<span class="chg {c}">{t}</span>'.format(c=dir_class(ytd), t=pct_text(ytd))

    stats = [
        ("现价", '<span class="stat-value">{}</span><span class="stat-unit">元</span> {}'.format(price, change_html)),
        ("总市值", '<span class="stat-value">{}</span><span class="stat-unit">亿</span>'.format(total_cap)),
        ("自由流通市值", '<span class="stat-value">{}</span><span class="stat-unit">亿</span>'.format(free_cap)),
        ("TTM 市盈率", '<span class="stat-value">{}</span><span class="stat-unit">倍</span>'.format(pe)),
        ("年内涨幅", '<span class="stat-value {c}">{t}</span>'.format(c=dir_class(ytd), t=pct_text(ytd, plus=False)) if to_num(ytd) is not None else '<span class="stat-value">—</span>'),
    ]
    stat_html = "".join(
        '<div class="stat"><div class="stat-label">{}</div><div class="stat-main">{}</div></div>'.format(
            esc(label), value
        )
        for label, value in stats
    )

    kicker = "个股深度研究"
    if industry:
        kicker += " · " + industry
    if exchange:
        kicker += " · " + exchange

    return """
<header class="hero" id="top">
  <div class="hero-top">
    <div class="hero-kicker">{kicker}</div>
    <div class="hero-date">数据截至 {date}</div>
  </div>
  <h1 class="hero-title">
    <span class="hero-code">{code}</span>
    <span class="hero-name">{name}</span>
    <span class="hero-kind">完整个股深度股评</span>
  </h1>
  <p class="hero-sub">{code} · {full} ｜ {date_short}</p>
  <div class="stats">{stats}</div>
</header>
""".format(
        kicker=esc(kicker),
        date=date,
        code=code,
        name=name,
        full=full,
        date_short=esc(date.replace("-", ".")),
        stats=stat_html,
    )


def build_conclusion(data):
    sec = pick(data, "conclusion", default={}) or {}
    one_line = esc(sec.get("one_line", ""))
    consensus = esc(sec.get("consensus", ""))
    contrarian = esc(sec.get("contrarian", ""))
    themes = as_list(sec.get("themes"))

    parts = []
    if one_line:
        parts.append(
            '<div class="callout callout-gold"><div class="callout-label">一句话定调</div>'
            '<div class="callout-text">{}</div></div>'.format(one_line)
        )
    if consensus or contrarian:
        parts.append(
            """
<div class="grid-2">
  <div class="mini-card">
    <div class="mini-title">市场共识</div>
    <p>{consensus}</p>
  </div>
  <div class="mini-card mini-card-gold">
    <div class="mini-title">我们的不同看法</div>
    <p>{contrarian}</p>
  </div>
</div>""".format(consensus=consensus or "—", contrarian=contrarian or "—")
        )
    if themes:
        parts.append('<div class="sub-block"><div class="sub-title">核心赛道 / 热门题材</div>{}</div>'.format(tag_list(themes)))
    return "".join(parts) if parts else '<p class="muted">暂无核心结论数据。</p>'


def build_sentiment(data):
    sec = pick(data, "sentiment", default={}) or {}
    sites = as_list(sec.get("sites"))
    summary = as_list(sec.get("summary"))
    parts = []

    if sites:
        blocks = []
        for site in sites:
            if not isinstance(site, dict):
                continue
            bull = as_list(site.get("bull"))
            bear = as_list(site.get("bear"))
            posts = as_list(site.get("posts"))
            post_html = ""
            if posts:
                items = []
                for p in posts:
                    if not isinstance(p, dict):
                        continue
                    title = esc(p.get("title", ""))
                    url = esc(p.get("url", ""))
                    date = esc(p.get("date", ""))
                    gist = esc(p.get("gist", ""))
                    head = '<a href="{u}" target="_blank" rel="noopener">{t}</a>'.format(u=url, t=title) if url else title
                    meta = " · ".join(x for x in [date, gist] if x)
                    items.append(
                        '<li><div class="post-title">{head}</div><div class="post-meta">{meta}</div></li>'.format(
                            head=head, meta=esc(meta)
                        )
                    )
                if items:
                    post_html = '<div class="sub-block"><div class="sub-title">代表性贴文</div><ul class="post-list">{}</ul></div>'.format("".join(items))
            blocks.append(
                """
<div class="site-block">
  <div class="site-head"><span class="site-name">{name}</span><span class="site-stat">看多 {nb} · 看空 {ns}</span></div>
  <div class="grid-2">
    <div class="side side-bull"><div class="side-title">看多逻辑</div>{bull}</div>
    <div class="side side-bear"><div class="side-title">看空逻辑</div>{bear}</div>
  </div>
  {posts}
</div>""".format(
                    name=esc(site.get("name", "股吧")),
                    nb=len(bull),
                    ns=len(bear),
                    bull=bullets(bull) or '<p class="muted">无明显看多观点。</p>',
                    bear=bullets(bear) or '<p class="muted">无明显看空观点。</p>',
                    posts=post_html,
                )
            )
        parts.append('<div class="sites">' + "".join(blocks) + "</div>")

        # 多空力量对比图
        if any(as_list(s.get("bull")) or as_list(s.get("bear")) for s in sites if isinstance(s, dict)):
            parts.append(
                """
<div class="chart-box">
  <div class="chart-title">各平台多空观点数量对比</div>
  <div class="chart" id="chart-sentiment"></div>
</div>"""
            )

    if summary:
        parts.append('<div class="sub-block"><div class="sub-title">舆情总结</div>{}</div>'.format(bullets(summary)))
    if not parts:
        return '<p class="muted">暂未采集到近两周股吧舆情。</p>'
    return "".join(parts)


def build_limit_up(data):
    sec = pick(data, "limit_up")
    if not sec:
        return None
    concepts = as_list(sec.get("core_concepts"))
    industry_reason = esc(sec.get("industry_reason", ""))
    company_reason = esc(sec.get("company_reason", ""))
    trade = sec.get("trade") or {}
    reopen = esc(sec.get("reopen_analysis", ""))
    date = esc(sec.get("date", ""))

    parts = []
    if concepts:
        parts.append('<div class="sub-block"><div class="sub-title">核心概念</div>{}</div>'.format(tag_list(concepts, tone="hot")))
    reasons = [
        ("行业原因", industry_reason),
        ("公司原因", company_reason),
    ]
    if any(v for _, v in reasons):
        parts.append(
            '<div class="grid-2">' + "".join(
                '<div class="mini-card"><div class="mini-title">{t}</div><p>{c}</p></div>'.format(t=t, c=c or "—")
                for t, c in reasons
            ) + "</div>"
        )
    if trade:
        stats = [
            ("当日成交", fmt(trade.get("volume"), 2, unit=" 亿")),
            ("换手率", pct_text(trade.get("turnover"), 2, plus=False)),
            ("封单", fmt(trade.get("seal_amount"), 2, unit=" 万")),
            ("封板形态", esc(trade.get("form", "—"))),
        ]
        parts.append(
            '<div class="stat-row">' + "".join(
                '<div class="stat-mini"><span class="k">{k}</span><span class="v">{v}</span></div>'.format(k=esc(k), v=v)
                for k, v in stats
            ) + "</div>"
        )
    if reopen:
        parts.append('<div class="callout callout-warn"><div class="callout-label">烂板回封 · 次日方向研判</div><div class="callout-text">{}</div></div>'.format(reopen))
    return "".join(parts) if parts else None


def build_merger(data):
    sec = pick(data, "merger")
    if not sec:
        return None
    items = as_list(sec.get("items"))
    if not items:
        return None
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        rows.append([
            esc(it.get("time", "—")),
            esc(it.get("target", "—")),
            esc(it.get("business", "—")),
            esc(it.get("stage", "—")),
            esc(it.get("stake", "—")),
            esc(it.get("amount", "—")),
        ])
    if not rows:
        return None
    return data_table(
        ["时间", "标的名称", "标的主营", "当前阶段", "股权比例", "交易金额"],
        rows,
        ["left", "left", "left", "left", "right", "right"],
    )


def build_business(data):
    sec = pick(data, "business", default={}) or {}
    rows = as_list(sec.get("rows"))
    if not rows:
        return None
    basis = esc(sec.get("basis", "最新年报"))
    table_rows = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        table_rows.append([
            esc(r.get("segment", "—")),
            fmt(r.get("share"), 1, unit="%"),
            fmt(r.get("revenue"), 2),
            fmt(r.get("margin"), 1, unit="%"),
            esc(r.get("desc", "—")),
        ])
    table = data_table(
        ["业务板块", "营收占比", "年营收(亿)", "毛利率", "产品 & 下游"],
        table_rows,
        ["left", "right", "right", "right", "left"],
        cls="data-table",
    )
    return '<div class="muted small" style="margin-bottom:10px">口径：{}（营收单位：亿元）</div>{}<div class="chart-box"><div class="chart-title">营收结构</div><div class="chart chart-sm" id="chart-business"></div></div>'.format(basis, table)


def build_advantages(data):
    items = as_list(pick(data, "advantages"))
    if not items:
        return None
    cards = []
    for i, it in enumerate(items, 1):
        if isinstance(it, dict):
            title = esc(it.get("title", ""))
            text = esc(it.get("text", ""))
        else:
            title = ""
            text = esc(it)
        cards.append(
            '<div class="adv-card"><span class="adv-no">{:02d}</span><div class="adv-body"><div class="adv-title">{}</div><p>{}</p></div></div>'.format(i, title or "优势{}".format(i), text)
        )
    return '<div class="adv-list">' + "".join(cards) + "</div>"


def build_financials(data):
    sec = pick(data, "financials", default={}) or {}
    annual = sec.get("annual") or {}
    quarter = sec.get("quarter") or {}
    comment = sec.get("commentary") or {}
    trend = as_list(sec.get("trend"))

    if not annual and not quarter:
        return None

    def row(label, item):
        item = item or {}
        return [
            '<span class="strong">{}</span>'.format(esc(item.get("period", label))),
            fmt(item.get("revenue"), 2),
            '<span class="{}">{}</span>'.format(dir_class(item.get("revenue_yoy")), pct_text(item.get("revenue_yoy"))),
            fmt(item.get("net_profit"), 2),
            '<span class="{}">{}</span>'.format(dir_class(item.get("net_profit_yoy")), pct_text(item.get("net_profit_yoy"))),
            fmt(item.get("gross_margin"), 2, unit="%"),
            fmt(item.get("debt_ratio"), 2, unit="%"),
            fmt(item.get("ocf"), 2, unit=" 亿"),
        ]

    rows = []
    if annual:
        rows.append(row("最新年报", annual))
    if quarter:
        rows.append(row("最新季报", quarter))

    table = data_table(
        ["报告期", "营收(亿)", "同比", "归母净利(亿)", "同比", "综合毛利率", "资产负债率", "经营现金流"],
        rows,
        ["left", "right", "right", "right", "right", "right", "right", "right"],
        cls="data-table",
    )

    parts = [table]

    if len(trend) >= 2:
        parts.append(
            '<div class="chart-box"><div class="chart-title">营收 / 归母净利 / 毛利率 多期趋势</div><div class="chart" id="chart-trend"></div></div>'
        )

    notes = []
    if comment.get("annual"):
        notes.append(("年报", esc(comment.get("annual"))))
    if comment.get("quarter"):
        notes.append(("季报", esc(comment.get("quarter"))))
    if comment.get("inflection"):
        notes.append(("财务拐点信号", esc(comment.get("inflection"))))
    if notes:
        parts.append(
            '<div class="sub-block"><div class="sub-title">财报解读</div><ol class="num-list">' + "".join(
                "<li><b>{}</b>：{}</li>".format(k, v) for k, v in notes
            ) + "</ol></div>"
        )
    summary = as_list(comment.get("summary"))
    if summary:
        parts.append('<div class="sub-block"><div class="sub-title">财务总结</div>{}</div>'.format(bullets(summary)))
    return "".join(parts)


def build_research(data):
    sec = pick(data, "research")
    if not sec:
        return None
    if sec.get("empty"):
        return None
    ratings = sec.get("ratings") or {}
    count = sec.get("count")
    if not count and not ratings:
        return None

    window = esc(sec.get("window", "近60日"))
    buy = int(to_num(ratings.get("buy")) or 0)
    add = int(to_num(ratings.get("add")) or 0)
    neutral = int(to_num(ratings.get("neutral")) or 0)
    sell = int(to_num(ratings.get("sell")) or 0)
    total = buy + add + neutral + sell

    stats = [
        ("覆盖机构", "{} 家".format(fmt(count, 0) if count is not None else (total or "—"))),
        ("买入", "{} 家".format(buy)),
        ("增持", "{} 家".format(add)),
        ("中性", "{} 家".format(neutral)),
    ]
    target_low = pick(sec, "target_low")
    target_high = pick(sec, "target_high")
    if target_low or target_high:
        stats.append(("目标价区间", "{} - {} 元".format(fmt(target_low, 2), fmt(target_high, 2))))

    parts = [
        '<div class="stat-row">' + "".join(
            '<div class="stat-mini"><span class="k">{k}</span><span class="v">{v}</span></div>'.format(k=esc(k), v=v)
            for k, v in stats
        ) + "</div>"
    ]
    if total:
        parts.append('<div class="chart-box"><div class="chart-title">{} 评级分布</div><div class="chart chart-sm" id="chart-rating"></div></div>'.format(window))

    blocks = []
    if as_list(sec.get("consensus")):
        blocks.append('<div class="mini-card"><div class="mini-title">机构一致看多逻辑</div>{}</div>'.format(bullets(as_list(sec.get("consensus")))))
    if as_list(sec.get("disputes")):
        blocks.append('<div class="mini-card"><div class="mini-title">机构分歧点</div>{}</div>'.format(bullets(as_list(sec.get("disputes")))))
    if blocks:
        parts.append('<div class="grid-2">' + "".join(blocks) + "</div>")
    if as_list(sec.get("warnings")):
        parts.append('<div class="callout callout-warn"><div class="callout-label">需警惕的机构信号</div>{}</div>'.format(bullets(as_list(sec.get("warnings")))))
    if sec.get("conclusion"):
        parts.append('<div class="sub-block"><div class="sub-title">总结</div><p>{}</p></div>'.format(esc(sec.get("conclusion"))))
    return "".join(parts)


def build_risks(data):
    risks = as_list(pick(data, "risks"))
    if not risks:
        return None
    return '<ul class="risk-list">' + "".join(
        '<li><span class="risk-mark">!</span><span>{}</span></li>'.format(esc(r)) for r in risks
    ) + "</ul>"


def build_sources(data):
    sources = as_list(pick(data, "sources"))
    disclaimer = pick(data, "disclaimer") or "本报告由 AI 依据公开资料整理，仅用于信息研究，不构成任何投资建议。市场有风险，决策需谨慎。"
    parts = []
    if sources:
        lis = []
        for s in sources:
            if not isinstance(s, dict):
                continue
            title = esc(s.get("title", ""))
            url = esc(s.get("url", ""))
            if url:
                lis.append('<li><a href="{u}" target="_blank" rel="noopener">{t}</a></li>'.format(u=url, t=title or url))
            else:
                lis.append("<li>{}</li>".format(title))
        if lis:
            parts.append('<div class="sub-block"><div class="sub-title">数据与信息来源</div><ul class="src-list">{}</ul></div>'.format("".join(lis)))
    parts.append('<div class="disclaimer">{}</div>'.format(esc(disclaimer)))
    parts.append('<div class="gen-note">生成器：dsh-stock-review · 单文件离线渲染</div>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# 页面骨架
# ---------------------------------------------------------------------------

CSS = """
:root{
  --bg:#0b1628; --bg-2:#0e1b33; --panel:#111f3a; --panel-2:#16284a;
  --line:rgba(245,192,99,.14); --line-strong:rgba(245,192,99,.38);
  --gold:#f5c063; --gold-dim:#c99b45; --text:#e8eefc; --muted:#93a6c4;
  --up:#ff5b5b; --down:#2ecc8f; --shadow:0 18px 40px rgba(0,0,0,.38);
  --radius:16px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--text);
  font-family:"Inter","PingFang SC","Microsoft YaHei","Noto Sans SC",system-ui,sans-serif;
  line-height:1.75; font-size:15px;
  background-image:
    radial-gradient(1200px 500px at 12% -8%, rgba(245,192,99,.10), transparent 62%),
    radial-gradient(900px 420px at 92% 2%, rgba(56,132,255,.14), transparent 60%),
    radial-gradient(800px 500px at 50% 110%, rgba(22,40,74,.65), transparent 70%);
  background-attachment:fixed;
}
a{color:var(--gold); text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1180px; margin:0 auto; padding:0 22px}
.muted{color:var(--muted)}
.small{font-size:13px}
.up{color:var(--up)}
.down{color:var(--down)}
.flat{color:var(--muted)}
.strong{color:var(--gold); font-weight:600}

/* ---------- 顶部导航 ---------- */
.nav{
  position:sticky; top:0; z-index:60;
  background:rgba(11,22,40,.82); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  border-bottom:1px solid rgba(245,192,99,.12);
}
.nav-inner{max-width:1180px; margin:0 auto; padding:0 22px; display:flex; align-items:center; gap:6px; height:58px}
.brand{display:flex; align-items:center; gap:10px; margin-right:14px; flex-shrink:0}
.brand-mark{
  width:30px; height:30px; border-radius:9px; display:grid; place-items:center;
  background:linear-gradient(145deg,#f5c063,#c99b45); color:#20160a; font-weight:800; font-size:15px;
  box-shadow:0 6px 16px rgba(245,192,99,.28)
}
.brand-text{font-weight:700; letter-spacing:.5px; font-size:14px; color:#f7e9c9}
.brand-text small{display:block; font-size:10px; letter-spacing:2px; color:var(--muted); font-weight:500}
.nav-links{display:flex; gap:2px; overflow-x:auto; scrollbar-width:none}
.nav-links::-webkit-scrollbar{display:none}
.nav a.nav-link{
  color:var(--muted); font-size:13px; padding:6px 10px; border-radius:8px; white-space:nowrap;
  border:1px solid transparent; transition:.18s
}
.nav a.nav-link:hover{color:var(--text); background:rgba(255,255,255,.05); text-decoration:none}
.nav a.nav-link.active{color:var(--gold); border-color:rgba(245,192,99,.35); background:rgba(245,192,99,.08)}

/* ---------- Hero ---------- */
.hero{padding:52px 0 30px}
.hero-top{display:flex; justify-content:space-between; align-items:center; gap:14px; flex-wrap:wrap}
.hero-kicker{font-size:12px; letter-spacing:3px; color:var(--gold); text-transform:uppercase}
.hero-date{font-size:12px; color:var(--muted)}
.hero-title{margin:16px 0 8px; font-size:40px; line-height:1.2; letter-spacing:.5px; font-weight:800}
.hero-code{color:var(--gold); font-variant-numeric:tabular-nums}
.hero-name{color:#fff; margin-left:10px}
.hero-kind{
  display:inline-block; margin-left:12px; font-size:14px; font-weight:600; letter-spacing:2px;
  color:var(--gold-dim); border-left:2px solid var(--line-strong); padding-left:12px; vertical-align:middle
}
.hero-sub{color:var(--muted); font-size:13px; margin:6px 0 26px; letter-spacing:.4px}
.stats{display:grid; grid-template-columns:repeat(5,1fr); gap:14px}
.stat{
  background:linear-gradient(160deg,rgba(22,40,74,.92),rgba(15,27,50,.92));
  border:1px solid var(--line); border-radius:14px; padding:16px 18px;
  box-shadow:var(--shadow); transition:transform .22s ease, border-color .22s ease, box-shadow .22s ease;
}
.stat:hover{transform:translateY(-3px); border-color:var(--line-strong); box-shadow:0 22px 46px rgba(0,0,0,.5)}
.stat-label{font-size:12px; color:var(--muted); letter-spacing:1px}
.stat-main{margin-top:6px; font-size:23px; font-weight:700; font-variant-numeric:tabular-nums; display:flex; align-items:baseline; gap:4px; flex-wrap:wrap}
.stat-value{font-variant-numeric:tabular-nums}
.stat-unit{font-size:12px; color:var(--muted); font-weight:500; margin-left:2px}
.chg{font-size:13px; font-weight:600; margin-left:4px}

/* ---------- 卡片 ---------- */
main{padding-bottom:40px}
.card{
  background:linear-gradient(170deg,rgba(17,31,58,.96),rgba(13,24,45,.96));
  border:1px solid var(--line); border-radius:var(--radius);
  box-shadow:var(--shadow); margin:22px 0; overflow:hidden;
  transition:transform .22s ease, border-color .22s ease, box-shadow .22s ease;
  scroll-margin-top:78px;
}
.card:hover{transform:translateY(-2px); border-color:rgba(245,192,99,.30); box-shadow:0 24px 50px rgba(0,0,0,.5)}
.card-head{display:flex; align-items:center; gap:14px; padding:18px 24px; border-bottom:1px solid rgba(255,255,255,.05)}
.idx{
  width:32px; height:32px; flex-shrink:0; border-radius:10px; display:grid; place-items:center;
  border:1px solid rgba(245,192,99,.45); color:var(--gold); font-weight:700; font-size:14px;
  background:rgba(245,192,99,.07)
}
.card-head h2{margin:0; font-size:19px; letter-spacing:.5px; font-weight:700; color:#fff}
.card-sub{font-size:12px; color:var(--muted); margin-left:auto; margin-right:8px}
.toggle{
  margin-left:auto; display:flex; align-items:center; gap:8px; background:transparent;
  border:1px solid rgba(255,255,255,.12); color:var(--muted); border-radius:999px;
  padding:5px 12px; font-size:12px; cursor:pointer; transition:.18s; font-family:inherit
}
.card-sub + .toggle{margin-left:0}
.toggle:hover{color:var(--gold); border-color:var(--line-strong); background:rgba(245,192,99,.06)}
.chev{width:7px; height:7px; border-right:1.6px solid currentColor; border-bottom:1.6px solid currentColor; transform:rotate(45deg); transition:transform .25s}
.card.collapsed .chev{transform:rotate(-135deg)}
.card-body{display:grid; grid-template-rows:1fr; transition:grid-template-rows .3s ease}
.card.collapsed .card-body{grid-template-rows:0fr}
.card-inner{overflow:hidden; padding:24px; transition:padding .3s ease}
.card.collapsed .card-inner{padding-top:0; padding-bottom:0}

/* ---------- 通用组件 ---------- */
.grid-2{display:grid; grid-template-columns:1fr 1fr; gap:16px}
.mini-card{background:rgba(255,255,255,.028); border:1px solid rgba(255,255,255,.07); border-radius:12px; padding:16px 18px; transition:.2s}
.mini-card:hover{background:rgba(255,255,255,.05); border-color:rgba(245,192,99,.25)}
.mini-card-gold{border-color:rgba(245,192,99,.35); background:linear-gradient(160deg,rgba(245,192,99,.10),rgba(245,192,99,.03))}
.mini-title{font-size:13px; color:var(--gold); font-weight:700; letter-spacing:1px; margin-bottom:6px}
.mini-card p{margin:0; font-size:14px; color:#dbe6fb}
.callout{border-radius:12px; padding:16px 18px; margin:16px 0; border:1px solid rgba(255,255,255,.08); background:rgba(255,255,255,.03)}
.callout-gold{border-color:rgba(245,192,99,.4); background:linear-gradient(120deg,rgba(245,192,99,.13),rgba(245,192,99,.03)); position:relative}
.callout-gold::before{content:""; position:absolute; left:0; top:14px; bottom:14px; width:3px; border-radius:3px; background:var(--gold)}
.callout-warn{border-color:rgba(255,120,90,.38); background:rgba(255,91,91,.07)}
.callout-label{font-size:12px; letter-spacing:2px; color:var(--gold); font-weight:700; margin-bottom:6px}
.callout-warn .callout-label{color:#ff9a85}
.callout-text{font-size:15px; color:#eef3ff}
.sub-block{margin-top:18px}
.sub-title{font-size:13px; letter-spacing:2px; color:var(--gold-dim); font-weight:700; margin-bottom:8px}
.bullet-list{margin:6px 0 0; padding-left:20px; color:#d9e3f7}
.bullet-list li{margin:5px 0}
.num-list{margin:6px 0 0; padding-left:22px; color:#d9e3f7}
.num-list li{margin:7px 0}
.tags{display:flex; flex-wrap:wrap; gap:8px}
.tag{
  font-size:12.5px; padding:4px 12px; border-radius:999px; border:1px solid rgba(245,192,99,.35);
  color:var(--gold); background:rgba(245,192,99,.07); transition:.18s
}
.tag:hover{background:rgba(245,192,99,.16)}
.tag-hot{border-color:rgba(255,91,91,.4); color:#ff9a9a; background:rgba(255,91,91,.08)}
.stat-row{display:flex; flex-wrap:wrap; gap:12px; margin:16px 0}
.stat-mini{
  display:flex; flex-direction:column; gap:2px; padding:10px 16px; border-radius:10px;
  background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.07); min-width:120px
}
.stat-mini .k{font-size:11.5px; color:var(--muted); letter-spacing:1px}
.stat-mini .v{font-size:16px; font-weight:700; color:#fff; font-variant-numeric:tabular-nums}

/* 表格 */
.table-wrap{overflow-x:auto; margin-top:14px; border-radius:12px; border:1px solid rgba(255,255,255,.07)}
table{border-collapse:collapse; width:100%; font-size:13.5px}
thead th{
  background:rgba(245,192,99,.09); color:var(--gold); font-weight:700; letter-spacing:.6px;
  padding:11px 12px; border-bottom:1px solid rgba(245,192,99,.18); white-space:nowrap
}
tbody td{padding:10px 12px; border-bottom:1px solid rgba(255,255,255,.05); color:#dde6f8; vertical-align:top}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:rgba(245,192,99,.045)}
th.left,td.left{text-align:left}
th.right,td.right{text-align:right; font-variant-numeric:tabular-nums}
.kv-table th{width:150px; text-align:left; background:transparent; color:var(--muted); font-weight:500; border-bottom:1px solid rgba(255,255,255,.05)}
.kv-table td{border-bottom:1px solid rgba(255,255,255,.05)}

/* 舆情 */
.sites{display:flex; flex-direction:column; gap:16px}
.site-block{background:rgba(255,255,255,.022); border:1px solid rgba(255,255,255,.07); border-radius:12px; padding:16px 18px}
.site-head{display:flex; align-items:center; justify-content:space-between; margin-bottom:10px}
.site-name{font-weight:700; color:#fff; letter-spacing:1px}
.site-name::before{content:""; display:inline-block; width:6px; height:6px; border-radius:2px; background:var(--gold); margin-right:8px; vertical-align:middle}
.site-stat{font-size:12px; color:var(--muted)}
.side{border-radius:10px; padding:12px 14px; border:1px solid rgba(255,255,255,.06)}
.side-bull{background:rgba(255,91,91,.05); border-color:rgba(255,91,91,.18)}
.side-bear{background:rgba(46,204,143,.05); border-color:rgba(46,204,143,.18)}
.side-title{font-size:12px; font-weight:700; letter-spacing:1.5px; margin-bottom:4px}
.side-bull .side-title{color:#ff8f8f}
.side-bear .side-title{color:#5fdbb0}
.side .bullet-list{color:#d6e0f4; font-size:13.5px}
.post-list{list-style:none; padding:0; margin:8px 0 0; display:flex; flex-direction:column; gap:8px}
.post-list li{border-left:2px solid rgba(245,192,99,.3); padding-left:12px}
.post-title{font-size:13.5px}
.post-meta{font-size:11.5px; color:var(--muted); margin-top:2px}

/* 优势 */
.adv-list{display:flex; flex-direction:column; gap:12px}
.adv-card{display:flex; gap:16px; padding:16px 18px; border-radius:12px; background:rgba(255,255,255,.028); border:1px solid rgba(255,255,255,.07); transition:.2s}
.adv-card:hover{border-color:rgba(245,192,99,.3); background:rgba(245,192,99,.045)}
.adv-no{font-size:22px; font-weight:800; color:rgba(245,192,99,.55); font-variant-numeric:tabular-nums; line-height:1.2}
.adv-title{font-weight:700; color:#fff; margin-bottom:4px}
.adv-card p{margin:0; color:#d6e0f4; font-size:14px}

/* 风险 */
.risk-list{list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:10px}
.risk-list li{display:flex; gap:12px; align-items:flex-start; padding:12px 16px; border-radius:10px; background:rgba(255,91,91,.05); border:1px solid rgba(255,91,91,.16); color:#f2dcdc; font-size:14px}
.risk-mark{width:20px; height:20px; flex-shrink:0; border-radius:50%; display:grid; place-items:center; background:rgba(255,91,91,.2); color:#ff8f8f; font-size:12px; font-weight:800; margin-top:2px}

/* 图表 */
.chart-box{margin-top:18px; border:1px solid rgba(255,255,255,.07); border-radius:12px; padding:14px 16px; background:rgba(255,255,255,.02)}
.chart-title{font-size:12.5px; letter-spacing:1.5px; color:var(--muted); margin-bottom:6px}
.chart{width:100%; height:330px}
.chart-sm{height:290px}
.chart-fallback{padding:24px; text-align:center; color:var(--muted); font-size:13px; display:none}

/* 页脚 */
.footer{border-top:1px solid rgba(255,255,255,.06); margin-top:34px; padding:26px 0 40px; color:var(--muted); font-size:12px}
.footer-inner{display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap}
.disclaimer{background:rgba(255,255,255,.025); border:1px dashed rgba(255,255,255,.12); border-radius:12px; padding:14px 18px; color:var(--muted); font-size:12.5px; line-height:1.8}
.gen-note{text-align:right; color:#5f7292; font-size:11.5px; margin-top:10px}
.src-list{margin:6px 0 0; padding-left:20px; font-size:13px; columns:2; column-gap:28px}
.src-list li{margin:4px 0; break-inside:avoid}

/* 示例数据提示条 */
.demo-bar{
  background:linear-gradient(90deg,rgba(255,138,92,.22),rgba(255,91,91,.10));
  border-bottom:1px solid rgba(255,138,92,.35); color:#ffb39a;
  font-size:12.5px; letter-spacing:1px; text-align:center; padding:7px 16px
}

/* 回到顶部 */
.to-top{
  position:fixed; right:26px; bottom:30px; z-index:80; width:42px; height:42px; border-radius:12px;
  border:1px solid var(--line-strong); background:rgba(17,31,58,.92); color:var(--gold);
  display:grid; place-items:center; cursor:pointer; opacity:0; pointer-events:none; transition:.25s;
  font-size:16px
}
.to-top.show{opacity:1; pointer-events:auto}
.to-top:hover{background:rgba(245,192,99,.14)}

/* 响应式 */
@media (max-width: 900px){
  .hero-title{font-size:28px}
  .hero-kind{display:block; margin:10px 0 0; border-left:none; padding-left:0}
  .stats{grid-template-columns:repeat(2,1fr)}
  .grid-2{grid-template-columns:1fr}
  .stat-row{gap:8px}
  .src-list{columns:1}
  .card-inner{padding:18px}
  .nav-links{display:none}
}
@media print{
  body{background:#fff; color:#111}
  .nav,.to-top,.toggle{display:none !important}
  .card{break-inside:avoid; box-shadow:none; border:1px solid #ddd}
  .card-body{grid-template-rows:1fr !important}
}
"""

JS = r"""
(function(){
  var DATA = window.__STOCK_REVIEW__ || {};
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));

  // 折叠/展开
  cards.forEach(function(card){
    var btn = card.querySelector('.toggle');
    if(!btn) return;
    btn.addEventListener('click', function(){
      var collapsed = card.classList.toggle('collapsed');
      btn.setAttribute('aria-expanded', String(!collapsed));
      btn.querySelector('.toggle-label').textContent = collapsed ? '展开' : '收起';
    });
  });

  // 导航高亮
  var links = Array.prototype.slice.call(document.querySelectorAll('.nav-link'));
  if('IntersectionObserver' in window){
    var map = {};
    links.forEach(function(a){ map[a.getAttribute('href').slice(1)] = a; });
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if(e.isIntersecting){
          links.forEach(function(a){ a.classList.remove('active'); });
          var link = map[e.target.id];
          if(link) link.classList.add('active');
        }
      });
    }, {rootMargin:'-45% 0px -50% 0px'});
    cards.forEach(function(c){ io.observe(c); });
  }

  // 回到顶部
  var top = document.querySelector('.to-top');
  if(top){
    window.addEventListener('scroll', function(){
      top.classList.toggle('show', window.scrollY > 500);
    }, {passive:true});
    top.addEventListener('click', function(){ window.scrollTo({top:0, behavior:'smooth'}); });
  }

  // 示例横幅
  if(DATA.demo){
    var bar = document.createElement('div');
    bar.className = 'demo-bar';
    bar.textContent = '示例数据 · 仅用于验证页面渲染，不代表真实研究结论';
    document.body.insertBefore(bar, document.body.firstChild);
  }

  // 图表
  if(!window.echarts){
    document.querySelectorAll('.chart').forEach(function(el){
      el.innerHTML = '<div class="chart-fallback" style="display:block">ECharts CDN 未加载，图表暂不可用（离线环境）。表格数据不受影响。</div>';
    });
    return;
  }

  var GOLD = '#f5c063', UP = '#ff5b5b', DOWN = '#2ecc8f', TEXT = '#dbe6fb', MUTED = '#93a6c4', LINE = 'rgba(255,255,255,.07)';
  var axisCommon = {
    axisLine: { lineStyle: { color: 'rgba(255,255,255,.16)' } },
    axisLabel: { color: MUTED, fontSize: 11 },
    splitLine: { lineStyle: { color: LINE } }
  };
  function chart(id, option){
    var el = document.getElementById(id);
    if(!el) return;
    var instance = echarts.init(el, null, {renderer:'canvas'});
    instance.setOption(option);
    window.addEventListener('resize', function(){ instance.resize(); });
    document.addEventListener('click', function(e){
      if(e.target && e.target.closest && e.target.closest('.toggle')) setTimeout(function(){ instance.resize(); }, 320);
    });
  }
  function has(id){ return document.getElementById(id) !== null; }

  // 多空对比
  if(has('chart-sentiment')){
    var sites = (DATA.sentiment && DATA.sentiment.sites) || [];
    var names = sites.map(function(s){ return s.name; });
    chart('chart-sentiment', {
      backgroundColor:'transparent',
      tooltip:{trigger:'axis', axisPointer:{type:'shadow'}},
      legend:{data:['看多','看空'], textStyle:{color:MUTED}, top:0, right:0},
      grid:{left:8, right:18, top:36, bottom:6, containLabel:true},
      xAxis:{type:'value', ...axisCommon, splitLine:{lineStyle:{color:LINE}}},
      yAxis:{type:'category', data:names, ...axisCommon, axisLine:{lineStyle:{color:'rgba(255,255,255,.16)'}}},
      series:[
        {name:'看多', type:'bar', stack:'total', data:sites.map(function(s){return (s.bull||[]).length}),
         itemStyle:{color:UP, borderRadius:[0,0,0,0]}, barWidth:16},
        {name:'看空', type:'bar', stack:'total', data:sites.map(function(s){return (s.bear||[]).length}),
         itemStyle:{color:DOWN}, barWidth:16}
      ]
    });
  }

  // 营收结构
  if(has('chart-business')){
    var rows = (DATA.business && DATA.business.rows) || [];
    chart('chart-business', {
      backgroundColor:'transparent',
      tooltip:{trigger:'item', formatter:'{b}<br/>营收占比 {d}%（营收 {c} 亿元）'},
      legend:{orient:'vertical', right:10, top:'middle', textStyle:{color:MUTED, fontSize:12}},
      series:[{
        type:'pie', radius:['46%','72%'], center:['34%','52%'], avoidLabelOverlap:true,
        itemStyle:{borderColor:'#0b1628', borderWidth:3},
        label:{color:TEXT, formatter:'{b}\n{d}%', fontSize:11},
        labelLine:{lineStyle:{color:'rgba(245,192,99,.35)'}},
        data: rows.map(function(r){ return {name:r.segment, value: r.share, revenue: r.revenue}; }),
        color:['#f5c063','#5b9dff','#2ecc8f','#ff8a5c','#9d7bff','#57c7d4']
      }]
    });
  }

  // 评级分布
  if(has('chart-rating')){
    var r = (DATA.research && DATA.research.ratings) || {};
    var data = [
      {name:'买入', value: r.buy||0},
      {name:'增持', value: r.add||0},
      {name:'中性', value: r.neutral||0},
      {name:'减持/卖出', value: r.sell||0}
    ].filter(function(d){ return d.value > 0; });
    chart('chart-rating', {
      backgroundColor:'transparent',
      tooltip:{trigger:'item', formatter:'{b}：{c} 家（{d}%）'},
      legend:{bottom:0, textStyle:{color:MUTED}},
      series:[{
        type:'pie', radius:['48%','74%'], center:['50%','46%'],
        itemStyle:{borderColor:'#0b1628', borderWidth:3},
        label:{color:TEXT, formatter:'{b} {c}家', fontSize:11},
        data:data,
        color:['#ff5b5b','#f5c063','#93a6c4','#2ecc8f']
      }]
    });
  }

  // 趋势
  if(has('chart-trend')){
    var trend = (DATA.financials && DATA.financials.trend) || [];
    chart('chart-trend', {
      backgroundColor:'transparent',
      tooltip:{trigger:'axis'},
      legend:{top:0, textStyle:{color:MUTED}, data:['营收(亿)','归母净利(亿)','毛利率(%)']},
      grid:{left:8, right:8, top:44, bottom:6, containLabel:true},
      xAxis:{type:'category', data:trend.map(function(t){return t.period}), ...axisCommon},
      yAxis:[
        {type:'value', name:'亿元', nameTextStyle:{color:MUTED}, ...axisCommon},
        {type:'value', name:'%', nameTextStyle:{color:MUTED}, ...axisCommon, min:'dataMin', splitLine:{show:false}}
      ],
      series:[
        {name:'营收(亿)', type:'bar', data:trend.map(function(t){return t.revenue}), barWidth:14,
         itemStyle:{color:'rgba(91,157,255,.75)', borderRadius:[4,4,0,0]}},
        {name:'归母净利(亿)', type:'bar', data:trend.map(function(t){return t.net_profit}), barWidth:14,
         itemStyle:{color:'rgba(245,192,99,.8)', borderRadius:[4,4,0,0]}},
        {name:'毛利率(%)', type:'line', yAxisIndex:1, data:trend.map(function(t){return t.gross_margin}),
         smooth:true, symbolSize:6, lineStyle:{color:UP, width:2.4}, itemStyle:{color:UP}}
      ]
    });
  }
})();
"""


def render(data):
    sections = []

    def add(title, body, sid, subtitle=""):
        if body:
            sections.append({"id": sid, "title": title, "body": body, "subtitle": subtitle})

    add("核心结论", build_conclusion(data), "s-conclusion")
    add("舆情分析总结", build_sentiment(data), "s-sentiment", "近两周各大股吧贴文")
    add("涨停分析", build_limit_up(data), "s-limitup", "近60日")
    add("并购重组", build_merger(data), "s-merger", "近半年")
    add("业务结构", build_business(data), "s-business", "最新年报口径")
    add("核心优势", build_advantages(data), "s-advantage")
    add("财报点评", build_financials(data), "s-finance", "最新年报 + 最新季报")
    add("券商研报点评", build_research(data), "s-research", "近60日")
    add("精简风险提示", build_risks(data), "s-risk")
    add("数据来源与免责", build_sources(data), "s-source")

    nav_items = []
    cards = []
    for i, sec in enumerate(sections):
        idx = CN_NUM[i] if i < len(CN_NUM) else str(i + 1)
        nav_items.append('<a class="nav-link" href="#{sid}">{idx}、{title}</a>'.format(sid=sec["id"], idx=idx, title=esc(sec["title"])))
        cards.append(card(sec["id"], idx, sec["title"], sec["body"], sec["subtitle"]))

    hero = build_hero(data)
    name = esc(data.get("name", ""))
    code = esc(data.get("code", ""))
    date = esc(data.get("date", datetime.date.today().isoformat()))
    page_title = "【{code}】【{name}】完整个股深度股评｜{date}".format(code=code, name=name, date=date.replace("-", "."))

    page = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<meta name="description" content="{name}（{code}）个股深度股评：核心结论、舆情分析、涨停复盘、业务结构、财报点评、券商研报与风险提示。">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
<style>{css}</style>
</head>
<body>
<nav class="nav">
  <div class="nav-inner">
    <div class="brand">
      <span class="brand-mark">评</span>
      <span class="brand-text">个股深度股评<small>STOCK REVIEW</small></span>
    </div>
    <div class="nav-links">{nav}</div>
  </div>
</nav>

<div class="wrap">
{hero}
</div>

<main class="wrap" id="main">
{cards}
</main>

<footer class="footer">
  <div class="wrap footer-inner">
    <div>© {year} 个股深度股评 · 结构化研究框架</div>
    <div>数据来自公开渠道，可能存在延迟或偏差，请以交易所与公司公告为准。</div>
  </div>
</footer>

<button class="to-top" type="button" aria-label="回到顶部">↑</button>
<script>window.__STOCK_REVIEW__ = {data_json};</script>
<script>{js}</script>
</body>
</html>
""".format(
        page_title=esc(page_title),
        name=name,
        code=code,
        css=CSS,
        nav="".join(nav_items),
        hero=hero,
        cards="".join(cards),
        year=datetime.date.today().year,
        data_json=json.dumps(
            {
                "demo": bool(pick(data, "demo")),
                "sentiment": pick(data, "sentiment", default={}),
                "business": pick(data, "business", default={}),
                "research": pick(data, "research", default={}),
                "financials": pick(data, "financials", default={}),
            },
            ensure_ascii=False,
        ).replace("</", "<\\/"),
        js=JS,
    )
    return page


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="个股深度股评 -> 单文件 HTML")
    parser.add_argument("data", help="股评数据 JSON 文件路径")
    parser.add_argument("-o", "--output", help="输出 HTML 路径")
    parser.add_argument("--open", action="store_true", help="生成后用默认浏览器打开")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    with open(args.data, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)

    code = str(data.get("code") or "stock")
    date = str(data.get("date") or datetime.date.today().isoformat())
    output = args.output or os.path.join(
        os.path.dirname(os.path.abspath(args.data)),
        "{}_股评_{}.html".format(code, date.replace("/", "-")),
    )

    page = render(data)
    with open(output, "w", encoding="utf-8") as fh:
        fh.write(page)

    print("[ok] 已生成：{}".format(output))
    print("[ok] 标题：{}".format(
        "【{}】【{}】完整个股深度股评｜{}".format(code, data.get("name", ""), date.replace("-", "."))
    ))
    size = os.path.getsize(output) / 1024.0
    print("[ok] 体积：{:.1f} KB（单文件，ECharts 走 CDN）".format(size))

    if args.open:
        try:
            os.startfile(output)  # type: ignore[attr-defined]
        except Exception:
            import subprocess
            subprocess.Popen(["cmd", "/c", "start", "", output])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
