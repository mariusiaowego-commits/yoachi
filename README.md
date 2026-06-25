# Yoachi - Children's Achievement Badge System 🏆

A fun achievement tracking system for kids, inheriting data from dizical.

## Features

- 🎯 Badge wall display with achievement tracking
- 🔄 Automatic sync from dizical every 5 minutes
- 📱 Responsive design for all devices
- 🎨 Kid-friendly UI with animations
- 🔌 RESTful JSON API

## Quick Start

```bash
# Start the application
./scripts/start.sh

# Stop the application
./scripts/stop.sh

# Manual sync
python3 sync/manager.py --once
```

## Access

- **Web UI:** http://localhost:5001
- **API:** http://localhost:5001/api/badges

## Project Structure

```
yoachi/
├── app.py                 # Flask application
├── config.py              # Configuration
├── requirements.txt       # Python dependencies
├── schema.sql             # Database schema
├── sync/
│   ├── __init__.py
│   └── manager.py         # Data sync from dizical
├── data/
│   └── yoachi.db          # SQLite database
├── static/
│   ├── css/
│   │   └── custom.css
│   └── js/
│       └── app.js
├── templates/
│   ├── base.html
│   └── badge_wall.html
├── scripts/
│   ├── start.sh
│   └── stop.sh
└── logs/
    ├── app.log
    └── sync.log
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Badge wall page |
| `/api/badges` | GET | All badges (JSON) |
| `/api/badges/<id>` | GET | Single badge detail |
| `/api/categories` | GET | All categories |

## Configuration

Edit `config.py` to modify:
- Port (default: 5001)
- Sync interval (default: 300 seconds)
- Database paths

## Data Sync

Yoachi syncs data from dizical every 5 minutes:
- Uses SQLite backup API for proper WAL handling
- Atomic copy with validation
- Read-only access to dizical database

## Tech Stack

- **Backend:** Python + Flask
- **Database:** SQLite
- **Frontend:** HTML + CSS + Alpine.js
- **Sync:** Custom sync manager

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run in development mode
python3 app.py

# Run sync once
python3 sync/manager.py --once
```

## License

Internal project - yoachi v1.0.0
