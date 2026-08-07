#!/usr/bin/env bash
# install.sh — 一键安装 rail-cli（RailGo 数据服务 CLI）
#
# 零依赖 Python CLI：安装 = 复制 rail + rail_cli/ 到目标目录 + 建立 rail 命令软链。
# 用法：
#   ./install.sh               # 安装到 ~/.local（bin 软链到 ~/.local/bin）
#   ./install.sh --prefix ~/x  # 自定义前缀
#   ./install.sh --user        # 安装到 ~/bin（旧式 macOS/Linux 用户 bin）
#   ./install.sh --uninstall   # 卸载
set -euo pipefail

# ---------- 常量 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIL_SRC="$SCRIPT_DIR/rail"
PKG_SRC="$SCRIPT_DIR/rail_cli"
MIN_PY=(3 10)
PREFIX="${PREFIX:-$HOME/.local}"

# ---------- 工具函数 ----------
info()  { printf '\033[32m%s\033[0m\n' "$*"; }
warn()  { printf '\033[33m%s\033[0m\n' "$*" >&2; }
die()   { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# 找可用的 python3（>= 3.10，支持 dict | None 语法）
find_python() {
    # 1) 环境变量显式指定
    if [ -n "${PYTHON:-}" ] && "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        echo "$PYTHON"; return 0
    fi
    # 2) PATH 里的 python3
    if command -v python3 >/dev/null 2>&1 \
        && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        command -v python3; return 0
    fi
    # 3) 常见 3.10+ 别名（系统自带可能只有 3.9）
    for p in python3.14 python3.13 python3.12 python3.11 python3.10; do
        if command -v "$p" >/dev/null 2>&1 \
            && "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            command -v "$p"; return 0
        fi
    done
    return 1
}

# ---------- 参数解析 ----------
UNINSTALL=0
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix)  PREFIX="${2:?--prefix 需要一个路径}"; shift 2 ;;
        --prefix=*) PREFIX="${1#*=}"; shift ;;
        --user)    PREFIX="$HOME"; shift ;;
        --uninstall) UNINSTALL=1; shift ;;
        -h|--help)
            sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) die "未知参数: $1（--help 查看用法）" ;;
    esac
done

BIN_DIR="$PREFIX/bin"
RAIL_DEST="$PREFIX/lib/rail-cli"

# ---------- 卸载 ----------
if [ "$UNINSTALL" = 1 ]; then
    [ -e "$BIN_DIR/rail" ] && rm -f "$BIN_DIR/rail" && info "已删除 $BIN_DIR/rail"
    [ -d "$RAIL_DEST" ] && rm -rf "$RAIL_DEST" && info "已删除 $RAIL_DEST"
    info "卸载完成。"
    exit 0
fi

# ---------- 前置检查 ----------
[ -f "$RAIL_SRC" ] || die "未找到 $RAIL_SRC —— 请在 rail-cli 仓库根目录运行本脚本"
[ -d "$PKG_SRC" ] || die "未找到 $PKG_SRC —— 请在 rail-cli 仓库根目录运行本脚本"

PYTHON_BIN="$(find_python)" || die "未找到 Python >= 3.10。请安装 Python 3.10+ 或设置 PYTHON 环境变量指向它。"
PY_VER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
info "使用 Python: $PYTHON_BIN ($PY_VER)"

# ---------- 安装 ----------
mkdir -p "$BIN_DIR" "$RAIL_DEST"
cp "$RAIL_SRC" "$RAIL_DEST/rail"
cp -r "$PKG_SRC" "$RAIL_DEST/rail_cli"
chmod +x "$RAIL_DEST/rail"

# 重写 shebang 为检测到的 python3 绝对路径。
# 原因：#!/usr/bin/env python3 依赖 PATH，而 macOS 系统自带 /usr/bin/python3
# 只有 3.9（不支持 dict | None 语法）。固定绝对路径后，无论用户 shell 的
# PATH 如何，rail 都能用 >=3.10 的解释器运行。
if [ -n "$PYTHON_BIN" ]; then
    if [ "$(uname)" = "Darwin" ]; then
        sed -i '' "1s|^#!.*|#!$PYTHON_BIN|" "$RAIL_DEST/rail"
    else
        sed -i "1s|^#!.*|#!$PYTHON_BIN|" "$RAIL_DEST/rail"
    fi
fi

# 软链（幂等：先删旧的）
rm -f "$BIN_DIR/rail"
ln -s "$RAIL_DEST/rail" "$BIN_DIR/rail"
info "已安装到 $RAIL_DEST"
info "命令软链: $BIN_DIR/rail -> $RAIL_DEST/rail"

# ---------- PATH 检查 ----------
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        warn "注意: $BIN_DIR 不在 PATH 中。"
        if [ -t 0 ]; then
            printf '是否将其加入 shell 配置文件？[Y/n] '
            read -r ans
            case "${ans:-y}" in
                y|Y|"")
                    SHELL_RC=""
                    case "${SHELL:-}" in
                        *zsh) SHELL_RC="$HOME/.zshrc" ;;
                        *bash) [ -n "$BASH_VERSION" ] && SHELL_RC="$HOME/.bashrc" || SHELL_RC="$HOME/.bash_profile" ;;
                    esac
                    if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
                        printf '\nexport PATH="%s:$PATH"\n' "$BIN_DIR" >> "$SHELL_RC"
                        info "已追加 PATH 到 ${SHELL_RC}（重新打开终端生效）"
                    else
                        warn "无法自动识别 shell 配置文件，请手动执行: export PATH=\"$BIN_DIR:\$PATH\""
                    fi
                    ;;
                *) warn "跳过。可手动执行: export PATH=\"$BIN_DIR:\$PATH\"" ;;
            esac
        else
            warn "非交互模式，跳过 PATH 配置。手动执行: export PATH=\"$BIN_DIR:\$PATH\""
        fi
        ;;
esac

# ---------- 验证 ----------
info "验证安装..."
"$BIN_DIR/rail" version
if command -v curl >/dev/null 2>&1; then
    "$BIN_DIR/rail" train sts SZQ GGQ 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    n = len(d)
    first = d[0]["number"] if n else "无"
    print("OK 深圳→广州东区间查询: %d 趟车（例如 %s）" % (n, first))
except Exception:
    print("WARN 区间查询验证跳过（网络或 API 异常）")
' 2>/dev/null || warn "在线验证跳过（网络或 API 异常）"
fi
info "安装完成！运行 \`rail --help\` 查看全部命令。"
