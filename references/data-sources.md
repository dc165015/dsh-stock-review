# 数据源与解析要点（已实测，2026-11）

所有请求都用 `web_fetch` 工具。返回是 JSON 文本，注意 `\"` 与 `\_` 转义。接口无需登录、无需 key。

## 1. 行情 / 市值 / PE（东方财富推送接口）

```
GET https://push2.eastmoney.com/api/qt/stock/get?secid=<secid>&fields=f43,f57,f58,f59,f116,f117,f162,f169,f170
```

| 字段 | 含义 | 换算 |
| --- | --- | --- |
| f43 | 最新价 | ÷10^f59（A 股通常 2 位） |
| f57 | 代码 | 原文 |
| f58 | 名称 | 原文 |
| f59 | 小数位 | — |
| f116 | 总市值 | 元，÷1e8 = 亿元 |
| f117 | 自由流通市值 | 元，÷1e8 = 亿元 |
| f162 | TTM 市盈率 | ÷100 |
| f169 | 涨跌额 | ÷10^f59 |
| f170 | 涨跌幅 | ÷100 |

`secid` 规则：沪市 `1.600519`、深市 `0.000001`、北交所 `0.430047`、港股 `116.00700`、美股 `105.AAPL`。

**注意**：同一接口如果带 `f116/f117` 在港股/美股可能为空，需改用 `f118` 或直接不写市值。

## 2. 公司资料（全称 / 行业 / 简介）

```
GET https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code=SH600519
```

- `jbzl[0].ORG_NAME` → 公司全称
- `jbzl[0].EM2016` → 东财行业（如“食品饮料-饮料-白酒”）
- `jbzl[0].ORG_PROFILE` → 公司简介（写“核心优势”时可用）
- 深市把 `SH` 换成 `SZ`，北交所 `BJ`。

## 3. 主营构成（业务结构）

```
GET https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax?code=SH600519
```

`zygcfx` 数组，按 `REPORT_DATE` 分组、`MAINOP_TYPE` 区分维度：

- `MAINOP_TYPE=="2"`：按产品/业务拆分（用这个做业务结构表）
- `MAINOP_TYPE=="3"`：按地区拆分
- `MAINOP_TYPE=="1"`：按行业大类

字段：`ITEM_NAME`（板块）、`MAIN_BUSINESS_INCOME`（营业收入，元）、`MBI_RATIO`（占比，0-1）、`GROSS_RPOFIT_RATIO`（毛利率，0-1，部分报告期为空）。

**规则**：优先取 `REPORT_DATE` 以 `12-31` 结尾的最新一期；毛利率为空时用最近中报（`06-30`）的同一板块补齐，并在正文注明“毛利率按中报口径”。

## 4. 主要财务指标（年报 / 季报 / 趋势）

```
GET https://datacenter-web.eastmoney.com/api/data/v1/get
    ?reportName=RPT_F10_FINANCE_MAINFINADATA
    &columns=SECUCODE,REPORT_DATE,REPORT_DATE_NAME,TOTALOPERATEREVE,TOTALOPERATEREVETZ,PARENTNETPROFIT,PARENTNETPROFITTZ,XSMLL,ZCFZL,NETCASH_OPERATE_PK
    &filter=(SECUCODE%3D%22600519.SH%22)
    &pageNumber=1&pageSize=13&sortColumns=REPORT_DATE&sortTypes=-1
```

| 列 | 含义 | 单位 |
| --- | --- | --- |
| TOTALOPERATEREVE | 营业总收入 | 元 |
| TOTALOPERATEREVETZ | 营收同比 | % |
| PARENTNETPROFIT | 归母净利润 | 元 |
| PARENTNETPROFITTZ | 归母净利同比 | % |
| XSMLL | 销售毛利率 | % |
| ZCFZL | 资产负债率 | % |
| NETCASH_OPERATE_PK | 经营活动现金流净额 | 元 |
| REPORT_DATE_NAME | “2026三季报”这类标签 | — |

**列名陷阱**：`PARENT_NETPROFIT` 会 400，必须 `PARENTNETPROFIT`；`TOTAL_OPERATE_INCOME` 也不对，必须 `TOTALOPERATEREVE`。报错时先用 `columns=ALL` + 单期 filter 看真实列名。

## 5. 券商研报

```
GET https://reportapi.eastmoney.com/report/list
    ?industryCode=*&pageSize=50&industry=*&rating=&ratingChange=
    &beginTime=2026-09-27&endTime=2026-11-26
    &pageNo=1&fields=&qType=0&orgCode=&code=600519&rcode=&p=1&pageNum=1
```

- `hits`：区间内研报篇数（≈覆盖机构数，同一机构多篇会重复，统计“家数”要去重 `orgSName`）
- `emRatingName`：买入 / 增持 / 中性 / 减持
- `indvAimPriceL`、`indvAimPriceT`：目标价下限/上限（很多研报为空）
- `title`：提炼共识与分歧的主要素材
- `publishDate`：近 60 日过滤
- 必须带 `pageNo`，只带 `page` 会 400。

近 60 日无数据（`hits==0`）→ `research` 写 `null`，正文写“近 60 日无券商新发研报覆盖”。

## 6. 舆情（无稳定 API，靠搜索 + 抓取）

搜索引擎对股吧收录参差，建议组合：

1. `web_search`：`site:jiuyangongshe.com 600519`、`site:xueqiu.com 贵州茅台`、`site:guba.eastmoney.com 600519`、`site:10jqka.com.cn 贵州茅台`、`site:taoguba.com.cn 贵州茅台`
2. `multi_search`：多引擎并行，提高命中率
3. `research`：一次抓 3-5 篇原文，适合提炼多空逻辑
4. 对命中链接 `web_fetch` 精读，只记录**能核实**的观点与日期

已知限制（如实写进报告，不要编）：
- 韭研公社需登录才能看全文，通常只能拿标题/摘要
- 雪球部分页面有反爬，抓不到就换东财股吧/同花顺
- 淘股吧内容质量参差，只取有数据支撑的观点

## 7. 涨停 / 异动 / 龙虎榜

优先用搜索定位最近一次涨停日，再交叉验证：

- `web_search`：`"贵州茅台" 涨停 2026年11月`、`600519 龙虎榜`
- 同花顺异动：`data.10jqka.com.cn`
- 东财涨停板池：`https://push2ex.eastmoney.com/getTopicZTPool?ut=...&dpt=wz.ztzt&Pageindex=0&pagesize=10&sort=fbt%3Aasc&date=YYYYMMDD`（需 `ut` 参数，易失效，失败就换搜索）
- 韭研公社涨停复盘：`jiuyangongshe.com` 搜索当日复盘

近 60 日无涨停 → `limit_up` 写 `null`。

## 8. 并购重组

- `web_search`：`"<名称>" 收购 公告 2026`、`"<名称>" 重大资产重组`
- 东财公告：`https://data.eastmoney.com/notices/stock/<code>.html`
- 交易所公告（沪市 `sse.com.cn`，深市 `szse.cn`）为准

近半年无 → `merger` 写 `null`。

## 9. 产出校验清单

- 现价 / 市值 / PE 与接口结果逐项核对（尤其 ÷100）
- 业务结构各板块营收之和 ≈ 年报总营收（差异 >5% 要解释）
- 年报同比符号：`TOTALOPERATEREVETZ` 为负时正文写“同比转负”
- 研报 `hits` 与“覆盖家数”区分：篇数 ≥ 家数
- 报告日期写实际抓取日，不写未来日期
