"""
Core Synchronization Logic

Fetches watched history from Trakt, matches with Plex items,
and marks items as watched on Plex.
"""

import logging
import time
from typing import List, Dict, Set, Optional, Any, Generator
from dataclasses import dataclass
from datetime import datetime

from plexapi.server import PlexServer
from plexapi.video import Movie, Show, Episode
import trakt.movies
import trakt.tv
from trakt.users import User

from .utils import (
    extract_all_guids,
    match_item,
    get_env_bool,
    get_env_list,
    RateLimiter,
    GuidProvider
)


logger = logging.getLogger(__name__)


@dataclass
class TraktWatchedItem:
    """Represents a watched item from Trakt."""
    title: str
    year: Optional[int]
    ids: Dict[str, Any]
    media_type: str  # 'movie' or 'episode'
    
    # For episodes
    show_title: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    
    def __str__(self) -> str:
        if self.media_type == 'movie':
            return f"{self.title} ({self.year})"
        else:
            return f"{self.show_title} S{self.season:02d}E{self.episode:02d}"


@dataclass
class SyncStats:
    """Statistics for a sync run."""
    trakt_movies: int = 0
    trakt_episodes: int = 0
    plex_movies: int = 0
    plex_episodes: int = 0
    matched_movies: int = 0
    matched_episodes: int = 0
    marked_watched: int = 0
    errors: int = 0
    
    def __str__(self) -> str:
        return (
            f"Trakt: {self.trakt_movies} movies, {self.trakt_episodes} episodes | "
            f"Plex: {self.plex_movies} movies, {self.plex_episodes} episodes | "
            f"Matched: {self.matched_movies} movies, {self.matched_episodes} episodes | "
            f"Marked watched: {self.marked_watched} | Errors: {self.errors}"
        )


class PlexTraktSync:
    """Main synchronization engine for Plex-Trakt sync."""
    
    def __init__(
        self,
        plex_url: str,
        plex_token: str,
        dry_run: bool = False,
        library_filter: Optional[List[str]] = None
    ):
        """
        Initialize Plex-Trakt synchronization engine.
        
        Args:
            plex_url: Plex server URL
            plex_token: Plex authentication token
            dry_run: If True, only log actions without making changes
            library_filter: List of library names to sync (None = all)
        """
        self.plex_url = plex_url
        self.plex_token = plex_token
        self.dry_run = dry_run
        self.library_filter = library_filter
        self.rate_limiter = RateLimiter()
        
        # Initialize Plex connection
        self.plex: Optional[PlexServer] = None
        self._connect_plex()
        
    def _connect_plex(self) -> None:
        """Establish connection to Plex server."""
        try:
            logger.info(f"Connecting to Plex server: {self.plex_url}")
            self.plex = PlexServer(self.plex_url, self.plex_token)
            logger.info(f"Connected to Plex server: {self.plex.friendlyName}")
        except Exception as e:
            logger.error(f"Failed to connect to Plex: {e}")
            raise
    
    def fetch_trakt_watched_movies(self) -> List[TraktWatchedItem]:
        """
        Fetch all watched movies from Trakt.
        
        Returns:
            List of watched movies
        """
        logger.info("Fetching watched movies from Trakt...")
        watched_movies = []
        
        try:
            user = User('me')
            watched = user.watched_movies
            
            for movie in watched:
                try:
                    # Extract IDs
                    ids = {}
                    if hasattr(movie, 'ids') and movie.ids:
                        ids = {
                            'imdb': getattr(movie.ids, 'imdb', None),
                            'tvdb': getattr(movie.ids, 'tvdb', None),
                            'tmdb': getattr(movie.ids, 'tmdb', None),
                            'trakt': getattr(movie.ids, 'trakt', None),
                            'slug': getattr(movie.ids, 'slug', None)
                        }
                    
                    item = TraktWatchedItem(
                        title=movie.title,
                        year=getattr(movie, 'year', None),
                        ids=ids,
                        media_type='movie'
                    )
                    watched_movies.append(item)
                    
                except Exception as e:
                    logger.warning(f"Error parsing Trakt movie: {e}")
            
            logger.info(f"Fetched {len(watched_movies)} watched movies from Trakt")
            return watched_movies
            
        except Exception as e:
            logger.error(f"Failed to fetch Trakt watched movies: {e}")
            return []
    
    def fetch_trakt_watched_episodes(self) -> List[TraktWatchedItem]:
        """
        Fetch all watched episodes from Trakt.
        
        Returns:
            List of watched episodes
        """
        logger.info("Fetching watched episodes from Trakt...")
        watched_episodes = []
        
        try:
            user = User('me')
            watched_shows = user.watched_shows
            
            for show in watched_shows:
                try:
                    show_title = show.title
                    show_ids = {}
                    
                    if hasattr(show, 'ids') and show.ids:
                        show_ids = {
                            'imdb': getattr(show.ids, 'imdb', None),
                            'tvdb': getattr(show.ids, 'tvdb', None),
                            'tmdb': getattr(show.ids, 'tmdb', None),
                            'trakt': getattr(show.ids, 'trakt', None),
                            'slug': getattr(show.ids, 'slug', None)
                        }
                    
                    # Iterate through seasons and episodes
                    for season in show.seasons:
                        for episode in season.episodes:
                            try:
                                item = TraktWatchedItem(
                                    title=episode.title if hasattr(episode, 'title') else f"Episode {episode.number}",
                                    year=getattr(show, 'year', None),
                                    ids=show_ids,  # Use show IDs for matching
                                    media_type='episode',
                                    show_title=show_title,
                                    season=season.number,
                                    episode=episode.number
                                )
                                watched_episodes.append(item)
                            except Exception as e:
                                logger.warning(f"Error parsing episode {show_title} S{season.number}E{episode.number}: {e}")
                    
                except Exception as e:
                    logger.warning(f"Error parsing Trakt show: {e}")
            
            logger.info(f"Fetched {len(watched_episodes)} watched episodes from Trakt")
            return watched_episodes
            
        except Exception as e:
            logger.error(f"Failed to fetch Trakt watched episodes: {e}")
            return []
    
    def get_plex_libraries(self) -> List[Any]:
        """
        Get Plex libraries to sync based on filter.
        
        Returns:
            List of Plex library sections
        """
        if not self.plex:
            return []
        
        all_libraries = self.plex.library.sections()
        
        # Filter by library names if specified
        if self.library_filter:
            filtered = [lib for lib in all_libraries if lib.title in self.library_filter]
            logger.info(f"Filtering libraries: {[lib.title for lib in filtered]}")
            return filtered
        
        # Only include movie and show libraries
        media_libraries = [
            lib for lib in all_libraries 
            if lib.type in ('movie', 'show')
        ]
        
        logger.info(f"Using libraries: {[lib.title for lib in media_libraries]}")
        return media_libraries
    
    def fetch_plex_movies(self) -> Generator[Movie, None, None]:
        """
        Fetch all movies from Plex libraries.
        
        Yields movies one at a time to avoid loading entire library into memory.
        
        Yields:
            Movie objects
        """
        libraries = self.get_plex_libraries()
        
        for library in libraries:
            if library.type != 'movie':
                continue
            
            logger.info(f"Fetching movies from library: {library.title}")
            
            try:
                # Use pagination to avoid memory issues
                for movie in library.search():
                    yield movie
            except Exception as e:
                logger.error(f"Error fetching movies from {library.title}: {e}")
    
    def fetch_plex_episodes(self) -> Generator[tuple[Show, Episode], None, None]:
        """
        Fetch all episodes from Plex TV libraries.
        
        Yields (show, episode) tuples to maintain show context.
        
        Yields:
            Tuple of (Show, Episode)
        """
        libraries = self.get_plex_libraries()
        
        for library in libraries:
            if library.type != 'show':
                continue
            
            logger.info(f"Fetching episodes from library: {library.title}")
            
            try:
                # Iterate through shows
                for show in library.search():
                    try:
                        # Iterate through episodes
                        for episode in show.episodes():
                            yield (show, episode)
                    except Exception as e:
                        logger.warning(f"Error fetching episodes from show {show.title}: {e}")
            except Exception as e:
                logger.error(f"Error fetching shows from {library.title}: {e}")
    
    def sync_movies(self, trakt_watched: List[TraktWatchedItem]) -> tuple[int, int]:
        """
        Sync watched movies from Trakt to Plex.
        
        Args:
            trakt_watched: List of watched movies from Trakt
            
        Returns:
            Tuple of (matched_count, marked_count)
        """
        logger.info("Syncing movies...")
        matched_count = 0
        marked_count = 0
        
        # Create a set of Trakt IDs for quick lookup
        trakt_ids_set = set()
        trakt_lookup = {}
        
        for item in trakt_watched:
            # Build lookup key from available IDs
            if item.ids.get('imdb'):
                key = ('imdb', item.ids['imdb'])
                trakt_ids_set.add(key)
                trakt_lookup[key] = item
            if item.ids.get('tmdb'):
                key = ('tmdb', str(item.ids['tmdb']))
                trakt_ids_set.add(key)
                trakt_lookup[key] = item
        
        # Iterate through Plex movies
        for plex_movie in self.fetch_plex_movies():
            try:
                # Skip if already watched
                if plex_movie.isWatched:
                    continue
                
                # Extract GUIDs from Plex item
                plex_guids = extract_all_guids(plex_movie)
                
                if not plex_guids:
                    logger.debug(f"No GUIDs found for: {plex_movie.title}")
                    continue
                
                # Check for match
                matched = False
                matched_trakt_item = None
                
                # Check IMDB
                if GuidProvider.IMDB in plex_guids:
                    key = ('imdb', plex_guids[GuidProvider.IMDB])
                    if key in trakt_ids_set:
                        matched = True
                        matched_trakt_item = trakt_lookup[key]
                
                # Check TMDB
                if not matched and GuidProvider.TMDB in plex_guids:
                    key = ('tmdb', plex_guids[GuidProvider.TMDB])
                    if key in trakt_ids_set:
                        matched = True
                        matched_trakt_item = trakt_lookup[key]
                
                if matched:
                    matched_count += 1
                    
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would mark as watched: {plex_movie.title} ({plex_movie.year})")
                    else:
                        try:
                            plex_movie.markWatched()
                            logger.info(f"✓ Marked as watched: {plex_movie.title} ({plex_movie.year})")
                            marked_count += 1
                        except Exception as e:
                            logger.error(f"Failed to mark watched: {plex_movie.title} - {e}")
            
            except Exception as e:
                logger.error(f"Error processing Plex movie: {e}")
        
        return matched_count, marked_count
    
    def sync_episodes(self, trakt_watched: List[TraktWatchedItem]) -> tuple[int, int]:
        """
        Sync watched episodes from Trakt to Plex.
        
        Args:
            trakt_watched: List of watched episodes from Trakt
            
        Returns:
            Tuple of (matched_count, marked_count)
        """
        logger.info("Syncing episodes...")
        matched_count = 0
        marked_count = 0
        
        # Group Trakt episodes by show and build lookup
        # Key: (show_id_type, show_id, season, episode)
        trakt_episodes_lookup = {}
        
        for item in trakt_watched:
            # Build lookup keys for this episode
            keys = []
            
            if item.ids.get('imdb'):
                keys.append(('imdb', item.ids['imdb'], item.season, item.episode))
            if item.ids.get('tvdb'):
                keys.append(('tvdb', str(item.ids['tvdb']), item.season, item.episode))
            if item.ids.get('tmdb'):
                keys.append(('tmdb', str(item.ids['tmdb']), item.season, item.episode))
            
            for key in keys:
                trakt_episodes_lookup[key] = item
        
        # Iterate through Plex episodes
        for show, episode in self.fetch_plex_episodes():
            try:
                # Skip if already watched
                if episode.isWatched:
                    continue
                
                # Extract GUIDs from show (not episode)
                show_guids = extract_all_guids(show)
                
                if not show_guids:
                    logger.debug(f"No GUIDs found for show: {show.title}")
                    continue
                
                # Get season and episode numbers
                season_num = episode.seasonNumber
                episode_num = episode.episodeNumber
                
                # Check for match
                matched = False
                matched_trakt_item = None
                
                # Check IMDB
                if GuidProvider.IMDB in show_guids:
                    key = ('imdb', show_guids[GuidProvider.IMDB], season_num, episode_num)
                    if key in trakt_episodes_lookup:
                        matched = True
                        matched_trakt_item = trakt_episodes_lookup[key]
                
                # Check TVDB
                if not matched and GuidProvider.TVDB in show_guids:
                    key = ('tvdb', show_guids[GuidProvider.TVDB], season_num, episode_num)
                    if key in trakt_episodes_lookup:
                        matched = True
                        matched_trakt_item = trakt_episodes_lookup[key]
                
                # Check TMDB
                if not matched and GuidProvider.TMDB in show_guids:
                    key = ('tmdb', show_guids[GuidProvider.TMDB], season_num, episode_num)
                    if key in trakt_episodes_lookup:
                        matched = True
                        matched_trakt_item = trakt_episodes_lookup[key]
                
                if matched:
                    matched_count += 1
                    
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would mark as watched: {show.title} S{season_num:02d}E{episode_num:02d}")
                    else:
                        try:
                            episode.markWatched()
                            logger.info(f"✓ Marked as watched: {show.title} S{season_num:02d}E{episode_num:02d}")
                            marked_count += 1
                        except Exception as e:
                            logger.error(f"Failed to mark watched: {show.title} S{season_num:02d}E{episode_num:02d} - {e}")
            
            except Exception as e:
                logger.error(f"Error processing Plex episode: {e}")
        
        return matched_count, marked_count
    
    def run_sync(self) -> SyncStats:
        """
        Run full synchronization cycle.
        
        Returns:
            Statistics for the sync run
        """
        stats = SyncStats()
        start_time = time.time()
        
        logger.info("=" * 60)
        logger.info("Starting Plex-Trakt synchronization")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 60)
        
        try:
            # Fetch watched items from Trakt
            trakt_movies = self.fetch_trakt_watched_movies()
            trakt_episodes = self.fetch_trakt_watched_episodes()
            
            stats.trakt_movies = len(trakt_movies)
            stats.trakt_episodes = len(trakt_episodes)
            
            # Sync movies
            if trakt_movies:
                matched, marked = self.sync_movies(trakt_movies)
                stats.matched_movies = matched
                stats.marked_watched += marked
            
            # Sync episodes
            if trakt_episodes:
                matched, marked = self.sync_episodes(trakt_episodes)
                stats.matched_episodes = matched
                stats.marked_watched += marked
            
        except Exception as e:
            logger.error(f"Sync failed with error: {e}", exc_info=True)
            stats.errors += 1
        
        elapsed_time = time.time() - start_time
        
        logger.info("=" * 60)
        logger.info(f"Synchronization complete in {elapsed_time:.1f}s")
        logger.info(stats)
        logger.info("=" * 60)
        
        return stats


def create_sync_engine() -> Optional[PlexTraktSync]:
    """
    Create PlexTraktSync instance from environment variables.
    
    Returns:
        PlexTraktSync instance if successful, None otherwise
    """
    import os
    
    plex_url = os.getenv('PLEX_BASE_URL')
    plex_token = os.getenv('PLEX_TOKEN')
    
    if not plex_url or not plex_token:
        logger.error("Missing PLEX_BASE_URL or PLEX_TOKEN environment variables")
        return None
    
    dry_run = get_env_bool('DRY_RUN', False)
    library_filter = get_env_list('PLEX_LIBRARIES')
    
    try:
        sync = PlexTraktSync(
            plex_url=plex_url,
            plex_token=plex_token,
            dry_run=dry_run,
            library_filter=library_filter if library_filter else None
        )
        return sync
    except Exception as e:
        logger.error(f"Failed to create sync engine: {e}")
        return None
