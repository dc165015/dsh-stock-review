import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * dsh-stock-review
 *
 * Registers the `stock-review` runtime skill. The body lives in SKILL.md so the
 * same folder can also be dropped into a skills root unchanged. `scripts/` and
 * `references/` are exposed as the skill's resource base.
 */

const NAME = 'stock-review'

const DESCRIPTION =
  '个股深度股评。用户给出 A 股/港股六位代码或股票名称，或要求“股评/个股深度分析/舆情+涨停+财报点评”时使用。' +
  '产出十段式深度股评（Markdown 全文）+ 自包含深色财经主题 HTML 报告（卡片折叠、sticky 导航、ECharts 图表）。' +
  '数据必须来自真实公开来源并核实代码-名称对应。'

const WHEN_TO_USE =
  '用户发来股票代码（如 600519、000001、300750）或说“股评 600519”“分析一下某某股票”时。'

const here = dirname(fileURLToPath(import.meta.url))

function stripFrontmatter(raw) {
  if (!raw.startsWith('---')) return raw
  const end = raw.indexOf('\n---', 3)
  if (end === -1) return raw
  const after = raw.indexOf('\n', end + 4)
  return after === -1 ? '' : raw.slice(after + 1)
}

export const name = 'stock-review'
export const inject = ['skills']

export function apply(ctx) {
  const path = join(here, 'SKILL.md')
  const content = stripFrontmatter(readFileSync(path, 'utf8')).trim()
  if (content.length === 0) {
    ctx.logger.warn('[dsh-stock-review] SKILL.md is empty; skill not registered')
    return
  }

  ctx.skills.register({
    name: NAME,
    description: DESCRIPTION,
    whenToUse: WHEN_TO_USE,
    content,
    source: 'bundle:dsh-stock-review',
    path,
    resourceBase: { kind: 'directory', path: here },
    invocation: { modelInvocable: true, userInvocable: true },
  })

  ctx.logger.info('[dsh-stock-review] registered skill "stock-review"')
}
