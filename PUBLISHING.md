# 发布清单（GitHub + npm + 插件市场）

本目录已具备发布条件，只差**你的账号身份**这一步。发布到公共市场是不可逆的外部动作（npm 包公开、GitHub 仓库公开、PR 公开），所以需要你自己执行，或明确授权后我代跑。

当前环境限制：这台机器上没有 npm 登录态（`npm whoami` → `ENEEDAUTH`），也没有 `gh` CLI 和 GitHub token。`node` 能访问 registry（已验证 200），所以**一旦你登录，我可以在本机直接 `npm publish`**。

---

## 1. 建 GitHub 仓库并推送（市场收录必需）

仓库年龄需 ≥ 1 天才会被市场 CI 接收，建议今天先建好。

```bash
cd <本目录>
git init -b main
git add -A
git commit -m "feat: dsh-stock-review 0.1.0 — 个股深度股评 skill + HTML 报告生成器"
```

在 GitHub 上新建一个**公开**仓库（建议名 `dsh-stock-review`），然后：

```bash
git remote add origin https://github.com/<你的账号>/dsh-stock-review.git
git push -u origin main
```

推送后做两件事：
1. 仓库 **Settings → Topics** 添加 `dsh-plugin`（市场 CI 检查项）。
2. 把 `package.json` 的 `repository` 补上（npm 靠它把包和仓库关联）：
   ```json
   "repository": { "type": "git", "url": "https://github.com/<你的账号>/dsh-stock-review.git" }
   ```
   之后 `git commit -am "chore: add repository field" && git push`。

`dsh.bundle` 已在 `package.json` 声明、`cordis.patch.yml` 在同级，满足可安装要求。

## 2. 发布 npm 包（可选，但强烈建议）

包名 `dsh-stock-review` 在 registry 上**当前未被占用**（2026-11-26 查到 404），可直接用无 scope 名称。

```bash
npm login                    # 用你自己的账号，浏览器/OTP 认证
npm publish --access public  # 在本目录执行
```

本机 npm 缓存在沙箱里写不了，如果 `npm publish` 报 `EPERM ... npm-cache`，加 `--cache ./.npm-cache`：

```bash
npm publish --access public --cache ./.npm-cache
```

发布后**不要立刻提 PR**，先确认产物真的可用（新包名常见几种异常形态）：

```bash
npm view dsh-stock-review dist-tags.latest
npm view dsh-stock-review dist.tarball
```

- `latest` 必须是 `0.1.0`（若停在 `0.0.0-stage` 占位包，把同一版本再发一次）。
- `dist.tarball` 要能下载；刚发布几分钟内可能 404，等一会儿。
- 国内镜像 `registry.npmmirror.com` 可能滞后，必要时 `curl -X PUT https://registry.npmmirror.com/dsh-stock-review/sync` 后等待。

## 3. 提交市场 PR（awesome-dsh-plugin）

市场列表由 [awesome-dsh-plugin](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin) 维护，收录方式：**给该仓库提一个 PR，只加一个文件** `data/plugins/<owner>__<repo>.yml`。

Fork → 新建分支 → 添加文件（内容见下方）→ 提交 PR。CI 会校验文件名/URL/分类/`dsh.bundle`/仓库年龄；维护者再人工读一遍源码。

### 条目文件

文件名：`data/plugins/<owner>__dsh-stock-review.yml`（`<owner>` 换成你的 GitHub 账号，小写；仓库名是 `dsh-stock-review`）

```yaml
url: https://github.com/<owner>/dsh-stock-review
name: <owner>/dsh-stock-review
category: skill
description:
  en: A DeepSeek Harness skill that turns a six-digit A-share or HK stock code into a ten-section research review plus a single-file dark HTML report.
  zh: 输入六位 A 股/港股代码即可产出十段式个股深度股评与单文件深色 HTML 报告的 DeepSeek Harness 技能。
```

注意：
- **不要**在 yml 里写 `npm:` 字段（会被 CI 拒绝，npm 映射从 registry 自动采集）。
- 描述必须与代码一致；不要营销词。
- 一个 PR 最多 3 条，这里只有 1 条。
- 图标用仓库里的位图（本目录 `assets/icon-180.png`），条目可选写：
  ```yaml
  icon: https://raw.githubusercontent.com/<owner>/dsh-stock-review/main/assets/icon-180.png
  ```
- 截图已按规范放在本仓库（`screenshots.json` + `assets/screenshot-*.png`），无需再往列表仓提。

## 4. 发布前自检（建议在干净 profile 跑一遍）

```bash
dsh plugin --profile demo-review add dsh-stock-review
```

装完在会话里发 `股评 600519`，确认能产出报告。市场评审也会这样验证。

本机已在本 profile 安装（`link:` 到本目录）；发布后再从 npm 装一次可以同时验证 registry 产物。

## 5. 最快路径（装了 `gh` CLI 的话）

```bash
# 1) 建公开仓库并推送
cd <本目录>
gh repo create dsh-stock-review --public --source=. --remote=origin --push
gh repo edit --add-topic dsh-plugin

# 2) npm 发布
npm login
npm publish --access public --cache ./.npm-cache

# 3) Fork 列表仓、加条目、提 PR
gh repo fork awesome-dsh-plugin/awesome-dsh-plugin --clone
cd awesome-dsh-plugin
git checkout -b add-dsh-stock-review
mkdir -p data/plugins
cp ../release/awesome-dsh-plugin-entry.yml data/plugins/<owner>__dsh-stock-review.yml
# 把文件里的 OWNER 全部替换成你的账号
sed -i "s/OWNER/<owner>/g" data/plugins/<owner>__dsh-stock-review.yml
git add data/plugins && git commit -m "Add <owner>/dsh-stock-review"
git push -u origin add-dsh-stock-review
gh pr create --title "Add <owner>/dsh-stock-review" --body "Individual stock review skill: verified quote/舆情/financials/broker data → ten-section review + single-file dark HTML report."
```

---

## 我这边还能代做的

- 你执行 `npm login` 之后：我直接跑 `npm publish` 并校验 registry 产物。
- 你建好仓库并给出 `owner/repo`：我把 `repository` 字段、条目 YAML 里的占位符全部替换好，并 `git commit`。
- 你 push 完、PR 需要改描述：按评审意见改 yml 重提。
