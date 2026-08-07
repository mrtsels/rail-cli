#!/usr/bin/env bash
# install.sh — 一键安装/更新/卸载 rail-cli（RailGo 数据服务 CLI）
#
# 零依赖 Python CLI：安装 = 复制 rail + rail_cli/ 到目标目录 + 建立 rail 命令软链。
# 仓库通过 git 跟踪 mrtsels/rail-cli，可用 --update 一键拉取作者更新并重装。
# 用法：
#   ./install.sh               # 安装到 ~/.local（bin 软链到 ~/.local/bin）
#   ./install.sh --prefix ~/x  # 自定义前缀
#   ./install.sh --user        # 安装到 ~/bin（旧式 macOS/Linux 用户 bin）
#   ./install.sh --update      # git pull 拉取更新并重装到原位置
#   rail update                # CLI 内更新（等价 --update；AUTO_UPDATE 默认开，每天首次运行自动更新）
#   ./install.sh --uninstall   # 卸载
set -euo pipefail

# ---------- 常量 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIL_SRC="$SCRIPT_DIR/rail"
PKG_SRC="$SCRIPT_DIR/rail_cli"
REPO_REMOTE_PATTERN="rail-cli"
PREFIX="${PREFIX:-$HOME/.local}"

# ---------- 工具函数 ----------
info()  { printf '\033[32m%s\033[0m\n' "$*"; }
warn()  { printf '\033[33m%s\033[0m\n' "$*" >&2; }
die()   { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# 跨平台 sed -i（macOS 需要空后缀）
sed_inplace() {
    if [ "$(uname)" = "Darwin" ]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

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
    # 3) PATH 里的 3.10+ 别名（系统自带可能只有 3.9）
    for p in python3.14 python3.13 python3.12 python3.11 python3.10; do
        if command -v "$p" >/dev/null 2>&1 \
            && "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            command -v "$p"; return 0
        fi
    done
    # 4) 常见安装位置的绝对路径（PATH 被污染/精简时兜底）
    for p in \
        "$HOME/miniconda3/bin/python3" "$HOME/anaconda3/bin/python3" \
        "/opt/homebrew/Caskroom/miniconda/base/bin/python3" \
        "/opt/homebrew/bin/python3" "/usr/local/bin/python3" \
        "$HOME/.local/bin/python3"; do
        if [ -x "$p" ] \
            && "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            echo "$p"; return 0
        fi
    done
    return 1
}

# 安装核心：把仓库文件复制到 RAIL_DEST + 软链 + shebang 重写
# 全局变量：BIN_DIR / RAIL_DEST / PYTHON_BIN
install_files() {
    mkdir -p "$BIN_DIR" "$RAIL_DEST"
    cp "$RAIL_SRC" "$RAIL_DEST/rail"
    rm -rf "$RAIL_DEST/rail_cli"          # 清旧包，避免删除的文件残留
    cp -r "$PKG_SRC" "$RAIL_DEST/rail_cli"
    chmod +x "$RAIL_DEST/rail"

    # 重写 shebang 为检测到的 python3 绝对路径。
    # 原因：#!/usr/bin/env python3 依赖 PATH，而 macOS 系统自带 /usr/bin/python3
    # 只有 3.9（不支持 dict | None 语法）。固定绝对路径后，无论用户 shell 的
    # PATH 如何，rail 都能用 >=3.10 的解释器运行。
    if [ -n "$PYTHON_BIN" ]; then
        sed_inplace "1s|^#!.*|#!$PYTHON_BIN|" "$RAIL_DEST/rail"
    fi

    # 软链（幂等：先删旧的）
    rm -f "$BIN_DIR/rail"
    ln -s "$RAIL_DEST/rail" "$BIN_DIR/rail"

    # 记录安装位置 + 仓库路径，供 --update 与 `rail update` 使用
    printf 'PREFIX=%s\nREPO=%s\n' "$PREFIX" "$SCRIPT_DIR" > "$RAIL_DEST/.install-meta"

    info "已安装到 $RAIL_DEST"
    info "命令软链: $BIN_DIR/rail -> $RAIL_DEST/rail"
}

# 验证安装（version + 在线查询）
# AUTO_UPDATE=0：验证流程不触发每日自动更新（否则安装/更新过程中会递归）
verify_install() {
    info "验证安装..."
    AUTO_UPDATE=0 "$BIN_DIR/rail" version
    if command -v curl >/dev/null 2>&1; then
        AUTO_UPDATE=0 "$BIN_DIR/rail" train sts SZQ GGQ 2>/dev/null | python3 -c '
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
}

# 找已安装位置（读 .install-meta）。找不到返回非零。
find_installed_prefix() {
    local cand pfx=""
    # 显式 --prefix 优先：`rail update` 传入当前安装的 prefix，
    # 避免多安装并存时（如 ~/.local 之外还有自定义前缀）更新错位置
    if [ -n "${PREFIX_EXPLICIT:-}" ] && [ -f "$PREFIX/lib/rail-cli/.install-meta" ]; then
        echo "$PREFIX"; return 0
    fi
    for cand in "$HOME/.local" "$HOME" "${PREFIX:-}"; do
        [ -n "$cand" ] || continue
        if [ -f "$cand/lib/rail-cli/.install-meta" ]; then
            pfx="$(sed -n 's/^PREFIX=//p' "$cand/lib/rail-cli/.install-meta")"
            [ -n "$pfx" ] && { echo "$pfx"; return 0; }
        fi
    done
    return 1
}

# ---------- 参数解析 ----------
MODE=install   # install | update | uninstall
PREFIX_EXPLICIT=0
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix)  PREFIX="${2:?--prefix 需要一个路径}"; PREFIX_EXPLICIT=1; shift 2 ;;
        --prefix=*) PREFIX="${1#*=}"; PREFIX_EXPLICIT=1; shift ;;
        --user)    PREFIX="$HOME"; shift ;;
        --update)  MODE=update; shift ;;
        --uninstall) MODE=uninstall; shift ;;
        -h|--help)
            sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) die "未知参数: $1（--help 查看用法）" ;;
    esac
done

# ---------- 卸载 ----------
if [ "$MODE" = uninstall ]; then
    INSTALLED_PREFIX="$(find_installed_prefix)" || INSTALLED_PREFIX="$PREFIX"
    BIN_DIR="$INSTALLED_PREFIX/bin"; RAIL_DEST="$INSTALLED_PREFIX/lib/rail-cli"
    [ -e "$BIN_DIR/rail" ] && rm -f "$BIN_DIR/rail" && info "已删除 $BIN_DIR/rail"
    [ -d "$RAIL_DEST" ] && rm -rf "$RAIL_DEST" && info "已删除 $RAIL_DEST"
    info "卸载完成。"
    exit 0
fi

# ---------- 更新（git pull + 重装） ----------
if [ "$MODE" = update ]; then
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        || die "当前目录不是 git 仓库。--update 需要在 rail-cli 仓库目录内运行（git clone 后进入该目录）。"
    REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
    case "$REMOTE_URL" in
        *"$REPO_REMOTE_PATTERN"*) ;;
        *) die "origin 不是 rail-cli 仓库（当前: ${REMOTE_URL:-无 origin}）。请确认 clone 自 mrtsels/rail-cli。" ;;
    esac

    # 已安装位置：读元数据；找不到则报错指引（避免静默装到默认位置造成重复安装）
    INSTALLED_PREFIX="$(find_installed_prefix)" \
        || die "未找到已安装的 rail-cli。请先运行 ./install.sh 安装；若安装时用了自定义 --prefix，请运行 ./install.sh --prefix <路径> --update。"
    PREFIX="$INSTALLED_PREFIX"
    BIN_DIR="$PREFIX/bin"; RAIL_DEST="$PREFIX/lib/rail-cli"
    info "检测到已安装位置: $RAIL_DEST"

    info "拉取作者更新（git pull origin main）..."
    git pull --ff-only origin main || die "git pull 失败。如有本地改动请先处理（git stash / git commit）。"
    info "更新已拉取，重新安装..."

    # 更新后重新走安装流程
    [ -f "$RAIL_SRC" ] || die "未找到 $RAIL_SRC"
    [ -d "$PKG_SRC" ] || die "未找到 $PKG_SRC"
    PYTHON_BIN="$(find_python)" || die "未找到 Python >= 3.10。请安装 Python 3.10+ 或设置 PYTHON 环境变量指向它。"
    PY_VER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
    info "使用 Python: $PYTHON_BIN ($PY_VER)"

    install_files
    verify_install
    info "更新完成！当前版本: $("$BIN_DIR/rail" version)"
    exit 0
fi

# ---------- 安装 ----------
[ -f "$RAIL_SRC" ] || die "未找到 $RAIL_SRC —— 请在 rail-cli 仓库根目录运行本脚本"
[ -d "$PKG_SRC" ] || die "未找到 $PKG_SRC —— 请在 rail-cli 仓库根目录运行本脚本"

BIN_DIR="$PREFIX/bin"
RAIL_DEST="$PREFIX/lib/rail-cli"

PYTHON_BIN="$(find_python)" || die "未找到 Python >= 3.10。请安装 Python 3.10+ 或设置 PYTHON 环境变量指向它。"
PY_VER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
info "使用 Python: $PYTHON_BIN ($PY_VER)"

install_files

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

verify_install
info "安装完成！运行 \`rail --help\` 查看全部命令。"
info "以后更新：rail update（或 cd $(pwd) && ./install.sh --update）"
