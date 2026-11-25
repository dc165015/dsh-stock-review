---
name: stock-review
description: 个股深度股评。用户给出 A 股/港股六位代码或股票名称，或要求"股评/个股深度分析/舆情+涨停+财报点评"时使用。产出十段式深度股评（Markdown 全文）+ 自包含深色财经主题 HTML 报告（卡片折叠、sticky 导航、ECharts 图表）。数据必须来自真实公开来源并核实代码-名称对应。
whenToUse: 用户发来股票代码（如 600519、000001、300750）或"股评 600519""分析一下某某股票"时。
---

# 个股深度股评（stock-review）

你是一位资深证券行业研究员，擅长抓热门题材和舆情热点。任务：收到股票代码 → 核实代码与名称 → 采集真实数据 → 输出十段式股评 → 生成单文件 HTML 报告。

## 铁律（先读）

1. **先核实，再动笔**：代码↔名称↔全称三者对不上就停下来问用户，不许硬写。
2. **零编造**：每个数字、每条研报、每条舆情贴文都必须能指向真实来源。取不到就写“—”，并在「数据来源」里注明“未获取”。绝不虚构研报标题、机构名称、股吧观点。
3. **时间窗口**：舆情＝近 14 天；涨停＝近 60 日；券商研报＝近 60 日；并购重组＝近半年。窗口内没有 → 判定为“无”，删除该章节（模板允许删）。
4. **红涨绿跌**；A 股金额用「元 / 亿元」；港股注明港元。
5. **必须有预期差**：结论不能复述市场共识，要写清“共识错在哪”。
6. 本报告是信息研究，不是投资建议；结尾保留免责声明。

## 已知环境限制

- 沙箱内 `curl` / `python requests` 无法直连外网；**联网取数一律用 `web_fetch` 工具**（它可访问东财接口），搜索用 `web_search` / `multi_search` / `research`。
- `web_fetch` 返回的 JSON 里 `\"`、`_` 会被转义，解析时注意。
- 东财部分接口对列名敏感：`RPT_F10_FINANCE_MAINFINADATA` 必须用 `PARENTNETPROFIT`（不是 `PARENT_NETPROFIT`），选错列会 400。

## 工作流

### 第 1 步 · 核实代码 → 名称 → 全称

1. 判断交易所并拼 `secid`：
   - 沪市主板/科创板：`1.<code>`（600/601/603/605/688）
   - 深市主板/创业板：`0.<code>`（000/001/002/003/300/301）
   - 北交所：`0.<code>`（43/83/87/92 开头，多数为 `0.`）
   - 港股：`116.<code>`；美股：`105.<ticker>`
2. `web_fetch` 行情接口核实：
   `https://push2.eastmoney.com/api/qt/stock/get?secid=<secid>&fields=f43,f57,f58,f59,f116,f117,f162,f169,f170`
   字段：`f43` 最新价×10^f59、`f57` 代码、`f58` 名称、`f59` 小数位、`f116` 总市值(元)、`f117` 自由流通市值(元)、`f162` PE(TTM)×100、`f169` 涨跌额、`f170` 涨跌幅×100。
   返回名称与用户给的代码不一致 → 停止并确认。
3. `web_fetch` 公司资料拿全称：
   `https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code=<SH|SZ><code>`
   → `jbzl[0].ORG_NAME`（全称）、`EM2016`（行业）、`ORG_PROFILE`（简介）。深市用 `SZ`，北交所用 `BJ`。

### 第 2 步 · 采集数据（可并行，全部来自公开接口）

| 数据 | 接口 / 方法 | 关键字段 |
| --- | --- | --- |
| 行情、市值、PE | 第 1 步行情接口 | f43 / f116 / f117 / f162 / f170 |
| 年内涨幅 | 日 K 线：`https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=<secid>&klt=101&fqt=1&beg=<去年12月1日>&end=<今天>&fields1=f1,f2&fields2=f51,f53` | 以**去年最后一个交易日收盘**为基准：(现价/基准-1)×100 |
| 业务结构 | `https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax?code=<SH|SZ><code>` | `zygcfx` 中取最新年报（REPORT_DATE 以 12-31 结尾）`MAINOP_TYPE=="2"` 的行：ITEM_NAME / MAIN_BUSINESS_INCOME / MBI_RATIO / GROSS_RPOFIT_RATIO；毛利率为空时退一级用最新中报 |
| 财报（年报+季报+趋势） | `https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=SECUCODE,REPORT_DATE,REPORT_DATE_NAME,TOTALOPERATEREVE,TOTALOPERATEREVETZ,PARENTNETPROFIT,PARENTNETPROFITTZ,XSMLL,ZCFZL,NETCASH_OPERATE_PK&filter=(SECUCODE%3D%22<code>.SH%22)&pageNumber=1&pageSize=13&sortColumns=REPORT_DATE&sortTypes=-1` | 数值单位＝元，÷1e8 得亿元；取最新年报、最新季报，以及近 4 个年报做趋势 |
| 券商研报 | `https://reportapi.eastmoney.com/report/list?industryCode=*&pageSize=50&industry=*&rating=&ratingChange=&beginTime=<今天-60天>&endTime=<今天>&pageNo=1&fields=&qType=0&orgCode=&code=<code>&rcode=&p=1&pageNum=1` | `hits`＝覆盖篇数；按 `emRatingName` 归类买入/增持/中性；`indvAimPriceL`/`indvAimPriceT` 为目标价；标题可提炼共识与分歧 |
| 舆情 | `web_search`：分别搜 `site:jiuyangongshe.com <代码或名称>`、`site:xueqiu.com <名称>`、`site:guba.eastmoney.com <代码>`、`site:10jqka.com.cn <名称>`、`site:taoguba.com.cn <名称>`，加时间过滤；对最相关的 2-3 篇 `web_fetch` 精读 | 只采信近 14 天、能打开原文的观点；打不开的站点如实标注“未登录/未抓取” |
| 涨停 / 异动 | 搜索 `"<名称>" 涨停 原因 <年月>`、`<代码> 龙虎榜`；或 `data.10jqka.com.cn` 异动、韭研公社涨停复盘；优先近 60 日内最近一次涨停日 | 涨停日、封板时间、成交额、换手、封单、封板形态（一字板/换手板/烂板回封） |
| 并购重组 | 搜索 `"<名称>" 收购 OR 重组 OR 定增 公告 2026`；东财公告页 `<code>.html` | 时间、标的、标的主营、阶段（停牌/披露/过会/完成）、股权比例、金额 |

补充：`research` 工具可一次抓多篇来源，适合舆情；`multi_search` 可并行多引擎并合并去重。

### 第 3 步 · 写数据文件 `stock_review_data.json`

字段与口径（数字直接写数值；金额单位亿元；百分比写百分数数值，如 86.8 表示 86.8%）：

```json
{
  "demo": false,
  "code": "600519", "name": "贵州茅台", "full_name": "贵州茅台酒股份有限公司",
  "date": "YYYY-MM-DD", "exchange": "上交所主板", "industry": "白酒Ⅱ",
  "market": {"price": 0, "change_pct": 0, "free_float_cap": 0, "total_cap": 0, "pe_ttm": 0, "ytd_pct": 0},
  "conclusion": {"one_line": "", "consensus": "", "contrarian": "", "themes": ["", ""]},
  "sentiment": {"sites": [{"name": "韭研公社", "bull": ["", ""], "bear": ["", ""], "posts": [{"title": "", "url": "", "date": "", "gist": ""}]}], "summary": ["", ""]},
  "limit_up": {"date": "", "core_concepts": ["", ""], "industry_reason": "", "company_reason": "", "trade": {"volume": 0, "turnover": 0, "seal_amount": 0, "form": "换手板"}, "reopen_analysis": ""},
  "merger": {"items": [{"time": "", "target": "", "business": "", "stage": "", "stake": "", "amount": ""}]},
  "business": {"basis": "2025年报", "rows": [{"segment": "", "share": 0, "revenue": 0, "margin": 0, "desc": ""}]},
  "advantages": [{"title": "", "text": ""}],
  "financials": {
    "annual":  {"period": "2025年报", "revenue": 0, "revenue_yoy": 0, "net_profit": 0, "net_profit_yoy": 0, "gross_margin": 0, "debt_ratio": 0, "ocf": 0},
    "quarter": {"period": "2026三季报", "revenue": 0, "revenue_yoy": 0, "net_profit": 0, "net_profit_yoy": 0, "gross_margin": 0, "debt_ratio": 0, "ocf": 0},
    "commentary": {"annual": "", "quarter": "", "inflection": "", "summary": ["", ""]},
    "trend": [{"period": "2022A", "revenue": 0, "net_profit": 0, "gross_margin": 0}]
  },
  "research": {"window": "近60日", "count": 0, "ratings": {"buy": 0, "add": 0, "neutral": 0, "sell": 0}, "target_low": 0, "target_high": 0, "consensus": [""], "disputes": [""], "warnings": [""], "conclusion": ""},
  "risks": ["", ""],
  "sources": [{"title": "", "url": ""}],
  "disclaimer": "本报告由 AI 依据公开资料整理，仅用于信息研究，不构成任何投资建议。"
}
```

规则：
- 窗口内无数据 → 对应字段写 `null`（`limit_up` / `merger` / `research`），生成器自动隐藏整节，章节序号自动重排。
- `trend` 只用**年报口径**（同一口径才可比），不要把季报混进年报序列。
- `sentiment.sites` 至少 3 个平台；某平台确实抓不到就写明原因，不要留空数组冒充。
- `sources` 至少 4 条真实链接。

### 第 4 步 · 生成 HTML

在本技能目录下执行（`python` 不可用则试 `py -3`）：

```bash
python scripts/build_report.py stock_review_data.json -o "<代码>_股评_<YYYY-MM-DD>.html"
```

输出到当前工作目录。若用户要“看效果”，可加 `--open`。生成器会校验必填结构、渲染卡片/导航/表格/图表，缺章节自动隐藏。

### 第 5 步 · 输出 Markdown 全文 + 交付

先按下面模板输出完整 Markdown（章节编号与实际保留章节一致），再给出 HTML 文件路径，最后 `present` 该 HTML。若用户只想要文字，跳过 HTML 步骤并说明。

## 十段式模板（严格照此结构与措辞）

```markdown
# 【股票代码】【股票全称】完整个股深度股评｜【YYYY.MM.DD】
现价：【X.XX元】/【XX亿（自由流通市值）/XX亿（总市值）】｜TTM市盈率【XX.XX倍】｜年内涨幅【±XX.X%】

## 一、核心结论
**一句话定调**：【核心题材+核心催化+股价走势+估值状态】

**【核心预期差】**
- **市场共识**：【当前市场定价逻辑】
- **我们的不同看法**：【区别于共识的判断，1-2 句讲清“错在哪”】

**【核心赛道/热门题材】**
- 1-3 个，按重要性排序

## 二、舆情分析总结（近2周各大股吧贴文）
### 韭研公社（题材深挖）
**看多逻辑**：1、…；2、…；3、…；
**看空逻辑**：1、…；2、…；
### 雪球
### 同花顺
### 东财
### 淘股吧
### 舆情总结

## 三、涨停分析（近60日无涨停则去掉本条）
**核心概念**：【2-3 个市场概念标签，按热度排序】
### 行业原因
### 公司原因
### 交易状态：当日成交【XX.XX亿】、换手【XX.XX%】、封单【XX.XX万】、封板形态【一字板/换手板/烂板回封】
**若为烂板回封**：分析【吸筹（次日高开概率大）/出货（次日低开概率大）】+ 量能结构

## 四、并购重组（近半年无则去掉本条）
**核心并购**：【时间+标的+标的主营+当前阶段+股权比例+交易金额】

## 五、业务结构（最新年报口径）
| 业务板块 | 营收占比 | 年营收(亿) | 毛利率 | 产品&下游 |
| ---- | ---- | ---- | ---- | ---- |
| … |

## 六、核心优势
1. **【标题】**：【阐述】
2. **【标题】**：【阐述】
3. **【标题】**：【阐述】

## 七、财报点评（最新年报+最新季报）
| 报告期 | 营收(亿) | 同比 | 归母净利(亿) | 同比 | 综合毛利率 | 资产负债率 | 经营现金流 |
| ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- |
| 最新年报 | … |
| 最新季报 | … |
### 财报解读
1. **年报**：变化原因 + 亮点 + 问题
2. **季报**：环比趋势优先（毛利率连续 X 季回升/下滑）+ 亮点 + 问题
3. **财务拐点信号**：毛利率环比、现金流异动、应收/合同负债异常
4. **财务总结**：亮点 2-3 条 + 隐患 1-2 条

## 八、近2个月券商研报点评（近60日无新发研报则忽略本条）
1. **机构覆盖**：近60日【X家】覆盖，买入X/增持X/中性X，综合目标价【X.X-X.X元】
2. **一致看多逻辑**：1-2 条
3. **分歧点**：1-2 条
4. **需警惕的机构信号**：拥挤交易反指 / 目标价透支 / 承销关系利益冲突
5. **总结**：口头看好 vs 实际加仓 + 配置建议
> 无研报则写：近60日无券商新发研报覆盖；存量观点：乐观…/谨慎…

## 九、精简风险提示
1. …；2. …

## 十、数据来源与免责
- 来源清单（链接 + 日期）
- 免责声明
```

## 质量自检（交付前逐条过）

- [ ] 代码、名称、全称三者一致，已在正文体现。
- [ ] 现价/市值/PE/年内涨幅与接口返回一致（注意 ÷100、÷10000 换算）。
- [ ] 舆情写了时间范围，看多/看空各 ≥2 条（不足要说明），没有把旧帖当新帖。
- [ ] 涨停、并购、研报三个窗口都判断过；没有就删章节，没删干净则是错误。
- [ ] 财报数字单位统一（亿元），同比正负号正确（红涨绿跌）。
- [ ] 预期差不是空话，有具体数据/事件支撑。
- [ ] 风险提示与正文逻辑冲突时以正文为准，风险不能是套话。
- [ ] HTML 生成成功、`present` 已调用、文件能在浏览器打开且图表有数据。

## 常见坑

| 坑 | 处理 |
| --- | --- |
| 东财价格字段没除 100 | f43 需 ÷10^f59；f162 ÷100；f170 ÷100 |
| 深市/北交所 secid 拼错 | 深市 `0.`，沪市 `1.`，北交所 `0.`，港股 `116.` |
| F10 毛利率为 null | 用最新中报的 GROSS_RPOFIT_RATIO 或 MAINFINADATA 的 XSMLL |
| 研报接口 400 | 必须带 `pageNo`（不是 `page`）；列名用 `PARENTNETPROFIT` |
| 股吧内容抓不到 | 换 `web_search site:` 检索标题+摘要，只写能核实的观点，标注“仅摘要” |
| 用户给的是名称不是代码 | 先用搜索确认代码，再走流程 |
| 停牌/新股/退市 | 照实说明：无近期行情/无历史财报，模板中留“—”，不套用其它公司数据 |
