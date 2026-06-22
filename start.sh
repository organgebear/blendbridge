#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
# BlendBridge — 启动脚本 (macOS / Linux)
#
# 零依赖：仅需系统自带 Python 3 + Blender
# 无需 pip install、无需下载任何东西
#
# 用法: chmod +x start.sh && ./start.sh
# ══════════════════════════════════════════════════════════════════
set -e

BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      🌉  BlendBridge                      ║${NC}"
echo -e "${CYAN}║      Blender FBX 纹理修复工具             ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── 查找 Python 3 ───────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        v=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
        if [ "$v" -ge 3 ] 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}❌ 未找到 Python 3${NC}"
    echo ""
    echo -e "  macOS:  ${BOLD}brew install python@3${NC}"
    echo -e "  Ubuntu: ${BOLD}sudo apt install python3${NC}"
    echo -e "  官网:   ${BOLD}https://www.python.org/downloads/${NC}"
    echo ""
    exit 1
fi

echo -e "  🐍 Python  ${GREEN}$($PYTHON --version 2>&1)${NC}"

# ── 检查 Blender ────────────────────────────────────────────────
BLENDER=""
if [ -f "/Applications/Blender.app/Contents/MacOS/Blender" ]; then
    BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
elif [ -f "/snap/bin/blender" ]; then
    BLENDER="/snap/bin/blender"
elif command -v blender &>/dev/null; then
    BLENDER="$(command -v blender)"
fi

if [ -n "$BLENDER" ]; then
    echo -e "  🎨 Blender ${GREEN}$("$BLENDER" --version 2>&1 | head -1)${NC}"
else
    echo -e "  ${YELLOW}⚠️  Blender 未找到（不影响启动，但无法处理 .blend）${NC}"
fi

echo ""

# ── 启动 ────────────────────────────────────────────────────────
cd "$PROJECT_DIR/backend"
echo -e "${GREEN}  启动中 → http://localhost:5000${NC}"
echo ""

# 自动打开浏览器
if command -v open &>/dev/null; then
    open "http://localhost:5000"
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:5000"
fi

"$PYTHON" server.py
