#!/bin/bash
# MoviePilot 插件打包脚本

set -e

cd "$(dirname "$0")"

echo "🔧 清理旧文件..."
rm -f plextraktsync.zip
rm -f plextraktsync/__init__.py.backup

echo "📦 打包插件..."
cd plextraktsync
zip -r ../plextraktsync.zip . -x "*.backup" -x "__pycache__/*" -x "*.pyc"
cd ..

echo "✅ 打包完成: plextraktsync.zip"
echo ""
echo "📋 包内容:"
unzip -l plextraktsync.zip

echo ""
echo "🎯 安装方法:"
echo "1. 在 MoviePilot 插件管理页面选择「本地安装」"
echo "2. 上传 plextraktsync.zip"
echo "3. 或将 plextraktsync.zip 解压到 MoviePilot 插件目录"
