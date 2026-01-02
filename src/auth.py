"""
Trakt OAuth Device Flow Authentication Handler

Implements headless-friendly OAuth device flow for Trakt API.
Persists tokens to /config for stateless container restarts.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

try:
    import trakt.core
    from trakt import users
except ImportError as e:
    logger.error(f"Failed to import trakt library: {e}")
    logger.error("Please install: pip install trakt.py")
    raise


class TraktAuth:
    """Handle Trakt OAuth device flow authentication with token persistence."""
    
    def __init__(
        self, 
        client_id: str, 
        client_secret: str,
        config_dir: str = "/config"
    ):
        """
        Initialize Trakt authentication handler.
        
        Args:
            client_id: Trakt API client ID
            client_secret: Trakt API client secret
            config_dir: Directory to store token file (default: /config)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.config_dir = Path(config_dir)
        self.token_file = self.config_dir / "trakt_token.json"
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure trakt.py for device authentication
        trakt.core.AUTH_METHOD = trakt.core.DEVICE
        
    def authenticate(self) -> bool:
        """
        Authenticate with Trakt API.
        
        Attempts to load existing token, refreshes if needed,
        or initiates new device flow authentication.
        
        Returns:
            bool: True if authentication successful
        """
        # Try to load existing token
        if self._load_token():
            logger.info("Loaded existing Trakt token")
            
            # Verify token is still valid
            if self._verify_token():
                logger.info("Trakt token is valid")
                return True
            else:
                logger.warning("Trakt token expired, refreshing...")
                if self._refresh_token():
                    return True
                else:
                    logger.warning("Token refresh failed, re-authenticating...")
        
        # No valid token, start device flow
        return self._device_flow_auth()
    
    def _load_token(self) -> bool:
        """Load token from file and configure trakt.core."""
        if not self.token_file.exists():
            logger.debug(f"Token file not found: {self.token_file}")
            return False
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            # Configure trakt.core with credentials
            trakt.core.CLIENT_ID = self.client_id
            trakt.core.CLIENT_SECRET = self.client_secret
            trakt.core.OAUTH_TOKEN = token_data.get('access_token')
            trakt.core.OAUTH_REFRESH = token_data.get('refresh_token')
            trakt.core.OAUTH_EXPIRES_AT = token_data.get('expires_at')
            
            return True
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load token: {e}")
            return False
    
    def _save_token(self, token_data: Dict[str, Any]) -> bool:
        """Save token data to file."""
        try:
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            logger.info(f"Token saved to {self.token_file}")
            return True
        except IOError as e:
            logger.error(f"Failed to save token: {e}")
            return False
    
    def _verify_token(self) -> bool:
        """Verify if current token is valid."""
        try:
            # Try a simple API call to verify token
            from trakt.users import User
            user = User('me')
            _ = user.username
            return True
        except Exception as e:
            logger.debug(f"Token verification failed: {e}")
            return False
    
    def _refresh_token(self) -> bool:
        """Refresh the access token using refresh token."""
        try:
            # trakt.py should handle refresh automatically
            # but we'll trigger it explicitly
            from trakt.core import oauth_refresh
            
            new_token = oauth_refresh()
            if new_token:
                token_data = {
                    'access_token': trakt.core.OAUTH_TOKEN,
                    'refresh_token': trakt.core.OAUTH_REFRESH,
                    'expires_at': trakt.core.OAUTH_EXPIRES_AT
                }
                self._save_token(token_data)
                logger.info("Token refreshed successfully")
                return True
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
        
        return False
    
    def _device_flow_auth(self) -> bool:
        """
        Perform OAuth device flow authentication.
        
        Displays code and URL for user to authorize the application.
        Polls Trakt until authorization is complete or timeout.
        
        Returns:
            bool: True if authentication successful
        """
        logger.info("Starting Trakt device flow authentication...")
        
        try:
            # Configure credentials
            trakt.core.CLIENT_ID = self.client_id
            trakt.core.CLIENT_SECRET = self.client_secret
            
            # Get device code
            from trakt.core import get_device_code
            code_data = get_device_code()
            
            if not code_data:
                logger.error("Failed to get device code")
                return False
            
            device_code = code_data.get('device_code')
            user_code = code_data.get('user_code')
            verification_url = code_data.get('verification_url')
            expires_in = code_data.get('expires_in', 600)
            interval = code_data.get('interval', 5)
            
            # Display instructions to user
            logger.info("=" * 60)
            logger.info("TRAKT AUTHORIZATION REQUIRED")
            logger.info("=" * 60)
            logger.info(f"1. Visit: {verification_url}")
            logger.info(f"2. Enter code: {user_code}")
            logger.info(f"3. Authorize the application")
            logger.info(f"Waiting for authorization (expires in {expires_in}s)...")
            logger.info("=" * 60)
            
            # Poll for authorization
            from trakt.core import get_device_token
            start_time = time.time()
            
            while time.time() - start_time < expires_in:
                try:
                    token_data = get_device_token(device_code)
                    
                    if token_data:
                        # Successfully authorized
                        logger.info("✓ Authorization successful!")
                        
                        # Save token
                        token_to_save = {
                            'access_token': token_data.get('access_token'),
                            'refresh_token': token_data.get('refresh_token'),
                            'expires_at': time.time() + token_data.get('expires_in', 7776000)  # 90 days default
                        }
                        
                        # Update trakt.core
                        trakt.core.OAUTH_TOKEN = token_to_save['access_token']
                        trakt.core.OAUTH_REFRESH = token_to_save['refresh_token']
                        trakt.core.OAUTH_EXPIRES_AT = token_to_save['expires_at']
                        
                        self._save_token(token_to_save)
                        return True
                        
                except Exception as poll_error:
                    # Expected while waiting for user
                    logger.debug(f"Polling... {poll_error}")
                
                time.sleep(interval)
            
            logger.error("Authorization timeout - user did not authorize in time")
            return False
            
        except Exception as e:
            logger.error(f"Device flow authentication failed: {e}", exc_info=True)
            return False
    
    def get_authenticated_session(self) -> bool:
        """
        Get an authenticated Trakt session.
        
        Returns:
            bool: True if session is authenticated and ready
        """
        return self.authenticate()


def init_trakt_auth() -> Optional[TraktAuth]:
    """
    Initialize Trakt authentication from environment variables.
    
    Returns:
        TraktAuth instance if successful, None otherwise
    """
    client_id = os.getenv('TRAKT_CLIENT_ID')
    client_secret = os.getenv('TRAKT_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        logger.error("Missing TRAKT_CLIENT_ID or TRAKT_CLIENT_SECRET environment variables")
        return None
    
    config_dir = os.getenv('CONFIG_DIR', '/config')
    
    auth = TraktAuth(
        client_id=client_id,
        client_secret=client_secret,
        config_dir=config_dir
    )
    
    if auth.authenticate():
        return auth
    else:
        logger.error("Trakt authentication failed")
        return None
