# Plex-Trakt Sync

自动将 Trakt 观看历史同步到 Plex，带 Web Dashboard 监控界面。

## 特性

- 🔄 **自动同步**: Trakt → Plex 单向同步
- 🌐 **Web 界面**: http://localhost:5000 监控和控制
- 🎯 **智能匹配**: 基于 IMDB/TVDB/TMDB ID 精确匹配
- 🔐 **OAuth 认证**: 设备流，无需输入密码
- 🐳 **Docker 部署**: 一键启动，容器化运行

## 快速开始

### 1. 配置

```bash
cp .env.example .env
nano .env  # 编辑填入你的凭据
```

需要配置：
- `PLEX_BASE_URL` - Plex 服务器地址 (如 http://192.168.1.100:32400)
- `PLEX_TOKEN` - [获取方法](https://support.plex.tv/articles/204059436)
- `TRAKT_CLIENT_ID` - 在 [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications) 创建应用获取
- `TRAKT_CLIENT_SECRET` - 同上

### 2. 启动

```bash
# 使用脚本（推荐）
./start-web.sh

# 或直接启动
docker-compose up -d
```

### 3. 授权 Trakt

首次运行需要授权：

```bash
# 查看日志获取授权码
docker-compose logs -f

# 你会看到类似这样的提示：
# 1. Visit: https://trakt.tv/activate
# 2. Enter code: XXXX-XXXX
```

访问 URL，输入代码，点击授权即可。

### 4. 访问 Web Dashboard

打开浏览器访问: **http://localhost:5000**

## 配置选项

在 `.env` 文件中配置：

```bash
# 必需
PLEX_BASE_URL=http://192.168.1.100:32400
PLEX_TOKEN=your_plex_token
TRAKT_CLIENT_ID=your_client_id
TRAKT_CLIENT_SECRET=your_client_secret

# 可选
SYNC_INTERVAL=3600        # 同步间隔（秒），3600 = 1小时
WEB_PORT=5000             # Web 端口
DRY_RUN=False             # True = 只记录不修改
LOG_LEVEL=INFO            # DEBUG/INFO/WARNING/ERROR
PLEX_LIBRARIES=           # 留空=全部，或指定: "Movies,TV Shows"
```

## 常用命令

```bash
make build    # 构建镜像
make up       # 启动容器
make down     # 停止容器
make logs     # 查看日志
make restart  # 重启容器
make clean    # 清理所有
```

或直接使用 docker-compose：

```bash
docker-compose up -d      # 启动
docker-compose logs -f    # 查看日志
docker-compose down       # 停止
docker-compose restart    # 重启
```

## Web Dashboard

访问 http://localhost:5000 查看：

- 📊 **实时状态** - 同步状态、认证状态、连接状态
- 📈 **统计数据** - 匹配数量、标记数量、耗时
- 📜 **历史记录** - 最近 50 次同步记录
- ⚙️ **配置信息** - 当前配置查看
- ▶️ **手动同步** - 点击按钮立即同步

自动刷新，每 5 秒更新一次数据。

## 工作原理

1. **获取数据**: 从 Trakt API 获取你的观看历史
2. **匹配项目**: 使用 IMDB/TVDB/TMDB ID 匹配 Plex 媒体库中的项目
3. **标记观看**: 在 Plex 上标记匹配的项目为已观看
4. **定时运行**: 按设定间隔自动重复执行

## 故障排查

### 连接 Plex 失败

```bash
# 使用实际 IP，不要用 localhost
PLEX_BASE_URL=http://192.168.1.100:32400
```

### 没有项目匹配

```bash
# 启用调试模式查看详情
LOG_LEVEL=DEBUG
docker-compose restart && docker-compose logs -f
```

确保你的 Plex 媒体库有正确的元数据（IMDB/TVDB ID）。

### Trakt 认证失败

```bash
# 删除旧令牌重新认证
rm config/trakt_token.json
docker-compose restart
docker-compose logs -f
```

### Web 界面打不开

```bash
# 检查容器状态
docker ps | grep plexsync

# 检查端口
netstat -an | grep 5000

# 查看日志
docker-compose logs
```

## 项目结构

```
plexsync/
├── src/
│   ├── main.py          # 主入口
│   ├── auth.py          # Trakt OAuth 认证
│   ├── sync.py          # 同步引擎
│   ├── utils.py         # 工具函数
│   ├── web.py           # Web Dashboard
│   └── templates/
│       └── index.html   # Web 界面
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                 # 你的配置（不要提交到 Git）
```

## 高级用法

### 一次性运行（测试）

```bash
docker-compose run --rm -e RUN_ONCE=True plexsync
```

### Dry Run（不修改 Plex）

```bash
docker-compose run --rm -e DRY_RUN=True plexsync
```

### 只同步特定媒体库

```bash
# 在 .env 中设置
PLEX_LIBRARIES=Movies,TV Shows,Anime
```

## API 接口

Web Dashboard 提供 RESTful API：

```bash
# 获取状态
curl http://localhost:5000/api/status

# 启动同步
curl -X POST http://localhost:5000/api/sync/start

# 查看历史
curl http://localhost:5000/api/history
```

## 更新

```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

## License

MIT License

## 致谢

- [PlexAPI](https://github.com/pkkid/python-plexapi)
- [trakt.py](https://github.com/moogar0880/trakt.py)
- [Flask](https://flask.palletsprojects.com/)

---

**Enjoy!** 🎬✨
