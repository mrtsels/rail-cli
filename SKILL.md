---
name: rail-cli
description: "Use when you need Chinese railway data (trains, stations)."
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [cli, railway, china, railgo, api, usage]
    related_skills: [api-docsite-to-cli, cli-install-update-scripts, bash-cli-patterns]
---

# rail-cli（RailGo 数据服务 CLI）

rail-cli 是我为 [RailGo 数据服务](https://api.railgo.dev) 封装的零依赖 CLI：13 个公开接口全部实测过，封装成 `rail` 子命令。纯 Python 标准库（`urllib` + `argparse` + `json`），不需要 pip 装任何依赖。

**作为 agent，查中国铁路信息（车次、车站、正晚点、检票口）时直接用 `rail`，不要自己拼 HTTP 请求** —— 真实 API 域名、V1/V2 双 base、`{success,msg,data}` 解包这些坑我已经在代码里处理好了。

## Trigger

- 用户要查：车次信息/时刻表、站到站有哪些车、车站信息或模糊搜索、正晚点、检票口/站台/出站口、车站大屏、动车组车厢图、列车运行线路
- 任何「G1 几点到上海 / 深圳到广州东有哪些车 / 这趟车晚点了吗」类问题

## 首次运行：安装

```bash
git clone https://github.com/mrtsels/rail-cli
cd rail-cli
./install.sh
```

- 默认装到 `~/.local`（程序在 `~/.local/lib/rail-cli/`，命令软链 `~/.local/bin/rail`）；装完验证 `rail version` → `rail 0.3.0`
- 脚本自动探测 Python 3.10+（PATH → `python3.14`..`python3.10` → Homebrew/miniconda 常见绝对路径；也可 `PYTHON=/path/to/python ./install.sh` 指定）
- **自动重写 shebang**：安装后的 `rail` 用探测到的 Python 绝对路径运行，之后无论 shell PATH 如何都能跑
- 变体：`./install.sh --prefix ~/tools`（自定义前缀）、`./install.sh --user`（装到 `~/bin`）、`pip install -e .`（需 pip）

### PATH 处理（agent 必看）

非交互（agent）调用 install.sh 不会改 shell 配置，只打印提示。若 `rail: command not found`，手动：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### 更新 / 卸载

```bash
rail update                      # CLI 内更新，任何目录可运行：git pull + 重装到原位置
./install.sh --update            # 等价脚本方式（需在 clone 的仓库目录内）
./install.sh --uninstall         # 卸载
```

`rail update` 自动定位仓库与安装位置（安装元数据 `.install-meta` 记录 `PREFIX`+`REPO`）；旧安装缺 REPO 元数据时，在仓库目录内运行会自愈回写。未安装过就 `--update` 会报错指引（不会静默装到默认位置造成重复安装）。

### 自动更新（AUTO_UPDATE，默认开）

**当天首次运行 `rail` 时自动更新**（git pull，已安装则重装到原位置），之后当天不再检查：

- **关闭**：`AUTO_UPDATE=0`（或 `false`/`off`/`no`/`n`/`disabled`）；**单次跳过**：`rail --no-update <命令>`
- 检查标记 `~/.cache/rail-cli/last-auto-update`（内容=当天日期，可用 `XDG_CACHE_HOME` 重定向），每天只检查一次
- 失败（如离线）只警告到 stderr，命令照常执行；可稍后 `rail update` 手动重试
- `rail version` / `rail update` 不触发自动更新；自动更新输出全走 stderr，不污染 stdout 的 JSON

### 不想安装？直接从仓库跑

```bash
./rail train query G1 --pretty   # 仓库根目录直接可用
```

⚠️ **macOS 大坑（实测复现）**：`./rail` 的 shebang 是 `#!/usr/bin/env python3`，而 macOS 默认 PATH 的 `/usr/bin/python3` 是 **3.9.6**，不支持 `dict | None` 语法，直接跑会崩：

```
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

PATH 里没有 3.10+ 时，先显式指定再跑：

```bash
PATH="/opt/homebrew/Caskroom/miniconda/base/bin:$PATH" ./rail train query G1
# 或 python3.13 ./rail ...
```

正式使用请走 install.sh（它重写 shebang 就是为了绕开这个坑）。

## 命令参考

### V1 接口（裸 JSON，无包装）

| 子命令 | 说明 |
|---|---|
| `rail train query <车次>` | 车次信息：车型、交路(diagram)、开行日(rundays)、时刻表(timetable) |
| `rail train sts <出发> <到达>` | 站到站车次（站名或电报码；默认今天，可 `--date`） |
| `rail train preselect <关键词>` | 车次号模糊搜索 |
| `rail station query <站名或电报码>` | 车站信息 |
| `rail station preselect <关键词>` | 车站名模糊搜索（中文 OK） |
| `rail lucky` | 随机车次 |

### V2 接口（默认已解包 `{success,msg,data}` → 直接输出 data）

| 子命令 | 说明 |
|---|---|
| `rail main <车次> [--date]` | 车次主数据 |
| `rail delay <车次>` | 各站正晚点（delayStatus: ON_TIME/EARLY/DELAY） |
| `rail screen <车站> [--kind departure\|arrival]` | 车站大屏（默认 departure） |
| `rail exit <车次> <车站> [--date] [--kind]` | 检票口/站台/出站口 |
| `rail coach <车次>` | 动车组车厢图 |
| `rail map [车次]` | 运行线路点（GCJ-02 坐标，车次可省） |

### 全局参数与环境变量

- `--pretty`：缩进 JSON（人类可读）；`-v/--verbose`：打印请求 URL + HTTP 状态（stderr）；`--raw`：V2 不解包原样输出；`--no-update`：本次跳过每日自动更新
- 全局 flag 子命令前后皆可：`rail -v lucky` ≡ `rail lucky -v`
- `RAILGO_BASE_URL`（V1，默认 `https://data.railgo.zenglingkun.cn`）、`RAILGO_V2_BASE_URL`（V2，默认 `https://rg-api.zenglingkun.cn`）——正常不用动
- 出错时打印 `rail: error: <msg>` 到 stderr 并 **exit 1**

## 已实测示例

```bash
rail train query G1 --pretty           # G1：CR400BF-S、上局、7 站时刻表
rail train sts 深圳 广州东 --pretty        # 站名或电报码均可
rail train sts IOQ IZQ --date 20260807 # 指定日期（YYYYMMDD 或 YYYY-MM-DD）
rail station preselect 新余             # 中文关键词直接传
rail station query 深圳北               # 站名或电报码均可
rail main G1 --pretty                  # V2 主数据（含 rundays 开行日）
rail delay G1 --pretty                 # 各站正晚点+晚点分钟(delayTime)
rail screen 深圳北 --kind departure
rail exit G1 北京南 --pretty           # 检票口/站台/出站口
rail lucky --pretty
```

### 常用电报码

深圳 `SZQ`、深圳北 `IOQ`、广州东 `GGQ`、广州 `GZQ`、广州南 `IZQ`、北京 `BJP`、北京南 `VNP`、上海虹桥 `AOH`、南京南 `NKH`、苏州北 `OHH`。
车站参数已支持站名直输，一般不用记码；`station preselect` 仍可做模糊搜索。

## Agent 使用要点（踩坑记录）

1. **先确认已安装**：`command -v rail`，没有就先 clone + install.sh + export PATH
2. **`train sts` 必须带日期**：不传默认今天；查未来日期务必显式 `--date`（API 缺 date 会静默返回空数组）
3. **空数组 `[]` 是正常响应**：区间无直达车时 sts 返回 `[]`（HTTP 200），不是错误，不要重试
4. **V2 失败即报错**：`success:false` 时 CLI 直接 `rail: error: <msg>` + exit 1（如车次不存在）
5. **`sts` 输出可能非常大**：深圳⇄广州东实测 ~370KB，别整段贴给用户，用 python 提炼：

   ```bash
   rail train sts SZQ GGQ | python3 -c "
   import json, sys
   for t in json.load(sys.stdin):
       print(t['number'], t['fromDepart'], '->', t['toArrive'], t['passTime'])"
   ```

6. **车站位置参数接受中文站名或电报码**：`sts`/`station query`/`screen`/`exit` 直接输站名（如 深圳北、广州东站）即可，内部先查内置 3382 站映射，未命中自动走 preselect 实时匹配；`station preselect` 仍用于模糊搜索
7. **别直接请求 api.railgo.dev**：那是 Apifox 文档站，WAF 把 `/api/*` 302 到帮助页；CLI 内部已走真实 API
8. **无 key、无显式限速**；V2 约 0.2-0.4s，CLI timeout 30s
9. **合规**：禁止商业用途、禁止公开接口中转；引用数据需标注来源
10. 输出为 UTF-8 中文 JSON（`ensure_ascii=False`），直接可读
11. **自动更新默认开**：当天首次运行会先 git pull（约 1s，已安装则重装）；脚本/批量场景用 `rail --no-update` 或 `AUTO_UPDATE=0` 跳过

## 验证清单（装完跑一遍确认可用）

```bash
rail version                      # rail 0.3.0
rail train query G1 --pretty      # 有 timetable 数组
rail delay G1 --pretty            # 各站 delayStatus
```

## 相关

- 仓库：https://github.com/mrtsels/rail-cli（README 完整用法；`docs/PLAN.md` 含 2026-08-07 可行性验证，13 端点实测矩阵）
- 开发流程 skill：`api-docsite-to-cli`（从 Apifox 文档站造 CLI 的全流程）
- 安装脚本 skill：`cli-install-update-scripts`（install.sh 的设计与 macOS 坑）
