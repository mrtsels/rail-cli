# RailGo CLI (`rail`) — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a zero-dependency Python CLI tool that wraps all 13 RailGo APIs with natural subcommands, then expose it as a Hermes skill for agent-driven queries.

---

## 0. 可行性验证（2026-08-07 实测，3 subagent 探测 + 主控交叉验证）

### ⚠️ 首要发现：api.railgo.dev 是文档站，不是 API

**`https://api.railgo.dev` 现在是 Apifox 文档站**（`x-doc-selfhost: true`）。其上所有 `/api/*` 请求被 WAF（腾讯 EdgeOne / openresty）302 重定向到 `/help/index.html`，返回文档 HTML 而非 JSON。**CLI 若直连 api.railgo.dev 将完全失败。**

**真实 API 域名通过两层来源确认：**
1. 文档站 HTML/JS 内嵌配置（`data.railgo.zenglingkun.cn` 出现在 server 配置 token 中）
2. 官方客户端源码 [RailGo-WinUI/DefaultApiUrls.cs](https://github.com/RailGoApps/RailGo-WinUI/blob/main/RailGo.Core/Query/Online/DefaultApiUrls.cs) 的 URL 映射表

### 真实 API 端点矩阵（全部实测 HTTP 200/400 正常返回 JSON）

| 版本 | Base URL | 端点 |
|---|---|---|
| **V1** | `https://data.railgo.zenglingkun.cn` | `/api/train/query` `/api/train/sts_query` `/api/train/preselect` `/api/station/preselect` `/api/station/query` `/api/lucky` |
| **V2** | `https://rg-api.zenglingkun.cn` | `/api/v2/getExit` `/api/v2/getTrainDelayAll` `/api/v2/getStationBigScreen` `/api/v2/getTrainMain` `/api/v2/getCoachPic` `/api/v2/mapLine` |

### 响应结构（实测）

- **V1：裸 JSON 无包装**。`train/query` 返回 dict（bureauName/car/carOwner/diagram/numberFull/numberKind/rundays/runner/timetable/type）；`station/preselect` 返回 list；`lucky` 返回 `{departTime, fromStation{name,pinyin}, number, toStation{name,pinyin}}`；`station/query` 返回 `{data: {车站信息...}, trains: [车次...]}`（特殊双键结构）
- **V2：统一 `{success, msg, data}` 包装**，data 为 null 时 success=false
- 错误形态：V2 缺参数 → HTTP 400 `{"data":null,"msg":"Missing required param 'xxx'.","success":false}`；V1 缺参数 → HTTP 400 `{"error":"缺少xxx参数"}`
- `sts_query` 实测 BJP→VNP 返回 `[]`（空数组，HTTP 200）——该区间无直达车时为正常空响应，非错误

### 参数名差异（文档 vs 实测）

- `getCoachPic` / `mapLine` 的参数名是 **`train`**（不是 trainNum）——与文档一致，但与其他 V2 端点不同
- `getExit` 需要 `trainNum` + `stationTelecode`（缺一即 400）
- 日期参数：`getTrainMain` 接受 `YYYY-MM-DD` 或 `YYYYMMDD`（文档），未填默认当天
- 客户端源码显示官方 app 的 delay 端点是 `getTrainDelay`（无 All 后缀），但文档和实测均确认 `getTrainDelayAll` 有效

### 环境验证

- **Python 3.13.12**（`python3` 默认命中 miniconda，`/opt/homebrew/Caskroom/miniconda/base/bin/python3`）✅ 满足 `dict | None` 等 3.10+ 语法
- ⚠️ **坑**：`/usr/bin/python3` 是系统自带 **3.9.6**（不支持 `dict | None`）；`python3.10` 不存在（有 3.11/3.12/3.13/3.14）。**入口脚本必须用 `#!/usr/bin/env python3`**，不要硬编码 `python3.10` 或 `/usr/bin/python3`
- **urllib 实测可直连**（无需代理配置）：`urllib.request.urlopen('https://data.railgo.zenglingkun.cn/api/lucky')` 正常返回 JSON
- **gzip**：服务器仅在客户端发送 `Accept-Encoding: gzip` 时才压缩（响应头 `vary: Accept-Encoding`）；urllib 默认不发送该头 → 收到的都是未压缩响应，**零额外处理安全**
- V1 延迟 ~0.2-0.35s；V2 延迟 ~0.2-0.35s（比文档声称的 1s 快，但保持 30s timeout 余量）
- DNS 解析为 198.18.0.x（Clash TUN fake-ip 段，系统代理 127.0.0.1:1082），curl/urllib 均正常，无需特殊处理；代理环境变量为空
- 中文参数（新余）URL 编码正常（`--data-urlencode` / urllib 自动编码）；响应 JSON 为 `\uXXXX` 转义，`json.loads` 后还原正确中文
- 无显式限速头（`ratelimit`/`x-ratelimit-*` 均未出现）

### 对 PLAN 的决策影响

1. **Base URL 改为 `https://data.railgo.zenglingkun.cn`（V1）和 `https://rg-api.zenglingkun.cn`（V2）**——client 需支持双 base（V1/V2 各一），`RAILGO_BASE_URL` 环境变量继续提供覆盖能力
2. **Python 版本要求 3.10+**（实际 3.13 可用），`dict | None` 语法保留
3. **V1/V2 响应处理不同**：V2 需检查 `success` 字段并在 false 时输出 `msg` 报错；V1 直接输出裸 JSON
4. `coach`/`map` 子命令参数名用 `train`，其余 V2 用 `trainNum`
5. 文档站 `api.railgo.dev` 仅作文档参考，不请求

---

**Design decisions:**
- **Python 3.10+ (stdlib only)** — `urllib.request` for HTTP, `argparse` for CLI, `json` for output. Zero pip installs.
- **Single entry, multi-module** — `rail` (shebang script) → `rail_cli/` package with `cli.py` (argparse) + `client.py` (HTTP layer)
- **Subcommands mirror API categories**: `rail train query G1`, `rail station preselect 新余`, etc.
- **Output**: JSON by default; `--pretty` for human-readable; `--raw` for unformatted API response

### API ↔ Subcommand Map

| # | API Endpoint | Subcommand | Params |
|---|---|---|---|
| 1 | GET /api/train/query | `rail train query <TRAIN>` | train (req) |
| 2 | GET /api/train/sts_query | `rail train sts <FROM> <TO>` | from, to (req) |
| 3 | GET /api/station/preselect | `rail station preselect <KEYWORD>` | keyword (req) |
| 4 | GET /api/station/query | `rail station query <TELECODE>` | telecode (req) |
| 5 | GET /api/train/preselect | `rail train preselect <KEYWORD>` | keyword (req) |
| 6 | GET /api/lucky | `rail lucky` | none |
| 7 | GET /api/v2/getExit | `rail exit <TRAIN> <STATION>` | trainNum, stationTelecode (req); --date, --kind (opt) |
| 8 | GET /api/v2/getTrainDelayAll | `rail delay <TRAIN>` | trainNum (req) |
| 9 | GET /api/v2/getStationBigScreen | `rail screen <STATION>` | stationTelecode (req); --kind departure|arrival (opt) |
| 10 | GET /api/v2/getTrainMain | `rail main <TRAIN>` | trainNum (req); --date (opt) |
| 11 | GET /api/v2/getCoachPic | `rail coach <TRAIN>` | train (req) |
| 12 | GET /api/v2/mapLine | `rail map <TRAIN>` | train (opt) |
| — | — | `rail version` | version info |
| — | — | `rail -v, --verbose` | global flag: print request URL + HTTP status |

---

## Filestructure (final state)

```
rail-cli/
├── rail                   # Executable entry point (chmod +x)
├── rail_cli/
│   ├── __init__.py        # version = "0.1.0"
│   ├── __main__.py        # python -m rail_cli entry
│   ├── cli.py             # argparse: all subcommands + main()
│   └── client.py          # RailGoClient: HTTP GET, JSON parse, error handling
├── references/            # API docs (existing, read-only)
├── tests/                 # pytest tests (write after implementation)
│   ├── __init__.py
│   ├── test_client.py
│   └── test_cli.py
├── AGENTS.md              # Project context (existing)
└── README.md              # Usage + examples
```

---

## Phase 1: Infrastructure

### Task 1.1: Create package skeleton

**Objective:** Set up directory structure, `__init__.py`, `__main__.py`, shebang entry point, and verify import chain.

**Files:**
- Create: `rail_cli/__init__.py`
- Create: `rail_cli/__main__.py`
- Create: `rail` (chmod +x)

**Steps:**

**Step 1:** Create `rail_cli/__init__.py`
```python
"""RailGo data service CLI — wrapper for https://api.railgo.dev."""
__version__ = "0.1.0"
```

**Step 2:** Create `rail_cli/__main__.py`
```python
"""Allow `python -m rail_cli`."""
from rail_cli.cli import main
main()
```

**Step 3:** Create executable `rail` script
```bash
#!/usr/bin/env python3
"""RailGo CLI entry point."""
from rail_cli.cli import main
main()
```

**Step 4:** Make executable and test
```bash
chmod +x rail
python3 -c "from rail_cli import __version__; print(__version__)"
python3 -m rail_cli --help
./rail --help
```

Expected: `0.1.0` printed; `--help` errors about missing cli module (expected, next task).

**Step 5:** Commit
```bash
git add rail rail_cli/
git commit -m "feat: scaffold rail_cli package + entry point"
```

---

### Task 1.2: HTTP client module

**Objective:** `RailGoClient` class — base URL, GET with query params, JSON parse, error handling, timeout.

**Files:**
- Create: `rail_cli/client.py`

**Steps:**

**Step 1:** Write `rail_cli/client.py`
```python
"""HTTP client for RailGo API."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class RailGoClient:
    """Lightweight HTTP client for https://api.railgo.dev."""

    BASE_URL = os.environ.get("RAILGO_BASE_URL", "https://api.railgo.dev")
    TIMEOUT = 30  # seconds; V2 endpoints ~1s, generous buffer

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def get(self, path: str, params: dict | None = None) -> dict:
        """GET `path` with optional query params. Returns parsed JSON."""
        url = self.BASE_URL + path
        if params:
            cleaned = {k: v for k, v in params.items() if v is not None}
            if cleaned:
                url += "?" + urllib.parse.urlencode(cleaned)

        if self.verbose:
            print(f"→ GET {url}", file=__import__("sys").stderr)

        try:
            with urllib.request.urlopen(url, timeout=self.TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
                if self.verbose:
                    print(f"← HTTP {resp.status}", file=__import__("sys").stderr)
                return json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            msg = f"HTTP {e.code}: {body[:200]}"
            raise RuntimeError(msg) from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}") from None
        except json.JSONDecodeError:
            raise RuntimeError("Invalid JSON response") from None
```

**Step 2:** Smoke test with a real API call
```bash
python3 -c "
from rail_cli.client import RailGoClient
c = RailGoClient()
r = c.get('/api/lucky')
print(r.get('success', r)[:200])
"
```

Expected: prints random train JSON or success=True.

**Step 3:** Commit
```bash
git add rail_cli/client.py
git commit -m "feat: add RailGoClient HTTP module"
```

---

## Phase 2: CLI Subcommands (one commit group)

### Task 2.1: Skeleton CLI + version command

**Objective:** `rail_cli/cli.py` with root parser, `--verbose`, subcommand dispatch, `version` command.

**Files:**
- Create: `rail_cli/cli.py`

**Step 1:** Write `rail_cli/cli.py`
```python
"""CLI entry point — argparse subcommands for all RailGo APIs."""
import argparse
import json
import sys

from rail_cli.client import RailGoClient
from rail_cli import __version__


def setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rail",
        description="RailGo data service CLI — query Chinese railway information.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="print request URL + status")
    parser.add_argument("--pretty", action="store_true", help="human-readable JSON output")
    parser.add_argument("--raw", action="store_true", help="print raw API response (unwrap nothing)")
    sub = parser.add_subparsers(dest="command", required=False)

    # version
    sub.add_parser("version", help="show version")

    return parser


def output(data, args):
    """Print data to stdout. With --pretty, pretty-print JSON."""
    if isinstance(data, str):
        print(data)
    elif args.pretty:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        json.dump(data, sys.stdout, ensure_ascii=False)
        print()


def main():
    parser = setup_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "version":
        print(f"rail {__version__}")
        return

    # Client + dispatch will be added in subsequent tasks
    client = RailGoClient(verbose=args.verbose)

    # TODO: dispatch table — populated as we add commands
    print("Command not implemented", file=sys.stderr)
    sys.exit(1)
```

**Step 2:** Test version
```bash
./rail version
./rail --help
```

Expected: `rail 0.1.0` and help text with --verbose, --pretty, --raw, version.

**Step 3:** Commit
```bash
git add rail_cli/cli.py
git commit -m "feat: CLI skeleton with version + global flags"
```

---

### Task 2.2: V1 subcommands (train, station, lucky)

**Objective:** Add V1 API subcommands: `train query`, `train sts`, `train preselect`, `station query`, `station preselect`, `lucky`.

**Files:**
- Modify: `rail_cli/cli.py`

**Step 1:** Add subparsers in `setup_parser()`:
```python
# --- train ---
train_p = sub.add_parser("train", help="train-related queries (V1)")
train_sub = train_p.add_subparsers(dest="train_cmd")

train_q = train_sub.add_parser("query", help="query train by number")
train_q.add_argument("train", help="train number, e.g. G1")

train_s = train_sub.add_parser("sts", help="station-to-station train query")
train_s.add_argument("from_", metavar="FROM", help="departure station telecode, e.g. BJP")
train_s.add_argument("to", help="arrival station telecode, e.g. VNP")

train_pres = train_sub.add_parser("preselect", help="train number autocomplete")
train_pres.add_argument("keyword", help="search keyword, e.g. G1")

# --- station ---
sta_p = sub.add_parser("station", help="station-related queries (V1)")
sta_sub = sta_p.add_subparsers(dest="station_cmd")

sta_q = sta_sub.add_parser("query", help="query station by telecode")
sta_q.add_argument("telecode", help="station telecode, e.g. XBG")

sta_pres = sta_sub.add_parser("preselect", help="station name autocomplete")
sta_pres.add_argument("keyword", help="search keyword, e.g. 新余")

# --- lucky ---
sub.add_parser("lucky", help="random train (memorial ticket)")
```

**Step 2:** Add dispatch table in `main()`:
```python
dispatch = {
    "train": {
        "query":    lambda: _get(client, "/api/train/query", {"train": args.train}),
        "sts":      lambda: _get(client, "/api/train/sts_query", {"from": args.from_, "to": args.to}),
        "preselect": lambda: _get(client, "/api/train/preselect", {"keyword": args.keyword}),
    },
    "station": {
        "query":     lambda: _get(client, "/api/station/query", {"telecode": args.telecode}),
        "preselect": lambda: _get(client, "/api/station/preselect", {"keyword": args.keyword}),
    },
    "lucky": lambda: _get(client, "/api/lucky"),
}
```

**Step 3:** Add `_get` helper + dispatch logic (replace the TODO block):
```python
def _get(client, path, params=None):
    return client.get(path, params)

cmd = args.command
sub = getattr(args, cmd + "_cmd", None)

if cmd in dispatch:
    handler = dispatch[cmd]
    if sub and isinstance(handler, dict):
        handler = handler.get(sub)
    if handler:
        data = handler()
        output(data, args)
        return

parser.print_help()
print(f"\nUnknown command: rail {cmd}" + (f" {sub}" if sub else ""), file=sys.stderr)
sys.exit(1)
```

**Step 4:** Test each V1 subcommand
```bash
./rail train query G1 --pretty | head -20
./rail station preselect 新余 --pretty | head -10
./rail lucky --pretty
./rail train sts BJP VNP --pretty | head -10
./rail station query XBG --pretty | head -10
./rail train preselect G1 --pretty | head -10
```

Expected: All return valid JSON, no errors.

**Step 5:** Commit
```bash
git add rail_cli/cli.py
git commit -m "feat: add V1 subcommands (train, station, lucky)"
```

---

### Task 2.3: V2 subcommands

**Objective:** Add V2 API subcommands: `exit`, `delay`, `screen`, `main`, `coach`, `map`.

**Files:**
- Modify: `rail_cli/cli.py`

**Step 1:** Add subparsers in `setup_parser()`:
```python
# --- exit (V2) ---
ex_p = sub.add_parser("exit", help="gate/platform/exit info (V2)")
ex_p.add_argument("train", help="train number, e.g. G1")
ex_p.add_argument("station", help="station telecode, e.g. VNP")
ex_p.add_argument("--date", default=None, help="date (default: today)")
ex_p.add_argument("--kind", default=None, choices=["arrival", "departure"],
                  help="arrival or departure (default: departure)")

# --- delay (V2) ---
del_p = sub.add_parser("delay", help="train delay status (V2)")
del_p.add_argument("train", help="train number, e.g. G1")

# --- screen (V2) ---
sc_p = sub.add_parser("screen", help="station big screen (V2)")
sc_p.add_argument("station", help="station telecode, e.g. BJP")
sc_p.add_argument("--kind", default=None, choices=["departure", "arrival"],
                  help="departure or arrival (default: departure)")

# --- main (V2) ---
mn_p = sub.add_parser("main", help="train master data (V2)")
mn_p.add_argument("train", help="train number, e.g. G1")
mn_p.add_argument("--date", default=None, help="date YYYY-MM-DD or YYYYMMDD (default: today)")

# --- coach (V2) ---
co_p = sub.add_parser("coach", help="coach/car image info (V2)")
co_p.add_argument("train", help="train number, e.g. G1")

# --- map (V2) ---
mp_p = sub.add_parser("map", help="train route line points (V2)")
mp_p.add_argument("train", nargs="?", default=None, help="train number (optional)")
```

**Step 2:** Add to dispatch table:
```python
dispatch.update({
    "exit":   lambda: _get(client, "/api/v2/getExit",           {"trainNum": args.train, "stationTelecode": args.station, "date": args.date, "kind": args.kind}),
    "delay":  lambda: _get(client, "/api/v2/getTrainDelayAll",   {"trainNum": args.train}),
    "screen": lambda: _get(client, "/api/v2/getStationBigScreen", {"stationTelecode": args.station, "kind": args.kind}),
    "main":   lambda: _get(client, "/api/v2/getTrainMain",      {"trainNum": args.train, "date": args.date}),
    "coach":  lambda: _get(client, "/api/v2/getCoachPic",       {"train": args.train}),
    "map":    lambda: _get(client, "/api/v2/mapLine",           {"train": args.train}),
})
```

**Step 3:** Test each V2 subcommand
```bash
./rail main G1 --pretty | head -30
./rail delay G1 --pretty | head -20
./rail screen BJP --pretty | head -20
./rail exit G1 VNP --pretty | head -20
./rail coach G1 --pretty | head -20
./rail map G1 --pretty | head -20
```

Expected: All return valid JSON. Some may fail with "Train data doesn't exist" for non-running trains — acceptable (API behavior, not our bug).

**Step 4:** Commit
```bash
git add rail_cli/cli.py
git commit -m "feat: add V2 subcommands (exit, delay, screen, main, coach, map)"
```

---

## Phase 3: Polish

### Task 3.1: README + usage documentation

**Objective:** Write `README.md` with installation, complete subcommand reference, and examples.

**Files:**
- Create: `README.md`

**Content template:**
```markdown
# RailGo CLI (`rail`)

Zero-dependency CLI for [RailGo data service](https://api.railgo.dev).

## Install

```bash
# From rail-cli directory
pip install -e .          # optional: editable install
# or just:
export PATH="$PWD:$PATH"
```

## Usage

```bash
rail train query G1          # V1: query train by number
rail train sts BJP VNP       # V1: station-to-station
rail train preselect G1      # V1: train number autocomplete
rail station query XBG       # V1: station by telecode
rail station preselect 新余   # V1: station name autocomplete
rail lucky                   # V1: random train

rail main G1                 # V2: train master data
rail main G1 --date 20260701 # V2: with date
rail delay G1                # V2: delay status
rail screen BJP              # V2: station big screen
rail screen BJP --kind arrival
rail exit G1 VNP             # V2: gate/platform/exit
rail coach G1                # V2: coach images
rail map G1                  # V2: route line points (GCJ-02)

rail --pretty train query G1 # human-readable JSON
rail --verbose delay G1      # show request URL + status
```

## Global Flags

| Flag | Effect |
|------|--------|
| `-v, --verbose` | Print request URL + HTTP status to stderr |
| `--pretty` | Pretty-print JSON (indented, 2-space) |
| `--raw` | Print raw API response (no unwrapping) |

## Environment

- `RAILGO_BASE_URL` — override base URL (default: `https://api.railgo.dev`)
```

**Step 1:** Commit
```bash
git add README.md
git commit -m "docs: add README with usage reference"
```

---

### Task 3.2: Skill for Hermes

**Objective:** Create `rail-cli` Hermes skill so agents can call `rail <subcommand>` from any session.

**Steps:**

Use `skill_manage(action="create", name="rail-cli")` with content:

```markdown
---
name: rail-cli
description: "Use when querying Chinese railway info: train schedules, station info, delays, seat gates, coach maps. Uses RailGo CLI."
---

# RailGo CLI Skill

## Overview

The `rail` CLI wraps all 13 RailGo APIs at https://api.railgo.dev.

**Location:** `~/rail-cli/rail` (Python, stdlib only, no pip deps).

## Command Reference

### V1
- `rail train query <TRAIN>` — train schedule by number
- `rail train sts <FROM> <TO>` — station-to-station (telecodes e.g. BJP, VNP)
- `rail train preselect <KEYWORD>` — train number autocomplete
- `rail station query <TELECODE>` — station by telecode
- `rail station preselect <KEYWORD>` — station name autocomplete
- `rail lucky` — random train

### V2
- `rail main <TRAIN> [--date YYYY-MM-DD]` — train master data (timetable, car info)
- `rail delay <TRAIN>` — delay status per station
- `rail screen <STATION> [--kind arrival|departure]` — station big screen
- `rail exit <TRAIN> <STATION> [--date ...] [--kind ...]` — gate/platform/exit
- `rail coach <TRAIN>` — coach/car image info
- `rail map <TRAIN>` — route line points (GCJ-02)

### Global
- `--pretty` — human-readable JSON output
- `--verbose, -v` — show request URL + status to stderr

## Constraints

- No API key required
- No commercial use, no public relay
- V2 endpoints ~1s response time — set timeout >= 10s
- Station codes use telecodes (e.g. BJP=北京, VNP=北京南, AOH=上海虹桥)
```

---

## Phase 4: Verification

### Task 4.1: Full integration test

**Objective:** Run every subcommand against the live API, confirm all 13 work.

```bash
echo "=== V1 ==="
./rail train query G1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'bureauName' in d else 'FAIL')"
./rail train sts BJP VNP | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if isinstance(d, (list,dict)) else 'FAIL')"
./rail train preselect G1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if isinstance(d, (list,dict)) else 'FAIL')"
./rail station query BJP | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if isinstance(d, (list,dict)) else 'FAIL')"
./rail station preselect 北京 | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if isinstance(d, (list,dict)) else 'FAIL')"
./rail lucky | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'trainNum' in d else 'FAIL')"

echo "=== V2 ==="
./rail main G1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('success') else 'FAIL')"
./rail delay G1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('success') else 'FAIL')"
./rail screen BJP | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('success') else 'FAIL')"
./rail exit G1 VNP | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('success') else 'FAIL')"
./rail coach G1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('success') else 'FAIL')"
./rail map G1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('success') else 'FAIL')"
```

Expected: All 12 print OK. (V2 failures on non-running trains are acceptable.)

---

## Risks

1. **API changes** — V2 is "slowly coming online." Subcommand dispatch is isolated, so new/removed endpoints affect single lines.
2. **JSON key assumptions** — `--raw` flag exists as escape hatch; user can always get raw response and parse manually.
3. **Station telecode lookup** — Users need to know telecodes (BJP = 北京). The `station preselect` command helps discover them, but no built-in reverse lookup table (YAGNI — can add later).
4. **No authentication** — Currently no key required per docs. If this changes, `client.py` single-point update to add header.

---

## Estimated total lines

| File | Lines (est.) |
|---|---|
| `rail` | 6 |
| `rail_cli/__init__.py` | 3 |
| `rail_cli/__main__.py` | 5 |
| `rail_cli/client.py` | 45 |
| `rail_cli/cli.py` | 180 |
| `rail_cli/update.py` | ~230 |
| `README.md` | 60 |
| **Total** | ~300 |

---

## Phase 5: 更新机制（`rail update` + AUTO_UPDATE 自动更新，2026-08-07）

**版本**：0.1.0 → 0.2.0。**提交粒度**：Task 5.1 + 5.2 同一次代码提交（自动更新复用 `rail update` 的更新管线，拆分会产生人为接缝），Task 5.3 文档单独提交。

### Task 5.1: `rail update` 命令 + 安装元数据扩展

**Objective:** 新增 `rail update` 子命令（任何目录可运行），并让安装元数据记录仓库路径。

**Files:**
- Create: `rail_cli/update.py`
- Modify: `rail_cli/cli.py`, `install.sh`, `rail_cli/__init__.py`, `pyproject.toml`

**设计决策:**

1. **布局检测**（`detect_install`）：以 `rail_cli/__file__` 定位——
   - 父目录有 `.install-meta` → **installed 模式**（读 `PREFIX`/`REPO`）
   - 父目录有 `.git` → **repo 模式**（从 clone / pip editable 运行）
   - 都没有 → pip 复制安装，无法自更新（报错 + 指引）
2. **installed 模式**：委托 `bash install.sh --prefix <PREFIX> --update`（git pull + 重装到原位置，单一事实来源，不重复实现）
3. **repo 模式**：`git pull --ff-only origin main`，对比 pull 前后 HEAD 判断"已是最新版本" vs "已更新到 <sha>"
4. **`.install-meta` 增加 `REPO=<仓库路径>`**（install_files 写入）；旧安装无 REPO 字段时，`rail update` 若在仓库目录内运行则自愈回写（`resolve_repo` 的 cwd 兜底）
5. **`find_installed_prefix` 显式 `--prefix` 优先**：多安装并存（如 `~/.local` + 自定义前缀）时，`rail update` 更新当前安装而非默认位置
6. **origin 校验**：更新前确认 origin 含 `rail-cli`，防止对无关仓库 pull

### Task 5.2: 每日自动更新（AUTO_UPDATE，默认开）

**Objective:** 当天首次运行 CLI 时自动更新，默认开启，可关闭/单次跳过。

**设计决策:**

1. **`AUTO_UPDATE` 环境变量**：默认开（未设置/空/任意值 = 开）；`0`/`false`/`no`/`off`/`n`/`disabled` = 关
2. **当天首次运行标记**：`$XDG_CACHE_HOME/rail-cli/last-auto-update`（默认 `~/.cache/rail-cli/`），内容 = YYYYMMDD，flock 串行化
3. **先写标记再更新**：`check_and_reserve_today()` 返回 True 前已写入今天 → 并发进程/重入调用都看到"今天已检查"，不会重复 pull（git index.lock 双保险）
4. **失败不阻塞**：更新失败只警告到 stderr，命令照常执行；标记照写（每天只尝试一次，避免离线时每条命令都卡网络）；提示 `rail update` 手动重试
5. **stdout 纯净**：所有自动更新输出（含 install.sh/git pull 的 stdout）转发到 stderr——否则会污染紧随其后的 API JSON 输出（实测抓到的 bug：`Already up to date.` 混入 stdout）
6. **防递归**：`rail version` / `rail update` 不触发自动更新；install.sh 的 `verify_install` 用 `AUTO_UPDATE=0` 运行（version 会被验证流程调用，否则安装/更新中会递归）
7. **`--no-update` 全局旗标**：单次跳过（根 + 子命令双位置，SUPPRESS 模式与 -v/--pretty/--raw 一致）
8. **`rail update` 成功后 `reserve_today()`**：手动更新当天不再自动更新

**验证（全部实测通过）：**
- 仓库模式：fresh marker → 首跑触发 pull + "已是最新版本"(stderr) + stdout 纯 JSON；同日再跑静默
- `AUTO_UPDATE=0` / `--no-update` → 不写 marker
- `rail version` → 不写 marker
- 已安装模式（`--prefix /tmp/rail-test`）：`rail update` 原位重装；自动更新同样 stdout 纯 JSON
- 旧 meta（无 REPO）+ 仓库 cwd → 自愈回写 REPO 并更新；非仓库 cwd → 清晰报错 exit 1
- install.sh `--update` 在 `--prefix` 显式时优先用该前缀（多安装场景）

### Task 5.3: 文档更新

**Objective:** README / AGENTS.md / PLAN.md 同步更新机制说明。

- `README.md`：更新章节两种方式（`rail update` / `./install.sh --update`）；新增"每日自动更新（AUTO_UPDATE）"章节；全局参数表加 `--no-update`；环境变量表加 `AUTO_UPDATE` / `XDG_CACHE_HOME`
- `AGENTS.md`：关键事实增加更新机制一行
- 本文件（PLAN.md）：追加 Phase 5
