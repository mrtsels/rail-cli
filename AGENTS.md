# rail-cli

RailGo 数据服务（https://api.railgo.dev）CLI 工作目录。

## 项目结构

- `rail` + `rail_cli/` — 主 CLI（Python，stdlib only，详见 `docs/PLAN.md`）
- `references/` — 从 https://api.railgo.dev 抓取的完整文档（Markdown），命名 `NN-页面名.md`，共 13 页（数据服务简介 + V1×6 + V2×6）
- 文档来源：Apifox 托管文档站，每页有 `.md` 端点（`https://api.railgo.dev/<pageid>.md`），sitemap 在 `https://api.railgo.dev/sitemap.xml`
- `docs/PLAN.md` — 实施计划（含可行性验证章节）

## 关键事实

- API 无 key、无显式限速；禁止商业用途、禁止公开中转；引用数据需标注来源
- V1/V2 调用方式和格式差异较大；V2 响应较慢（约 1s），需合理设置 timeout
- `train sts`（站到站查询）**必须带 `date` 参数**（格式 YYYYMMDD，缺省会返回空数组），CLI 已默认填今天
- 更新机制：`rail update` 手动更新；`AUTO_UPDATE` 默认开，当天首次运行自动更新（标记 `~/.cache/rail-cli/last-auto-update`，每天一次）；`--no-update` 单次跳过；`version`/`update` 不触发自动更新；安装元数据 `.install-meta` 含 `PREFIX`+`REPO`
- 常用电报码：深圳 SZQ、深圳北 IOQ、广州东 GGQ、广州 GZQ、广州南 IZQ、北京 BJP、北京南 VNP
- 反馈 QQ 群 652032716；E-mail: tkp30@tkp30.top（开发者）

## 约定

- 本目录为 rail-cli 项目根；文件操作默认相对此目录
- 新增抓取/脚本放在本目录内，避免散落 home

## Git 规则

- 本仓库为**公开仓库** `mrtsels/rail-cli`：严禁提交任何敏感信息（密钥、token、凭据、个人信息、内部路径）
- **禁止 `git add .` / `git add -A`**：只 `git add <具体路径>`，逐个确认
- **逐条 commit**：按 `docs/PLAN.md` 的 task 粒度提交，每个 task 完成后立即 commit
- commit message 用 Conventional Commits：`feat:` / `fix:` / `docs:` / `chore:` / `refactor:` + 英文简短描述
- **commit 后立即 push**（`git push origin main`），不留本地堆积
- `.gitignore` 已排除 `__pycache__/`、`.DS_Store`、`*.pyc`、虚拟环境等，新增忽略项需同步更新

## 相关技能（按需加载）

- **开发 (coding)**：`python-code-style`（人类风格 Python 代码）、`test-driven-development`（先测试后实现）、`systematic-debugging`（根因调试）、`writing-plans`（计划写作）、`de-ai-ify-code`（去 AI 味）
- **DevOps / Git**：`github`（仓库创建、提交、PR 全流程）、`repository-cleanup`（提交前清理垃圾文件）
- **CLI**：`bash-cli-patterns`（跨平台 CLI 模式：set -euo pipefail、TTY 检测、flag 解析、sed -i 兼容）
