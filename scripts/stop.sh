#!/bin/bash
# Yoachi Stop Script
# Stops the Flask application and sync manager

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${RED}Stopping Yoachi...${NC}"

# Stop Flask app
if [ -f "$DATA_DIR/app.pid" ]; then
    APP_PID=$(cat "$DATA_DIR/app.pid")
    if kill -0 "$APP_PID" 2>/dev/null; then
        kill "$APP_PID"
        echo -e "${GREEN}Flask app stopped (PID: $APP_PID)${NC}"
    else
        echo -e "${YELLOW}Flask app was not running${NC}"
    fi
    rm -f "$DATA_DIR/app.pid"
else
    echo -e "${YELLOW}No Flask app PID file found${NC}"
fi

# Stop sync manager
if [ -f "$DATA_DIR/sync.pid" ]; then
    SYNC_PID=$(cat "$DATA_DIR/sync.pid")
    if kill -0 "$SYNC_PID" 2>/dev/null; then
        kill "$SYNC_PID"
        echo -e "${GREEN}Sync manager stopped (PID: $SYNC_PID)${NC}"
    else
        echo -e "${YELLOW}Sync manager was not running${NC}"
    fi
    rm -f "$DATA_DIR/sync.pid"
else
    echo -e "${YELLOW}No sync manager PID file found${NC}"
fi

# Cleanup any remaining processes
pkill -f "python.*app.py" 2>/dev/null || true
pkill -f "python.*sync/manager.py" 2>/dev/null || true

echo -e "${GREEN}✓ Yoachi stopped${NC}"
