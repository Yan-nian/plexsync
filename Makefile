# Makefile for Plex-Trakt Sync

.PHONY: help build up down logs restart clean

help:
	@echo "Plex-Trakt Sync - 命令列表:"
	@echo ""
	@echo "  make up       - 启动容器"
	@echo "  make down     - 停止容器"
	@echo "  make logs     - 查看日志"
	@echo "  make restart  - 重启容器"
	@echo "  make clean    - 清理所有"
	@echo ""

up:
	docker-compose up -d
	@echo "✓ 容器已启动"
	@echo "访问: http://localhost:5000"

down:
	docker-compose down

logs:
	docker-compose logs -f

restart:
	docker-compose restart

clean:
	docker-compose down -v
	docker rmi plexsync_plexsync 2>/dev/null || true
