# PlexTraktSync - MoviePilot 插件

Plex 和 Trakt 双向同步插件，用于 MoviePilot 插件系统。

## 功能特性

- ✅ **双向同步**：支持 Plex ↔ Trakt 双向同步
- ✅ **观看记录同步**：自动同步电影和剧集的观看状态
- ✅ **评分同步**：同步 Trakt 评分到 Plex
- ✅ **PIN 码认证**：自动处理 Trakt OAuth 认证流程
- ✅ **批量同步**：支持大量媒体库的高效同步

## 安装方法

### 方式一：直接上传（推荐）
1. 在 MoviePilot 插件管理页面选择「本地安装」
2. 上传 `plextraktsync.zip`
3. 重启 MoviePilot

### 方式二：手动安装
1. 解压 `plextraktsync.zip`
2. 将 `plextraktsync` 文件夹复制到 MoviePilot 插件目录
3. 重启 MoviePilot

## 配置说明

### 必需配置
- **Plex 服务器地址**：Plex 服务器的完整 URL
- **Plex Token**：从 Plex 获取的认证 Token
- **Trakt Client ID**：从 Trakt API 应用获取
- **Trakt Client Secret**：从 Trakt API 应用获取

### 认证流程
1. 填写基本配置后保存
2. 点击「获取 PIN 码并认证」
3. 系统会打开 Trakt 认证页面
4. 输入显示的 PIN 码完成认证
5. 插件会自动换取 Access Token

### 同步选项
- **同步观看记录**：同步已观看的电影和剧集
- **同步评分**：同步 Trakt 评分到 Plex
- **双向同步**：启用后会同时进行 Plex→Trakt 和 Trakt→Plex 的同步

## 版本历史

### v2.1.1 (2026-01-03)
- 修复数据解析问题
- 添加错误处理和重试机制
- 优化 Plex 标记性能

## 打包插件

\`\`\`bash
bash package-plugin.sh
\`\`\`

## 许可证

MIT License
