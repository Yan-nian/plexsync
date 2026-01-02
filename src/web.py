"""
Web Dashboard for Plex-Trakt Sync

Provides a Flask-based web interface for monitoring and controlling the sync process.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from threading import Thread, Lock
import time

from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS

from .sync import PlexTraktSync, create_sync_engine, SyncStats
from .auth import init_trakt_auth
from .utils import get_env_bool, get_env_int


logger = logging.getLogger(__name__)

# Global state
app = Flask(__name__)
CORS(app)

# Thread-safe state management
state_lock = Lock()
sync_state = {
    'running': False,
    'last_sync': None,
    'last_stats': None,
    'sync_history': [],
    'error': None,
    'trakt_authenticated': False,
    'plex_connected': False
}


def get_state() -> Dict[str, Any]:
    """Get current application state (thread-safe)."""
    with state_lock:
        return state_lock.copy() if hasattr(state_lock, 'copy') else dict(sync_state)


def update_state(**kwargs) -> None:
    """Update application state (thread-safe)."""
    with state_lock:
        sync_state.update(kwargs)


def load_sync_history() -> List[Dict[str, Any]]:
    """Load sync history from file."""
    history_file = Path('/config/sync_history.json')
    if history_file.exists():
        try:
            with open(history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load sync history: {e}")
    return []


def save_sync_history(history: List[Dict[str, Any]]) -> None:
    """Save sync history to file."""
    history_file = Path('/config/sync_history.json')
    try:
        # Keep only last 50 entries
        history = history[-50:]
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save sync history: {e}")


def run_sync_with_status() -> bool:
    """Run synchronization and update status."""
    update_state(running=True, error=None)
    
    try:
        # Authenticate with Trakt
        logger.info("Authenticating with Trakt...")
        trakt_auth = init_trakt_auth()
        if not trakt_auth:
            update_state(running=False, error="Trakt authentication failed", trakt_authenticated=False)
            return False
        
        update_state(trakt_authenticated=True)
        
        # Create sync engine
        logger.info("Initializing sync engine...")
        sync = create_sync_engine()
        if not sync:
            update_state(running=False, error="Failed to create sync engine", plex_connected=False)
            return False
        
        update_state(plex_connected=True)
        
        # Run sync
        start_time = time.time()
        stats = sync.run_sync()
        elapsed = time.time() - start_time
        
        # Update state
        sync_result = {
            'timestamp': datetime.now().isoformat(),
            'duration': round(elapsed, 2),
            'trakt_movies': stats.trakt_movies,
            'trakt_episodes': stats.trakt_episodes,
            'matched_movies': stats.matched_movies,
            'matched_episodes': stats.matched_episodes,
            'marked_watched': stats.marked_watched,
            'errors': stats.errors,
            'success': stats.errors == 0
        }
        
        # Update history
        history = load_sync_history()
        history.append(sync_result)
        save_sync_history(history)
        
        update_state(
            running=False,
            last_sync=datetime.now().isoformat(),
            last_stats=sync_result,
            sync_history=history,
            error=None if stats.errors == 0 else f"{stats.errors} errors occurred"
        )
        
        return stats.errors == 0
        
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        update_state(running=False, error=str(e))
        return False


# Routes
@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Get current sync status."""
    return jsonify(sync_state)


@app.route('/api/config')
def api_config():
    """Get current configuration (sanitized)."""
    config = {
        'plex_url': os.getenv('PLEX_BASE_URL', ''),
        'sync_interval': get_env_int('SYNC_INTERVAL', 3600),
        'dry_run': get_env_bool('DRY_RUN', False),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'libraries': os.getenv('PLEX_LIBRARIES', 'All'),
        'trakt_configured': bool(os.getenv('TRAKT_CLIENT_ID') and os.getenv('TRAKT_CLIENT_SECRET')),
        'plex_configured': bool(os.getenv('PLEX_BASE_URL') and os.getenv('PLEX_TOKEN'))
    }
    return jsonify(config)


@app.route('/api/history')
def api_history():
    """Get sync history."""
    history = load_sync_history()
    return jsonify(history)


@app.route('/api/sync/start', methods=['POST'])
def api_sync_start():
    """Start a manual sync."""
    if sync_state['running']:
        return jsonify({'error': 'Sync already running'}), 400
    
    # Run sync in background thread
    thread = Thread(target=run_sync_with_status, daemon=True)
    thread.start()
    
    return jsonify({'message': 'Sync started'})


@app.route('/api/logs')
def api_logs():
    """Get recent logs."""
    # This is a simplified version - in production you'd tail the actual log file
    return jsonify({
        'logs': [
            {'timestamp': datetime.now().isoformat(), 'level': 'INFO', 'message': 'Log streaming not implemented yet'}
        ]
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


def init_web_state():
    """Initialize web state on startup."""
    logger.info("Initializing web dashboard state...")
    
    # Load history
    history = load_sync_history()
    
    # Check authentication status
    trakt_token_file = Path('/config/trakt_token.json')
    trakt_authenticated = trakt_token_file.exists()
    
    update_state(
        sync_history=history,
        trakt_authenticated=trakt_authenticated,
        last_sync=history[-1]['timestamp'] if history else None,
        last_stats=history[-1] if history else None
    )


def run_web_server(host: str = '0.0.0.0', port: int = 5000):
    """Run the Flask web server with background sync scheduler."""
    init_web_state()
    
    # Get sync interval and start background scheduler
    from .utils import get_env_int
    import schedule
    from threading import Thread
    
    sync_interval = get_env_int('SYNC_INTERVAL', 3600)
    
    # Run initial sync in background
    logger.info("Starting initial sync in background...")
    Thread(target=run_sync_with_status, daemon=True).start()
    
    # Schedule recurring syncs
    schedule.every(sync_interval).seconds.do(
        lambda: Thread(target=run_sync_with_status, daemon=True).start()
    )
    
    # Start scheduler in background thread
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    Thread(target=run_scheduler, daemon=True).start()
    
    logger.info(f"Starting web dashboard on {host}:{port}")
    logger.info(f"Background sync every {sync_interval}s")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    from .utils import setup_logging
    setup_logging()
    run_web_server()
