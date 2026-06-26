#!/bin/bash
# Yoachi Start Script
# Starts the Flask application and sync manager

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data"
LOGS_DIR="$PROJECT_DIR/logs"

# Create directories if they don't exist
mkdir -p "$DATA_DIR" "$LOGS_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Yoachi...${NC}"

# Check if already running
if pgrep -f "python.*app.py" > /dev/null; then
    echo -e "${YELLOW}Yoachi is already running${NC}"
    exit 1
fi

# Run initial sync
echo -e "${GREEN}Running initial data sync...${NC}"
cd "$PROJECT_DIR"
python3 sync/manager.py --once

# Start sync manager in background
echo -e "${GREEN}Starting sync manager...${NC}"
nohup python3 sync/manager.py > "$LOGS_DIR/sync.log" 2>&1 &
SYNC_PID=$!
echo $SYNC_PID > "$DATA_DIR/sync.pid"
echo -e "${GREEN}Sync manager started (PID: $SYNC_PID)${NC}"

# Start Flask app in background
echo -e "${GREEN}Starting Flask app on port 8201...${NC}"
cd "$PROJECT_DIR"
nohup python3 app.py > "$LOGS_DIR/app.log" 2>&1 &
APP_PID=$!
echo $APP_PID > "$DATA_DIR/app.pid"
echo -e "${GREEN}Flask app started (PID: $APP_PID)${NC}"

# Wait a moment for app to start
sleep 2

# Check if app is running
if pgrep -f "python.*app.py" > /dev/null; then
    echo -e "${GREEN}✓ Yoachi is running${NC}"
    echo -e "${GREEN}  Web UI: http://localhost:5001${NC}"
    echo -e "${GREEN}  Logs: $LOGS_DIR/${NC}"
else
    echo -e "${YELLOW}⚠ Flask app may not have started. Check logs.${NC}"
    exit 1
fi
