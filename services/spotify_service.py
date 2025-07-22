import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time

logger = logging.getLogger(__name__)

class SpotifyService:
    """Real-time Spotify API integration service"""
    
    def __init__(self):
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        
        if not self.client_id or not self.client_secret:
            logger.warning("Spotify credentials not configured - using mock data")
            self.spotify = None
        else:
            try:
                client_credentials_manager = SpotifyClientCredentials(
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
                self.spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                logger.info("Spotify API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Spotify API: {e}")
                self.spotify = None
        
        # Simple in-memory cache
        self.cache = {}
        self.cache_expiry = {}
        self.cache_duration = timedelta(hours=1)
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry[key]
    
    def _cache_data(self, key: str, data: Any) -> None:
        """Cache data with expiry"""
        self.cache[key] = data
        self.cache_expiry[key] = datetime.now() + self.cache_duration
    
    def search_artists(self, query: str, limit: int = 20, market: str = 'US') -> List[Dict]:
        """Search for artists using Spotify API with real-time data"""
        cache_key = f"search_artists_{query}_{limit}_{market}"
        
        # Check cache first
        if self._is_cache_valid(cache_key):
            logger.info(f"Returning cached search results for: {query}")
            return self.cache[cache_key]
        
        if not self.spotify:
            return self._get_mock_search_results(query, limit)
        
        try:
            results = self.spotify.search(
                q=query,
                type='artist',
                limit=limit,
                market=market
            )
            
            artists = []
            for artist in results['artists']['items']:
                artist_data = {
                    'artist_id': artist['id'],
                    'name': artist['name'],
                    'genres': artist['genres'],
                    'popularity': artist['popularity'],
                    'followers': artist['followers']['total'],
                    'image_url': artist['images'][0]['url'] if artist['images'] else None,
                    'spotify_url': artist['external_urls']['spotify'],
                    'spotify_id': artist['id'],
                    'country': market,  # Based on search market
                    'bio': f"Popular {', '.join(artist['genres'][:2])} artist" if artist['genres'] else "Emerging artist",
                    'language': self._detect_language_from_artist(artist),
                    'real_time_data': True,
                    'last_updated': datetime.now().isoformat()
                }
                artists.append(artist_data)
            
            # Cache the results
            self._cache_data(cache_key, artists)
            logger.info(f"Fetched {len(artists)} real-time artist results for: {query}")
            return artists
            
        except Exception as e:
            logger.error(f"Error searching Spotify artists: {e}")
            return self._get_mock_search_results(query, limit)
    
    def get_artist_details(self, artist_id: str) -> Optional[Dict]:
        """Get detailed information about a specific artist"""
        cache_key = f"artist_details_{artist_id}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        if not self.spotify:
            return None
        
        try:
            artist = self.spotify.artist(artist_id)
            albums = self.spotify.artist_albums(artist_id, album_type='album,single', limit=10)
            top_tracks = self.spotify.artist_top_tracks(artist_id)
            
            artist_details = {
                'artist_id': artist['id'],
                'name': artist['name'],
                'genres': artist['genres'],
                'popularity': artist['popularity'],
                'followers': artist['followers']['total'],
                'image_url': artist['images'][0]['url'] if artist['images'] else None,
                'spotify_url': artist['external_urls']['spotify'],
                'albums_count': albums['total'],
                'recent_albums': [
                    {
                        'name': album['name'],
                        'release_date': album['release_date'],
                        'id': album['id']
                    } for album in albums['items'][:5]
                ],
                'top_tracks': [
                    {
                        'name': track['name'],
                        'popularity': track['popularity'],
                        'preview_url': track['preview_url'],
                        'id': track['id']
                    } for track in top_tracks['tracks'][:5]
                ],
                'language': self._detect_language_from_artist(artist),
                'real_time_data': True,
                'last_updated': datetime.now().isoformat()
            }
            
            self._cache_data(cache_key, artist_details)
            return artist_details
            
        except Exception as e:
            logger.error(f"Error getting artist details: {e}")
            return None
    
    def get_trending_artists(self, market: str = 'US', limit: int = 20) -> List[Dict]:
        """Get trending artists from featured playlists"""
        cache_key = f"trending_artists_{market}_{limit}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        if not self.spotify:
            return self._get_mock_trending_artists(limit)
        
        try:
            # Alternative approach: search for trending terms to get popular artists
            trending_terms = ['pop', 'hip hop', 'rock', 'electronic', 'indie', 'r&b']
            artist_ids = set()
            
            # Search for popular artists in each trending genre
            for term in trending_terms:
                search_results = self.spotify.search(
                    q=f'genre:"{term}"',
                    type='artist',
                    limit=5,
                    market=market
                )
                for artist in search_results['artists']['items']:
                    if artist['popularity'] >= 70:  # Only high-popularity artists
                        artist_ids.add(artist['id'])
            
            # Get details for trending artists
            trending_artists = []
            artist_ids_list = list(artist_ids)[:limit]
            
            # Batch request for artist details
            if artist_ids_list:
                artists_details = self.spotify.artists(artist_ids_list)
                for artist in artists_details['artists']:
                    artist_data = {
                        'artist_id': artist['id'],
                        'name': artist['name'],
                        'genres': artist['genres'],
                        'popularity': artist['popularity'],
                        'followers': artist['followers']['total'],
                        'image_url': artist['images'][0]['url'] if artist['images'] else None,
                        'spotify_url': artist['external_urls']['spotify'],
                        'language': self._detect_language_from_artist(artist),
                        'trending_score': artist['popularity'],  # Use popularity as trending indicator
                        'real_time_data': True,
                        'last_updated': datetime.now().isoformat()
                    }
                    trending_artists.append(artist_data)
            
            # Sort by popularity
            trending_artists.sort(key=lambda x: x['popularity'], reverse=True)
            
            self._cache_data(cache_key, trending_artists)
            return trending_artists
            
        except Exception as e:
            logger.error(f"Error getting trending artists: {e}")
            return self._get_mock_trending_artists(limit)
    
    def get_artists_by_language(self, language: str, limit: int = 20) -> List[Dict]:
        """Get artists by language/region"""
        cache_key = f"artists_language_{language}_{limit}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        # Language to market/genre mapping
        language_queries = {
            'telugu': 'telugu music',
            'hindi': 'bollywood hindi',
            'tamil': 'tamil music',
            'spanish': 'latin reggaeton',
            'korean': 'k-pop korean',
            'japanese': 'j-pop japanese',
            'portuguese': 'brazilian portuguese',
            'french': 'french chanson',
            'german': 'german pop',
            'italian': 'italian pop'
        }
        
        query = language_queries.get(language.lower(), f'{language} music')
        
        if not self.spotify:
            return self._get_mock_language_artists(language, limit)
        
        try:
            # Search for artists with language-specific query
            results = self.spotify.search(
                q=query,
                type='artist',
                limit=limit
            )
            
            artists = []
            for artist in results['artists']['items']:
                artist_data = {
                    'artist_id': artist['id'],
                    'name': artist['name'],
                    'genres': artist['genres'],
                    'popularity': artist['popularity'],
                    'followers': artist['followers']['total'],
                    'image_url': artist['images'][0]['url'] if artist['images'] else None,
                    'spotify_url': artist['external_urls']['spotify'],
                    'language': language,
                    'confidence_score': self._calculate_language_confidence(artist, language),
                    'real_time_data': True,
                    'last_updated': datetime.now().isoformat()
                }
                artists.append(artist_data)
            
            # Sort by confidence and popularity
            artists.sort(key=lambda x: (x['confidence_score'], x['popularity']), reverse=True)
            
            self._cache_data(cache_key, artists)
            return artists
            
        except Exception as e:
            logger.error(f"Error getting artists by language: {e}")
            return self._get_mock_language_artists(language, limit)
    
    def _detect_language_from_artist(self, artist: Dict) -> str:
        """Detect language based on artist genres and name"""
        genres = [g.lower() for g in artist.get('genres', [])]
        name = artist.get('name', '').lower()
        
        # Language detection based on genres
        if any(g in ['bollywood', 'indian', 'hindi'] for g in genres):
            return 'hindi'
        elif any(g in ['k-pop', 'korean'] for g in genres):
            return 'korean'
        elif any(g in ['j-pop', 'japanese'] for g in genres):
            return 'japanese'
        elif any(g in ['latin', 'reggaeton', 'spanish'] for g in genres):
            return 'spanish'
        elif any(g in ['french', 'chanson'] for g in genres):
            return 'french'
        elif any(g in ['german'] for g in genres):
            return 'german'
        elif any(g in ['brazilian', 'portuguese'] for g in genres):
            return 'portuguese'
        else:
            return 'english'  # Default
    
    def _calculate_language_confidence(self, artist: Dict, target_language: str) -> float:
        """Calculate confidence score for language matching"""
        detected_language = self._detect_language_from_artist(artist)
        base_score = 1.0 if detected_language == target_language else 0.5
        
        # Boost score based on popularity for the target language
        popularity_boost = artist.get('popularity', 0) / 100
        
        return min(base_score + popularity_boost * 0.5, 1.0)
    
    def _get_mock_search_results(self, query: str, limit: int) -> List[Dict]:
        """Return mock search results when Spotify API is not available"""
        mock_artists = [
            {
                'artist_id': f'mock_{i}',
                'name': f'Artist {i} - {query}',
                'genres': ['pop', 'rock'],
                'popularity': 50 + (i * 5),
                'followers': 10000 + (i * 1000),
                'image_url': None,
                'spotify_url': f'https://open.spotify.com/artist/mock_{i}',
                'country': 'US',
                'bio': f'Mock artist for {query}',
                'language': 'english',
                'real_time_data': False,
                'last_updated': datetime.now().isoformat()
            }
            for i in range(min(limit, 5))
        ]
        return mock_artists
    
    def _get_mock_trending_artists(self, limit: int) -> List[Dict]:
        """Return mock trending artists"""
        return [
            {
                'artist_id': f'trending_mock_{i}',
                'name': f'Trending Artist {i}',
                'genres': ['pop', 'electronic'],
                'popularity': 80 + i,
                'followers': 50000 + (i * 5000),
                'image_url': None,
                'spotify_url': f'https://open.spotify.com/artist/trending_mock_{i}',
                'language': 'english',
                'trending_score': 80 + i,
                'real_time_data': False,
                'last_updated': datetime.now().isoformat()
            }
            for i in range(min(limit, 10))
        ]
    
    def _get_mock_language_artists(self, language: str, limit: int) -> List[Dict]:
        """Return mock artists for a specific language"""
        return [
            {
                'artist_id': f'{language}_mock_{i}',
                'name': f'{language.title()} Artist {i}',
                'genres': [f'{language} pop', 'world'],
                'popularity': 60 + i,
                'followers': 20000 + (i * 2000),
                'image_url': None,
                'spotify_url': f'https://open.spotify.com/artist/{language}_mock_{i}',
                'language': language,
                'confidence_score': 0.9,
                'real_time_data': False,
                'last_updated': datetime.now().isoformat()
            }
            for i in range(min(limit, 8))
        ] 