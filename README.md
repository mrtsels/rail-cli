# RailGo CLI (`rail`)

零依赖的 [RailGo 数据服务](https://api.railgo.dev) 命令行工具，封装全部 13 个公开 API，用于查询中国铁路车次、车站、正晚点、检票口等信息。

纯 Python 标准库实现（`urllib` + `argparse` + `json`），无需任何 pip 安装。

## 功能

**V1 接口**（基础查询）：

| 子命令 | 接口 | 说明 |
|---|---|---|
| `rail train query <车次>` | `/api/train/query` | 按车次号查询列车信息 |
| `rail train sts <出发> <到达>` | `/api/train/sts_query` | 站到站车次查询（电报码） |
| `rail train preselect <关键词>` | `/api/train/preselect` | 车次号预选词（模糊搜索） |
| `rail station query <电报码>` | `/api/station/query` | 按电报码查询车站 |
| `rail station preselect <关键词>` | `/api/station/preselect` | 车站名预选词（模糊搜索） |
| `rail lucky` | `/api/lucky` | 随机车次（原为纪念车票设计） |

**V2 接口**（增强查询，响应带 `{success, msg, data}` 包装）：

| 子命令 | 接口 | 说明 |
|---|---|---|
| `rail main <车次> [--date]` | `/api/v2/getTrainMain` | 车次主数据（时刻表、车型、开行日） |
| `rail delay <车次>` | `/api/v2/getTrainDelayAll` | 车次各站正晚点 |
| `rail screen <车站> [--kind]` | `/api/v2/getStationBigScreen` | 车站大屏（候车/开检/晚点状态） |
| `rail exit <车次> <车站>` | `/api/v2/getExit` | 检票口、站台、出站口 |
| `rail coach <车次>` | `/api/v2/getCoachPic` | 动车组车厢图 |
| `rail map <车次>` | `/api/v2/mapLine` | 列车运行线路点（GCJ-02 坐标） |

## 安装

```bash
# 一键安装（推荐）：复制到 ~/.local 并建立 rail 命令软链
./install.sh

# 自定义前缀 / 安装到 ~/bin / 卸载
./install.sh --prefix ~/tools
./install.sh --user
./install.sh --uninstall
```

脚本自动检测 Python 3.10+（支持 `PYTHON` 环境变量指定解释器），并把入口脚本的 shebang 固定为检测到的 Python 绝对路径——即使 shell 的 PATH 里只有系统自带 Python 3.9 也能正常运行。

```bash
# 备选：editable 安装（需要 pip）
pip install -e .
```

要求 Python 3.10+（入口使用 `#!/usr/bin/env python3`）。

## 使用示例

```bash
# 车次查询
rail train query G1 --pretty

# 站到站查询（深圳 → 广州东，使用电报码；可加 --date）
rail train sts SZQ GGQ --pretty

# 车站模糊搜索
rail station preselect 新余

# 车次主数据（指定日期）
rail main G1 --date 20260807 --pretty

# 正晚点
rail delay G1 --pretty

# 车站大屏（出发/到达）
rail screen BJP --pretty
rail screen BJP --kind arrival

# 检票口/站台/出站口
rail exit G1 VNP --pretty

# 随机车次
rail lucky --pretty

# 查看帮助
rail --help
rail train --help
```

## 全局参数

| 参数 | 说明 |
|---|---|
| `-v, --verbose` | 显示请求 URL 和 HTTP 状态（stderr） |
| `--pretty` | 人类可读的 JSON 输出（2 空格缩进） |
| `--raw` | 原样输出 API 响应 |

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `RAILGO_BASE_URL` | `https://data.railgo.zenglingkun.cn` | 覆盖 V1 接口 base URL |
| `RAILGO_V2_BASE_URL` | `https://rg-api.zenglingkun.cn` | 覆盖 V2 接口 base URL |

## 数据说明

- 数据来源：[RailGo 数据服务](https://api.railgo.dev)（官方文档站），实际 API 域名 `data.railgo.zenglingkun.cn`（V1）/ `rg-api.zenglingkun.cn`（V2）
- API 无需 key、无显式限速
- **禁止商业用途、禁止公开接口中转**；公开使用数据请标注来源
- V2 响应约 0.2-0.4s，客户端 timeout 30s

## 开发

- 实施计划：`docs/PLAN.md`（含 2026-08-07 可行性验证）
- API 文档：`references/`（13 页官方文档 Markdown）
