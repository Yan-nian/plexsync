# Makefile for Plex-Trakt Sync

.PHONY: help build up down logs restart clean test

help:
	@echo "Plex-Trakt Sync - Available Commands:"
	@echo ""
	@echo "  make build     - Build Docker image"
	@echo "  make up        - Start container (CLI mode)"
	@echo "  make web       - Start container with Web Dashboard"
	@echo "  make down      - Stop container"
	@echo "  make logs      - View container logs (follow)"
	@echo "  make restart   - Restart container"
	@echo "  make clean     - Remove container and image"
	@echo "  make test      - Run in dry-run mode"
	@echo "  make shell     - Open shell in container"
	@echo "  make open      - Open web dashboard in browser"
	@echo ""

build:
	@echo "Building Docker image..."
	docker-compose build

up:
	@echo "Starting container (CLI mode)..."
	docker-compose up -d
	@echo "Container started. View logs with: make logs"

web:
	@echo "Starting container with Web Dashboard..."
	docker-compose -f docker-compose.web.yml up -d
	@echo "Web Dashboard available at: http://localhost:5000"
	@echo "View logs with: make logs"

down:
	@echo "Stopping container..."
	docker-compose down
	docker-compose -f docker-compose.web.yml down 2>/dev/null || true

logs:
	@echo "Following logs (Ctrl+C to exit)..."
	docker-compose logs -f

restart:
	@echo "Restarting container..."
	docker-compose restart
	@echo "Container restarted. View logs with: make logs"

clean:
	@echo "Removing container and image..."
	docker-compose down -v
	docker rmi plexsync_plexsync 2>/dev/null || true
	@echo "Cleaned up"

test:
	@echo "Running in dry-run mode..."
	docker-compose run --rm -e DRY_RUN=True plexsync

shell:
	@echo "Opening shell in container..."
	docker-compose exec plexsync /bin/bash

status:
	@echo "Container status:"
	docker-compose ps

open:
	@echo "Opening web dashboard..."
	@command -v open >/dev/null 2>&1 && open http://localhost:5000 || \
	 command -v xdg-open >/dev/null 2>&1 && xdg-open http://localhost:5000 || \
	 echo "Please open http://localhost:5000 in your browser"
