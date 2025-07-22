import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, jsonify, send_from_directory
from google.cloud import firestore
from algoliasearch.search_client import SearchClient
from pydantic import BaseModel, Field
import openai
from dotenv import load_dotenv
from services.spotify_service import SpotifyService
from services.predictive_engine import PredictiveAnalysisEngine
import bcrypt
import jwt
from functools import wraps
from flask import session, redirect, url_for
from google.auth.transport import requests as google_requests
from google_auth_oauthlib import flow
import json
import uuid

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key_change_in_production')

# Initialize clients
db = firestore.Client()
algolia_client = SearchClient.create(
    os.getenv('ALGOLIA_APP_ID'),
    os.getenv('ALGOLIA_API_KEY')
)
search_index = algolia_client.init_index('artists')

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Pydantic models for data validation
class UserPreferences(BaseModel):
    user_id: str
    favorite_genres: List[str] = Field(default_factory=list)
    favorite_artists: List[str] = Field(default_factory=list)
    listening_history: List[str] = Field(default_factory=list)
    mood_preferences: List[str] = Field(default_factory=list)
    tempo_preferences: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ArtistRecommendation(BaseModel):
    artist_id: str
    artist_name: str
    genres: List[str]
    similarity_score: float
    reasoning: str
    recommended_tracks: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RecommendationRequest(BaseModel):
    user_id: str
    limit: int = Field(default=10, ge=1, le=50)
    include_reasoning: bool = Field(default=True)
    filters: Optional[Dict[str, Any]] = Field(default=None)

class Artist(BaseModel):
    artist_id: str
    name: str
    genres: List[str]
    popularity: int
    followers: int
    country: str
    bio: str
    image_url: str
    spotify_id: Optional[str] = None

# LLM-driven recommendation engine
class LLMRecommendationEngine:
    def __init__(self):
        self.model = "gpt-4"
        self.max_tokens = 1000
        
    def generate_recommendations(self, user_prefs: UserPreferences, 
                               available_artists: List[Dict], 
                               limit: int = 10) -> List[ArtistRecommendation]:
        """Generate personalized artist recommendations using LLM"""
        
        # Create context for the LLM
        context = self._build_context(user_prefs, available_artists)
        
        # Generate LLM prompt
        prompt = self._create_recommendation_prompt(user_prefs, context, limit)
        
        try:
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert music recommendation system. Analyze user preferences and available artists to provide personalized recommendations with detailed reasoning."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.7
            )
            
            # Parse LLM response
            recommendations = self._parse_llm_response(response.choices[0].message.content, available_artists)
            return recommendations[:limit]
            
        except Exception as e:
            logger.error(f"Error generating LLM recommendations: {e}")
            # Fallback to rule-based recommendations
            return self._fallback_recommendations(user_prefs, available_artists, limit)
    
    def _build_context(self, user_prefs: UserPreferences, artists: List[Dict]) -> str:
        """Build context string for LLM"""
        context = f"""
        User Preferences:
        - Favorite Genres: {', '.join(user_prefs.favorite_genres)}
        - Favorite Artists: {', '.join(user_prefs.favorite_artists)}
        - Mood Preferences: {', '.join(user_prefs.mood_preferences)}
        - Tempo Preferences: {', '.join(user_prefs.tempo_preferences)}
        
        Available Artists ({len(artists)} total):
        """
        
        for artist in artists[:20]:  # Limit context size
            context += f"- {artist['name']} ({', '.join(artist['genres'])}) - Popularity: {artist['popularity']}\n"
        
        return context
    
    def _create_recommendation_prompt(self, user_prefs: UserPreferences, context: str, limit: int) -> str:
        """Create the prompt for LLM recommendation generation"""
        return f"""
        {context}
        
        Based on the user preferences above, recommend exactly {limit} artists from the available list.
        
        For each recommendation, provide:
        1. Artist name (must match exactly from available list)
        2. Similarity score (0.0-1.0)
        3. Detailed reasoning for the recommendation
        
        Format your response as JSON:
        {{
            "recommendations": [
                {{
                    "artist_name": "Artist Name",
                    "similarity_score": 0.85,
                    "reasoning": "Detailed explanation of why this artist matches the user's preferences"
                }}
            ]
        }}
        
        Focus on artists that match the user's genre preferences, mood, and listening history.
        Ensure all artist names exactly match those in the available list.
        """

    def _parse_llm_response(self, response: str, available_artists: List[Dict]) -> List[ArtistRecommendation]:
        """Parse LLM response into structured recommendations"""
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            json_str = response[json_start:json_end]
            
            data = json.loads(json_str)
            recommendations = []
            
            for rec in data.get('recommendations', []):
                artist_name = rec.get('artist_name')
                # Find matching artist in available list
                matching_artist = next(
                    (a for a in available_artists if a['name'].lower() == artist_name.lower()),
                    None
                )
                
                if matching_artist:
                    recommendations.append(ArtistRecommendation(
                        artist_id=matching_artist['artist_id'],
                        artist_name=matching_artist['name'],
                        genres=matching_artist['genres'],
                        similarity_score=rec.get('similarity_score', 0.5),
                        reasoning=rec.get('reasoning', 'Recommended based on user preferences')
                    ))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return []
    
    def _fallback_recommendations(self, user_prefs: UserPreferences, 
                                available_artists: List[Dict], limit: int) -> List[ArtistRecommendation]:
        """Fallback rule-based recommendations"""
        recommendations = []
        
        # Simple genre-based matching
        for artist in available_artists:
            if any(genre in user_prefs.favorite_genres for genre in artist['genres']):
                recommendations.append(ArtistRecommendation(
                    artist_id=artist['artist_id'],
                    artist_name=artist['name'],
                    genres=artist['genres'],
                    similarity_score=0.7,
                    reasoning=f"Matches user's favorite genres: {', '.join(artist['genres'])}"
                ))
                
                if len(recommendations) >= limit:
                    break
        
        return recommendations

# Initialize recommendation engine
recommendation_engine = LLMRecommendationEngine()

# Database operations
class FirestoreManager:
    def __init__(self):
        self.db = db
    
    def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Retrieve user preferences from Firestore"""
        try:
            doc_ref = self.db.collection('user_preferences').document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return UserPreferences(**data)
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving user preferences: {e}")
            return None
    
    def save_user_preferences(self, preferences: UserPreferences) -> bool:
        """Save user preferences to Firestore"""
        try:
            doc_ref = self.db.collection('user_preferences').document(preferences.user_id)
            doc_ref.set(preferences.model_dump())
            return True
            
        except Exception as e:
            logger.error(f"Error saving user preferences: {e}")
            return False
    
    def save_recommendation_history(self, user_id: str, recommendations: List[ArtistRecommendation]) -> bool:
        """Save recommendation history to Firestore"""
        try:
            batch = self.db.batch()
            
            for rec in recommendations:
                doc_ref = self.db.collection('recommendation_history').document()
                batch.set(doc_ref, {
                    'user_id': user_id,
                    'artist_id': rec.artist_id,
                    'artist_name': rec.artist_name,
                    'similarity_score': rec.similarity_score,
                    'reasoning': rec.reasoning,
                    'created_at': rec.created_at
                })
            
            batch.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error saving recommendation history: {e}")
            return False

# Algolia search operations
class AlgoliaManager:
    def __init__(self):
        self.index = search_index
    
    def search_artists(self, query: str = "", filters: Dict = None, limit: int = 100) -> List[Dict]:
        """Search artists using Algolia with sub-100ms performance"""
        try:
            search_params = {
                'hitsPerPage': limit,
                'attributesToRetrieve': ['artist_id', 'name', 'genres', 'popularity', 'followers', 'country', 'bio', 'image_url']
            }
            
            if filters:
                search_params['filters'] = self._build_filters(filters)
            
            results = self.index.search(query, search_params)
            # Convert to dictionary for JSON serialization
            return [dict(hit) for hit in results.get('hits', [])]
            
        except Exception as e:
            logger.error(f"Error searching artists: {e}")
            return []
    
    def _build_filters(self, filters: Dict) -> str:
        """Build Algolia filter string"""
        filter_parts = []
        
        if 'genres' in filters:
            genre_filters = [f"genres:{genre}" for genre in filters['genres']]
            filter_parts.append(f"({' OR '.join(genre_filters)})")
        
        if 'min_popularity' in filters:
            filter_parts.append(f"popularity >= {filters['min_popularity']}")
        
        if 'country' in filters:
            filter_parts.append(f"country:{filters['country']}")
        
        return ' AND '.join(filter_parts)

# Initialize managers
firestore_manager = FirestoreManager()
algolia_manager = AlgoliaManager()

# Initialize new services
spotify_service = SpotifyService()
predictive_engine = PredictiveAnalysisEngine(db)

JWT_SECRET = os.getenv('JWT_SECRET', 'dev_secret')
JWT_ALGO = 'HS256'

# Google OAuth2 Configuration
GOOGLE_OAUTH2_CLIENT_ID = os.getenv('GOOGLE_OAUTH2_CLIENT_ID')
GOOGLE_OAUTH2_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH2_CLIENT_SECRET')
GOOGLE_OAUTH2_REDIRECT_URI = os.getenv('GOOGLE_OAUTH2_REDIRECT_URI', 'http://localhost:8000/api/auth/google/callback')

# OAuth2 scopes
GOOGLE_OAUTH2_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

# --- Auth Helpers ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_jwt(user_id):
    return jwt.encode({'user_id': user_id}, JWT_SECRET, algorithm=JWT_ALGO)

def decode_jwt(token):
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        try:
            payload = decode_jwt(token.split(' ')[-1])
            request.user_id = payload['user_id']
        except Exception:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

# --- Auth Endpoints ---
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    if not (email or username) or not password:
        return jsonify({'error': 'Email/username and password required'}), 400
    user_ref = db.collection('users').document(email or username)
    if user_ref.get().exists:
        return jsonify({'error': 'User already exists'}), 409
    hashed = hash_password(password)
    user_ref.set({
        'email': email,
        'username': username,
        'password': hashed,
        'created_at': datetime.now(timezone.utc).isoformat()
    })
    token = generate_jwt(email or username)
    return jsonify({'token': token, 'user_id': email or username})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    if not (email or username) or not password:
        return jsonify({'error': 'Email/username and password required'}), 400
    user_ref = db.collection('users').document(email or username)
    user_doc = user_ref.get()
    if not user_doc.exists:
        return jsonify({'error': 'User not found'}), 404
    user = user_doc.to_dict()
    if not check_password(password, user['password']):
        return jsonify({'error': 'Incorrect password'}), 401
    token = generate_jwt(email or username)
    return jsonify({'token': token, 'user_id': email or username})

# --- Google OAuth2 Implementation ---
def create_google_oauth_flow():
    """Create Google OAuth2 flow"""
    if not GOOGLE_OAUTH2_CLIENT_ID or not GOOGLE_OAUTH2_CLIENT_SECRET:
        raise ValueError("Google OAuth2 credentials not configured")
    
    # Create flow instance
    oauth_flow = flow.Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_OAUTH2_CLIENT_ID,
                "client_secret": GOOGLE_OAUTH2_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_OAUTH2_REDIRECT_URI]
            }
        },
        scopes=GOOGLE_OAUTH2_SCOPES
    )
    oauth_flow.redirect_uri = GOOGLE_OAUTH2_REDIRECT_URI
    return oauth_flow

@app.route('/api/auth/google', methods=['GET'])
def google_auth():
    """Initialize Google OAuth2 authentication"""
    try:
        oauth_flow = create_google_oauth_flow()
        
        # Generate state parameter for CSRF protection
        state = str(uuid.uuid4())
        session['oauth_state'] = state
        
        # Get authorization URL
        authorization_url, _ = oauth_flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state
        )
        
        return jsonify({
            'authorization_url': authorization_url,
            'state': state
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Error initiating Google OAuth2: {e}")
        return jsonify({'error': 'OAuth2 initialization failed'}), 500

@app.route('/api/auth/google/callback', methods=['GET'])
def google_auth_callback():
    """Handle Google OAuth2 callback"""
    try:
        # Verify state parameter for CSRF protection
        state = request.args.get('state')
        if not state or state != session.get('oauth_state'):
            return jsonify({'error': 'Invalid state parameter'}), 400
        
        # Check for authorization code
        authorization_code = request.args.get('code')
        if not authorization_code:
            error = request.args.get('error')
            return jsonify({'error': f'Authorization failed: {error}'}), 400
        
        # Exchange authorization code for tokens
        oauth_flow = create_google_oauth_flow()
        oauth_flow.fetch_token(authorization_response=request.url)
        
        # Get user info from Google
        credentials = oauth_flow.credentials
        request_session = google_requests.Request()
        
        # Verify the token and get user info
        user_info_response = request_session(
            'GET',
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {credentials.token}'}
        )
        
        if user_info_response.status != 200:
            return jsonify({'error': 'Failed to get user info from Google'}), 400
        
        user_info = json.loads(user_info_response.data.decode('utf-8'))
        
        # Extract user data
        google_id = user_info.get('id')
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')
        
        if not google_id or not email:
            return jsonify({'error': 'Invalid user data from Google'}), 400
        
        # Check if user already exists
        user_id = f"google_{google_id}"
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            # Create new user
            user_data = {
                'google_id': google_id,
                'email': email,
                'name': name,
                'picture': picture,
                'provider': 'google',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_login': datetime.now(timezone.utc).isoformat()
            }
            user_ref.set(user_data)
        else:
            # Update last login
            user_ref.update({
                'last_login': datetime.now(timezone.utc).isoformat(),
                'name': name,
                'picture': picture
            })
        
        # Generate JWT token
        token = generate_jwt(user_id)
        
        # Clear session state
        session.pop('oauth_state', None)
        
        return jsonify({
            'token': token,
            'user_id': user_id,
            'email': email,
            'name': name,
            'picture': picture,
            'provider': 'google'
        })
        
    except Exception as e:
        logger.error(f"Error in Google OAuth2 callback: {e}")
        return jsonify({'error': 'OAuth2 callback failed'}), 500

# API Routes
@app.route('/', methods=['GET'])
def root():
    """Serve the frontend application"""
    return send_from_directory('static', 'index.html')

@app.route('/api', methods=['GET'])
def api_info():
    """API information endpoint"""
    return jsonify({
        'service': 'LLM-Driven Artist Recommendation Engine',
        'version': '1.0.0',
        'endpoints': {
            'health': '/health',
            'recommendations': '/api/v1/recommendations',
            'preferences': '/api/v1/preferences',
            'artist_search': '/api/v1/artists/search',
            'get_artist': '/api/v1/artists/<artist_id>'
        },
        'status': 'running'
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'service': 'LLM Artist Recommendation Engine'
    })

@app.route('/api/v1/recommendations', methods=['POST'])
@login_required
def get_recommendations():
    """Generate personalized artist recommendations"""
    try:
        # Validate request
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'No request data provided'}), 400
        
        # Use authenticated user_id from JWT token
        request_data['user_id'] = request.user_id
        rec_request = RecommendationRequest(**request_data)
        
        # Get user preferences
        user_prefs = firestore_manager.get_user_preferences(rec_request.user_id)
        if not user_prefs:
            return jsonify({'error': 'User preferences not found'}), 404
        
        # Search for available artists
        search_filters = rec_request.filters or {}
        available_artists = algolia_manager.search_artists(
            filters=search_filters,
            limit=100
        )
        
        if not available_artists:
            return jsonify({'error': 'No artists found matching criteria'}), 404
        
        # Generate recommendations using LLM
        recommendations = recommendation_engine.generate_recommendations(
            user_prefs=user_prefs,
            available_artists=available_artists,
            limit=rec_request.limit
        )
        
        # Save recommendation history
        firestore_manager.save_recommendation_history(rec_request.user_id, recommendations)
        
        # Prepare response
        response_data = {
            'user_id': rec_request.user_id,
            'recommendations': [
                {
                    'artist_id': rec.artist_id,
                    'artist_name': rec.artist_name,
                    'genres': rec.genres,
                    'similarity_score': rec.similarity_score,
                    'reasoning': rec.reasoning if rec_request.include_reasoning else None,
                    'recommended_tracks': rec.recommended_tracks
                }
                for rec in recommendations
            ],
            'total_count': len(recommendations),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/preferences', methods=['GET', 'POST', 'PUT'])
@login_required
def manage_preferences():
    """Manage user preferences"""
    try:
        if request.method == 'GET':
            # Use authenticated user_id from JWT token
            user_id = request.user_id
            
            preferences = firestore_manager.get_user_preferences(user_id)
            if not preferences:
                return jsonify({'error': 'User preferences not found'}), 404
            
            return jsonify(preferences.dict()), 200
        
        elif request.method in ['POST', 'PUT']:
            request_data = request.get_json()
            if not request_data:
                return jsonify({'error': 'No request data provided'}), 400
            
            # Use authenticated user_id from JWT token
            request_data['user_id'] = request.user_id
            preferences = UserPreferences(**request_data)
            success = firestore_manager.save_user_preferences(preferences)
            
            if success:
                return jsonify({'message': 'Preferences saved successfully'}), 200
            else:
                return jsonify({'error': 'Failed to save preferences'}), 500
    
    except Exception as e:
        logger.error(f"Error managing preferences: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/artists/search', methods=['GET'])
def search_artists():
    """Search artists using real-time Spotify API and Algolia fallback"""
    try:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 20))
        language = request.args.get('language', '')
        market = request.args.get('market', 'US')
        use_realtime = request.args.get('realtime', 'true').lower() == 'true'
        
        artists = []
        
        # Track search interaction if user is authenticated
        auth_token = request.headers.get('Authorization')
        user_id = None
        if auth_token:
            try:
                token = auth_token.split(' ')[-1]
                payload = decode_jwt(token)
                user_id = payload['user_id']
                
                # Track search behavior
                predictive_engine.behavior_tracker.track_interaction(
                    user_id,
                    'search',
                    {
                        'query': query,
                        'language': language,
                        'market': market,
                        'session_id': request.headers.get('X-Session-ID', 'unknown')
                    }
                )
            except:
                pass  # Continue without tracking if auth fails
        
        if use_realtime and query:
            # Use Spotify API for real-time data
            if language:
                artists = spotify_service.get_artists_by_language(language, limit)
            else:
                artists = spotify_service.search_artists(query, limit, market)
        
        # Fallback to Algolia if no results or realtime disabled
        if not artists:
            # Parse filters from query parameters
            filters = {}
            if request.args.get('genres'):
                filters['genres'] = request.args.get('genres').split(',')
            if request.args.get('min_popularity'):
                filters['min_popularity'] = int(request.args.get('min_popularity'))
            if request.args.get('country'):
                filters['country'] = request.args.get('country')
            
            artists = algolia_manager.search_artists(query=query, filters=filters, limit=limit)
        
        # Track artist views for authenticated users
        if user_id and artists:
            for artist in artists[:3]:  # Track first 3 results
                predictive_engine.behavior_tracker.track_interaction(
                    user_id,
                    'artist_view',
                    {
                        'artist_name': artist.get('name', ''),
                        'artist_id': artist.get('artist_id', ''),
                        'genres': artist.get('genres', []),
                        'language': artist.get('language', 'english'),
                        'popularity': artist.get('popularity', 0),
                        'session_id': request.headers.get('X-Session-ID', 'unknown')
                    }
                )
        
        return jsonify({
            'artists': artists,
            'total_count': len(artists),
            'query': query,
            'language': language,
            'real_time_data': use_realtime and bool(artists and artists[0].get('real_time_data'))
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching artists: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/artists/<artist_id>', methods=['GET'])
def get_artist(artist_id):
    """Get specific artist details"""
    try:
        # Search for artist by ID
        results = algolia_manager.search_artists(
            filters={'artist_id': artist_id},
            limit=1
        )
        
        if not results:
            return jsonify({'error': 'Artist not found'}), 404
        
        return jsonify(results[0]), 200
        
    except Exception as e:
        logger.error(f"Error retrieving artist: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/artists/trending', methods=['GET'])
def get_trending_artists():
    """Get trending artists from real-time data"""
    try:
        market = request.args.get('market', 'US')
        limit = int(request.args.get('limit', 20))
        
        trending_artists = spotify_service.get_trending_artists(market, limit)
        
        return jsonify({
            'artists': trending_artists,
            'total_count': len(trending_artists),
            'market': market,
            'real_time_data': True
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting trending artists: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/artists/by-language/<language>', methods=['GET'])
def get_artists_by_language(language):
    """Get artists by specific language"""
    try:
        limit = int(request.args.get('limit', 20))
        
        artists = spotify_service.get_artists_by_language(language, limit)
        
        return jsonify({
            'artists': artists,
            'total_count': len(artists),
            'language': language,
            'real_time_data': True
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting artists by language: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/predictions/user-preferences', methods=['GET'])
@login_required
def get_user_predictions():
    """Get predictive analysis for user preferences"""
    try:
        user_id = request.user_id
        
        predictions = predictive_engine.predict_user_preferences(user_id)
        
        return jsonify({
            'user_id': user_id,
            'predictions': predictions,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user predictions: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/recommendations/hybrid', methods=['POST'])
@login_required
def get_hybrid_recommendations():
    """Get hybrid recommendations using predictive analysis"""
    try:
        user_id = request.user_id
        request_data = request.get_json() or {}
        
        limit = request_data.get('limit', 10)
        include_trending = request_data.get('include_trending', True)
        language_filter = request_data.get('language', '')
        
        # Get available artists from multiple sources
        available_artists = []
        
        # Get some trending artists
        if include_trending:
            trending = spotify_service.get_trending_artists('US', 30)
            available_artists.extend(trending)
        
        # Get language-specific artists if requested
        if language_filter:
            language_artists = spotify_service.get_artists_by_language(language_filter, 20)
            available_artists.extend(language_artists)
        
        # Get some artists from Algolia as well
        algolia_artists = algolia_manager.search_artists(limit=50)
        available_artists.extend(algolia_artists)
        
        # Remove duplicates
        seen_artists = set()
        unique_artists = []
        for artist in available_artists:
            artist_id = artist.get('artist_id', '')
            if artist_id and artist_id not in seen_artists:
                seen_artists.add(artist_id)
                unique_artists.append(artist)
        
        # Filter artists by language if specified
        if language_filter and language_filter.lower() != 'all':
            filtered_artists = []
            for artist in unique_artists:
                artist_language = artist.get('language', 'english').lower()
                if language_filter.lower() in artist_language or artist_language in language_filter.lower():
                    filtered_artists.append(artist)
            unique_artists = filtered_artists
        
        # Get hybrid recommendations
        recommendations = predictive_engine.get_hybrid_recommendations(
            user_id, 
            unique_artists, 
            limit
        )
        
        # Track recommendation generation
        predictive_engine.behavior_tracker.track_interaction(
            user_id,
            'recommendations_generated',
            {
                'method': 'hybrid',
                'total_available': len(unique_artists),
                'recommendations_count': len(recommendations),
                'language_filter': language_filter,
                'session_id': request.headers.get('X-Session-ID', 'unknown')
            }
        )
        
        return jsonify({
            'user_id': user_id,
            'recommendations': recommendations,
            'method': 'hybrid_predictive',
            'total_analyzed': len(unique_artists),
            'generated_at': datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting hybrid recommendations: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/feedback/recommendation', methods=['POST'])
@login_required
def track_recommendation_feedback():
    """Track user feedback on recommendations"""
    try:
        user_id = request.user_id
        request_data = request.get_json()
        
        if not request_data:
            return jsonify({'error': 'No request data provided'}), 400
        
        recommendation_id = request_data.get('recommendation_id', '')
        feedback = request_data.get('feedback', '')  # 'like', 'dislike', 'save', 'skip'
        artist_data = request_data.get('artist_data', {})
        
        if not feedback or not artist_data:
            return jsonify({'error': 'Missing feedback or artist data'}), 400
        
        # Track the feedback
        predictive_engine.track_recommendation_feedback(
            user_id,
            recommendation_id,
            feedback,
            artist_data
        )
        
        return jsonify({
            'message': 'Feedback tracked successfully',
            'user_id': user_id,
            'feedback': feedback
        }), 200
        
    except Exception as e:
        logger.error(f"Error tracking recommendation feedback: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/analytics/user-behavior', methods=['GET'])
@login_required
def get_user_behavior_analytics():
    """Get user behavior analytics and insights"""
    try:
        user_id = request.user_id
        days = int(request.args.get('days', 30))
        
        behavior_patterns = predictive_engine.behavior_tracker.get_user_behavior_patterns(user_id, days)
        predictions = predictive_engine.predict_user_preferences(user_id)
        
        analytics = {
            'user_id': user_id,
            'period_days': days,
            'behavior_patterns': behavior_patterns,
            'predictions': predictions,
            'insights': []
        }
        
        # Generate insights
        if behavior_patterns:
            total_interactions = behavior_patterns.get('total_interactions', 0)
            discovery_rate = behavior_patterns.get('discovery_rate', 0)
            
            if total_interactions > 0:
                analytics['insights'].append(f"You've had {total_interactions} interactions in the last {days} days")
            
            if discovery_rate > 0.3:
                analytics['insights'].append("You have a high discovery rate - you're great at finding new music!")
            elif discovery_rate > 0.1:
                analytics['insights'].append("You occasionally discover new music - try our recommendations!")
            else:
                analytics['insights'].append("You stick to familiar music - we can help you discover new artists!")
            
            # Genre insights
            genre_prefs = behavior_patterns.get('genre_preferences', {})
            if genre_prefs:
                top_genre = max(genre_prefs.items(), key=lambda x: x[1])
                analytics['insights'].append(f"Your most explored genre is {top_genre[0]}")
        
        return jsonify(analytics), 200
        
    except Exception as e:
        logger.error(f"Error getting user behavior analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # For local development
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
else:
    # For Cloud Run
    app.debug = False 