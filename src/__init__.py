"""
Plex-Trakt Sync

A lightweight, robust application that synchronizes watched history from Trakt to Plex.
"""

__version__ = '1.0.0'
__author__ = 'Plex-Trakt Sync Contributors'

from .main import main
from .sync import PlexTraktSync
from .auth import TraktAuth

__all__ = ['main', 'PlexTraktSync', 'TraktAuth']
