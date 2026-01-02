"""
Utility functions for Plex-Trakt Sync

Includes logging setup, GUID extraction, and matching helpers.
"""

import logging
import os
import re
import sys
from typing import Optional, Dict, Set, Tuple
from enum import Enum


class GuidProvider(Enum):
    """Supported GUID providers for matching."""
    IMDB = "imdb"
    TVDB = "tvdb"
    TMDB = "tmdb"


def setup_logging() -> None:
    """
    Configure application logging based on LOG_LEVEL environment variable.
    
    Outputs to stdout for Docker container compatibility.
    """
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Map string to logging level
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    level = level_map.get(log_level, logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('plexapi').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at {log_level} level")


def extract_guid(plex_guid: str) -> Optional[Tuple[GuidProvider, str]]:
    """
    Extract provider and ID from Plex GUID string.
    
    Plex GUIDs come in various formats:
    - com.plexapp.agents.imdb://tt1234567?lang=en
    - com.plexapp.agents.thetvdb://123456?lang=en
    - com.plexapp.agents.themoviedb://12345?lang=en
    - plex://movie/5d776b59ad5437001f79c6f8
    - imdb://tt1234567
    - tvdb://123456
    - tmdb://12345
    
    Args:
        plex_guid: The Plex GUID string
        
    Returns:
        Tuple of (provider, id) if parseable, None otherwise
    """
    if not plex_guid:
        return None
    
    logger = logging.getLogger(__name__)
    
    # Pattern 1: com.plexapp.agents format
    agent_pattern = r'com\.plexapp\.agents\.(imdb|thetvdb|themoviedb)://([^?]+)'
    match = re.search(agent_pattern, plex_guid)
    if match:
        provider_name, guid_id = match.groups()
        
        # Normalize provider names
        if provider_name == 'thetvdb':
            provider = GuidProvider.TVDB
        elif provider_name == 'themoviedb':
            provider = GuidProvider.TMDB
        else:
            provider = GuidProvider.IMDB
        
        logger.debug(f"Extracted {provider.value}:{guid_id} from agent format")
        return (provider, guid_id)
    
    # Pattern 2: Simple format (imdb://tt1234567)
    simple_pattern = r'^(imdb|tvdb|tmdb)://([^?]+)'
    match = re.search(simple_pattern, plex_guid)
    if match:
        provider_name, guid_id = match.groups()
        provider = GuidProvider(provider_name)
        logger.debug(f"Extracted {provider.value}:{guid_id} from simple format")
        return (provider, guid_id)
    
    # Pattern 3: Direct ID with prefix (imdb://tt1234567 or tvdb://123456)
    # Already covered above
    
    logger.debug(f"Could not extract GUID from: {plex_guid}")
    return None


def extract_all_guids(plex_item) -> Dict[GuidProvider, str]:
    """
    Extract all available GUIDs from a Plex item.
    
    Checks both the main guid field and the guids list (newer Plex versions).
    
    Args:
        plex_item: A PlexAPI media item (Movie or Episode)
        
    Returns:
        Dictionary mapping provider to ID
    """
    guids = {}
    logger = logging.getLogger(__name__)
    
    # Extract from main guid field
    try:
        if hasattr(plex_item, 'guid') and plex_item.guid:
            result = extract_guid(plex_item.guid)
            if result:
                provider, guid_id = result
                guids[provider] = guid_id
    except Exception as e:
        logger.debug(f"Error extracting main guid: {e}")
    
    # Extract from guids list (Plex TV Series Scanner and Movie Scanner store multiple)
    try:
        if hasattr(plex_item, 'guids'):
            for guid_obj in plex_item.guids:
                guid_str = str(guid_obj.id) if hasattr(guid_obj, 'id') else str(guid_obj)
                result = extract_guid(guid_str)
                if result:
                    provider, guid_id = result
                    guids[provider] = guid_id
    except Exception as e:
        logger.debug(f"Error extracting from guids list: {e}")
    
    return guids


def normalize_imdb_id(imdb_id: str) -> str:
    """
    Normalize IMDB ID to ensure it has 'tt' prefix.
    
    Args:
        imdb_id: IMDB ID with or without 'tt' prefix
        
    Returns:
        IMDB ID with 'tt' prefix
    """
    if not imdb_id:
        return imdb_id
    
    imdb_id = str(imdb_id).strip()
    
    if not imdb_id.startswith('tt'):
        return f'tt{imdb_id}'
    
    return imdb_id


def normalize_tvdb_id(tvdb_id: str) -> str:
    """
    Normalize TVDB ID to remove any non-numeric characters.
    
    Args:
        tvdb_id: TVDB ID
        
    Returns:
        Numeric TVDB ID as string
    """
    if not tvdb_id:
        return tvdb_id
    
    # Extract only digits
    return re.sub(r'\D', '', str(tvdb_id))


def normalize_tmdb_id(tmdb_id: str) -> str:
    """
    Normalize TMDB ID to remove any non-numeric characters.
    
    Args:
        tmdb_id: TMDB ID
        
    Returns:
        Numeric TMDB ID as string
    """
    if not tmdb_id:
        return tmdb_id
    
    # Extract only digits
    return re.sub(r'\D', '', str(tmdb_id))


def match_item(
    plex_guids: Dict[GuidProvider, str],
    trakt_ids: Dict[str, any]
) -> bool:
    """
    Match a Plex item against Trakt IDs.
    
    Uses priority: IMDB > TVDB > TMDB
    
    Args:
        plex_guids: Dictionary of GUIDs extracted from Plex item
        trakt_ids: Dictionary of IDs from Trakt item (imdb, tvdb, tmdb, slug)
        
    Returns:
        True if items match, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    # Priority 1: IMDB (most reliable)
    if GuidProvider.IMDB in plex_guids and trakt_ids.get('imdb'):
        plex_imdb = normalize_imdb_id(plex_guids[GuidProvider.IMDB])
        trakt_imdb = normalize_imdb_id(trakt_ids['imdb'])
        
        if plex_imdb == trakt_imdb:
            logger.debug(f"Match found via IMDB: {plex_imdb}")
            return True
    
    # Priority 2: TVDB (for TV shows)
    if GuidProvider.TVDB in plex_guids and trakt_ids.get('tvdb'):
        plex_tvdb = normalize_tvdb_id(plex_guids[GuidProvider.TVDB])
        trakt_tvdb = normalize_tvdb_id(str(trakt_ids['tvdb']))
        
        if plex_tvdb == trakt_tvdb:
            logger.debug(f"Match found via TVDB: {plex_tvdb}")
            return True
    
    # Priority 3: TMDB (fallback)
    if GuidProvider.TMDB in plex_guids and trakt_ids.get('tmdb'):
        plex_tmdb = normalize_tmdb_id(plex_guids[GuidProvider.TMDB])
        trakt_tmdb = normalize_tmdb_id(str(trakt_ids['tmdb']))
        
        if plex_tmdb == trakt_tmdb:
            logger.debug(f"Match found via TMDB: {plex_tmdb}")
            return True
    
    return False


def get_env_bool(key: str, default: bool = False) -> bool:
    """
    Get boolean value from environment variable.
    
    Accepts: true, yes, 1, on (case-insensitive) as True
    
    Args:
        key: Environment variable name
        default: Default value if not set
        
    Returns:
        Boolean value
    """
    value = os.getenv(key)
    if value is None:
        return default
    
    return value.lower().strip() in ('true', 'yes', '1', 'on')


def get_env_int(key: str, default: int) -> int:
    """
    Get integer value from environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set or invalid
        
    Returns:
        Integer value
    """
    value = os.getenv(key)
    if value is None:
        return default
    
    try:
        return int(value)
    except ValueError:
        logger = logging.getLogger(__name__)
        logger.warning(f"Invalid integer for {key}: {value}, using default: {default}")
        return default


def get_env_list(key: str, default: list = None) -> list:
    """
    Get list value from comma-separated environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set
        
    Returns:
        List of strings
    """
    if default is None:
        default = []
    
    value = os.getenv(key)
    if not value:
        return default
    
    # Split by comma and strip whitespace
    return [item.strip() for item in value.split(',') if item.strip()]


class RateLimiter:
    """Simple rate limiter for API calls with exponential backoff."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.logger = logging.getLogger(__name__)
    
    def should_retry(self, attempt: int, error: Exception) -> Tuple[bool, float]:
        """
        Determine if request should be retried and how long to wait.
        
        Args:
            attempt: Current attempt number (0-indexed)
            error: The exception that occurred
            
        Returns:
            Tuple of (should_retry, delay_seconds)
        """
        if attempt >= self.max_retries:
            return False, 0.0
        
        # Calculate exponential backoff: base_delay * 2^attempt
        delay = self.base_delay * (2 ** attempt)
        
        # Cap at 60 seconds
        delay = min(delay, 60.0)
        
        self.logger.warning(
            f"Retry {attempt + 1}/{self.max_retries} after error: {error}. "
            f"Waiting {delay:.1f}s..."
        )
        
        return True, delay
