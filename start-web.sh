#!/usr/bin/env bash

# Quick Web Dashboard Start Script
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Plex-Trakt Sync - Web Dashboard${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ No .env file found. Creating from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env file${NC}"
    echo -e "${YELLOW}⚠ Please edit .env with your credentials before continuing${NC}"
    echo ""
    read -p "Press Enter when ready..."
fi

# Enable web mode in .env if not already set
if ! grep -q "WEB_MODE=True" .env; then
    echo -e "${BLUE}Enabling Web Mode...${NC}"
    if grep -q "WEB_MODE=" .env; then
        sed -i.bak 's/WEB_MODE=.*/WEB_MODE=True/' .env
    else
        echo "WEB_MODE=True" >> .env
    fi
    echo -e "${GREEN}✓ Web Mode enabled${NC}"
fi

# Start container
echo ""
echo -e "${BLUE}Starting Docker container...${NC}"
docker-compose -f docker-compose.web.yml up -d

echo ""
echo -e "${GREEN}✓ Container started successfully!${NC}"
echo ""
echo -e "${BLUE}Web Dashboard: ${GREEN}http://localhost:5000${NC}"
echo ""
echo "Useful commands:"
echo "  View logs:    docker-compose -f docker-compose.web.yml logs -f"
echo "  Stop:         docker-compose -f docker-compose.web.yml down"
echo "  Restart:      docker-compose -f docker-compose.web.yml restart"
echo ""

# Try to open browser
if command -v open >/dev/null 2>&1; then
    read -p "Open dashboard in browser? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sleep 2
        open http://localhost:5000
    fi
elif command -v xdg-open >/dev/null 2>&1; then
    read -p "Open dashboard in browser? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sleep 2
        xdg-open http://localhost:5000
    fi
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Setup complete! Enjoy your sync dashboard! 🎉${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
