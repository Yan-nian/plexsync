#!/usr/bin/env bash
set -e

echo "================================"
echo "Plex-Trakt Sync"
echo "================================"
echo ""

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  创建 .env 文件..."
    cp .env.example .env
    echo "✓ 已创建 .env"
    echo "⚠️  请编辑 .env 填入你的凭据"
    echo ""
    read -p "按 Enter 继续..."
fi

# 启动容器
echo "启动容器..."
docker-compose up -d

echo ""
echo "✓ 启动成功!"
echo ""
echo "Web Dashboard: http://localhost:5000"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose logs -f"
echo "  停止:     docker-compose down"
echo "  重启:     docker-compose restart"
echo ""

# 尝试打开浏览器
if command -v open >/dev/null 2>&1; then
    sleep 2
    open http://localhost:5000 2>/dev/null || true
elif command -v xdg-open >/dev/null 2>&1; then
    sleep 2
    xdg-open http://localhost:5000 2>/dev/null || true
fi
