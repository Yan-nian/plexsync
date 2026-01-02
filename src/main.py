"""
Main Entry Point for Plex-Trakt Sync

Orchestrates authentication, scheduling, and synchronization with robust error handling.
"""

import os
import sys
import time
import logging
import signal
from typing import Optional
from datetime import datetime

import schedule

from .utils import setup_logging, get_env_int, get_env_bool
from .auth import init_trakt_auth
from .sync import create_sync_engine


logger = logging.getLogger(__name__)


class GracefulKiller:
    """Handle shutdown signals gracefully."""
    
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
    
    def exit_gracefully(self, signum, frame):
        """Set flag to exit on next loop iteration."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.kill_now = True


def validate_environment() -> bool:
    """
    Validate required environment variables are set.
    
    Returns:
        True if all required variables are present, False otherwise
    """
    required_vars = [
        'PLEX_BASE_URL',
        'PLEX_TOKEN',
        'TRAKT_CLIENT_ID',
        'TRAKT_CLIENT_SECRET'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Please check your .env file or environment configuration")
        return False
    
    return True


def run_sync_cycle() -> bool:
    """
    Run a single synchronization cycle.
    
    Returns:
        True if sync completed successfully, False otherwise
    """
    try:
        logger.info(f"Starting sync cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Authenticate with Trakt
        logger.info("Authenticating with Trakt...")
        trakt_auth = init_trakt_auth()
        if not trakt_auth:
            logger.error("Trakt authentication failed")
            return False
        
        # Create sync engine
        logger.info("Initializing sync engine...")
        sync = create_sync_engine()
        if not sync:
            logger.error("Failed to create sync engine")
            return False
        
        # Run synchronization
        stats = sync.run_sync()
        
        # Check if sync had errors
        if stats.errors > 0:
            logger.warning(f"Sync completed with {stats.errors} errors")
            return False
        
        logger.info("Sync cycle completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Sync cycle failed with exception: {e}", exc_info=True)
        return False


def run_once_and_exit() -> int:
    """
    Run synchronization once and exit.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger.info("Running in one-shot mode")
    
    if not validate_environment():
        return 1
    
    success = run_sync_cycle()
    
    if success:
        logger.info("One-shot sync completed successfully")
        return 0
    else:
        logger.error("One-shot sync failed")
        return 1


def main() -> int:
    """
    Main entry point - Always runs with Web Dashboard + background sync.
    
    Returns:
        Exit code
    """
    # Setup logging first
    setup_logging()
    
    logger.info("=" * 60)
    logger.info("Plex-Trakt Sync with Web Dashboard")
    logger.info("Version: 1.0.0")
    logger.info("=" * 60)
    
    if not validate_environment():
        return 1
    
    # Check if running in one-shot mode (for testing)
    run_once = get_env_bool('RUN_ONCE', False)
    if run_once:
        return run_once_and_exit()
    
    # Start web server with background sync scheduler
    try:
        from .web import run_web_server
        web_port = get_env_int('WEB_PORT', 5000)
        sync_interval = get_env_int('SYNC_INTERVAL', 3600)
        
        logger.info(f"Starting Web Dashboard on port {web_port}")
        logger.info(f"Background sync every {sync_interval}s ({sync_interval / 60:.0f} min)")
        
        run_web_server(port=web_port)
        return 0
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
