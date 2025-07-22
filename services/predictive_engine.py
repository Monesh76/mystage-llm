import os
import logging
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import NMF
from sklearn.preprocessing import StandardScaler
import joblib

logger = logging.getLogger(__name__)

class UserBehaviorTracker:
    """Track and analyze user behavior patterns"""
    
    def __init__(self, db):
        self.db = db
    
    def track_interaction(self, user_id: str, action: str, data: Dict) -> None:
        """Track user interaction"""
        try:
            interaction_data = {
                'user_id': user_id,
                'action': action,
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'session_id': data.get('session_id', 'unknown')
            }
            
            self.db.collection('user_interactions').add(interaction_data)
            logger.info(f"Tracked interaction: {action} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error tracking interaction: {e}")
    
    def get_user_behavior_patterns(self, user_id: str, days: int = 30) -> Dict:
        """Analyze user behavior patterns"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Simplified query to avoid index requirements
            # Just get recent interactions without timestamp ordering
            interactions = self.db.collection('user_interactions').where(
                'user_id', '==', user_id
            ).limit(100).stream()
            
            behavior_data = {
                'search_patterns': defaultdict(int),
                'genre_preferences': defaultdict(int),
                'language_preferences': defaultdict(int),
                'listening_times': [],
                'session_durations': [],
                'most_played_artists': defaultdict(int),
                'discovery_rate': 0,
                'total_interactions': 0
            }
            
            session_starts = {}
            
            for interaction in interactions:
                data = interaction.to_dict()
                try:
                    timestamp = datetime.fromisoformat(data.get('timestamp', ''))
                    # Filter by date client-side  
                    if timestamp < start_date:
                        continue
                except:
                    # If timestamp parsing fails, include the interaction
                    timestamp = datetime.now()
                    
                behavior_data['total_interactions'] += 1
                
                action = data.get('action', '')
                interaction_data = data.get('data', {})
                session_id = data.get('session_id', 'unknown')
                
                # Track session duration
                if session_id not in session_starts:
                    session_starts[session_id] = timestamp
                
                # Analyze different interaction types
                if action == 'search':
                    query = interaction_data.get('query', '').lower()
                    behavior_data['search_patterns'][query] += 1
                
                elif action == 'artist_view':
                    artist_name = interaction_data.get('artist_name', '')
                    genres = interaction_data.get('genres', [])
                    language = interaction_data.get('language', 'english')
                    
                    behavior_data['most_played_artists'][artist_name] += 1
                    behavior_data['language_preferences'][language] += 1
                    
                    for genre in genres:
                        behavior_data['genre_preferences'][genre] += 1
                
                elif action == 'recommendation_click':
                    behavior_data['discovery_rate'] += 1
                
                # Track listening times
                hour = timestamp.hour
                behavior_data['listening_times'].append(hour)
            
            # Calculate session durations
            for session_id, start_time in session_starts.items():
                # Find last interaction in session
                last_interaction = start_time
                for interaction in interactions:
                    data = interaction.to_dict()
                    if data.get('session_id') == session_id:
                        interaction_time = datetime.fromisoformat(data.get('timestamp', ''))
                        if interaction_time > last_interaction:
                            last_interaction = interaction_time
                
                duration = (last_interaction - start_time).total_seconds() / 60  # minutes
                behavior_data['session_durations'].append(duration)
            
            # Calculate discovery rate
            if behavior_data['total_interactions'] > 0:
                behavior_data['discovery_rate'] = behavior_data['discovery_rate'] / behavior_data['total_interactions']
            
            return dict(behavior_data)
            
        except Exception as e:
            logger.error(f"Error analyzing user behavior: {e}")
            return {}

class CollaborativeFilteringEngine:
    """Advanced collaborative filtering with matrix factorization"""
    
    def __init__(self, db):
        self.db = db
        self.user_item_matrix = None
        self.user_factors = None
        self.item_factors = None
        self.scaler = StandardScaler()
        self.model = None
    
    def build_user_item_matrix(self, min_interactions: int = 5) -> pd.DataFrame:
        """Build user-item interaction matrix from user data"""
        try:
            # Get user preferences and interactions
            users_ref = self.db.collection('user_preferences').stream()
            interactions_ref = self.db.collection('user_interactions').stream()
            
            # Build interaction matrix
            user_artist_scores = defaultdict(lambda: defaultdict(float))
            
            # From preferences (explicit ratings)
            for user_doc in users_ref:
                user_data = user_doc.to_dict()
                user_id = user_data.get('user_id', user_doc.id)
                
                favorite_artists = user_data.get('favorite_artists', [])
                favorite_genres = user_data.get('favorite_genres', [])
                
                # Give high scores to favorite artists
                for artist in favorite_artists:
                    user_artist_scores[user_id][artist] = 5.0
                
                # Give medium scores to artists in favorite genres
                for genre in favorite_genres:
                    # This would need to be mapped to actual artists
                    user_artist_scores[user_id][f'genre_{genre}'] = 3.0
            
            # From interactions (implicit ratings)
            for interaction_doc in interactions_ref:
                interaction_data = interaction_doc.to_dict()
                user_id = interaction_data.get('user_id', '')
                action = interaction_data.get('action', '')
                data = interaction_data.get('data', {})
                
                if action == 'artist_view':
                    artist_name = data.get('artist_name', '')
                    if artist_name:
                        user_artist_scores[user_id][artist_name] += 0.5
                
                elif action == 'recommendation_click':
                    artist_name = data.get('artist_name', '')
                    if artist_name:
                        user_artist_scores[user_id][artist_name] += 1.0
                
                elif action == 'search':
                    query = data.get('query', '')
                    if query:
                        user_artist_scores[user_id][f'search_{query}'] += 0.2
            
            # Convert to DataFrame
            if not user_artist_scores:
                return pd.DataFrame()
            
            # Create matrix
            all_users = list(user_artist_scores.keys())
            all_items = set()
            for user_items in user_artist_scores.values():
                all_items.update(user_items.keys())
            all_items = list(all_items)
            
            matrix_data = []
            for user in all_users:
                row = []
                for item in all_items:
                    row.append(user_artist_scores[user].get(item, 0.0))
                matrix_data.append(row)
            
            self.user_item_matrix = pd.DataFrame(
                matrix_data,
                index=all_users,
                columns=all_items
            )
            
            # Filter users and items with minimum interactions
            user_counts = (self.user_item_matrix > 0).sum(axis=1)
            item_counts = (self.user_item_matrix > 0).sum(axis=0)
            
            active_users = user_counts[user_counts >= min_interactions].index
            popular_items = item_counts[item_counts >= min_interactions].index
            
            self.user_item_matrix = self.user_item_matrix.loc[active_users, popular_items]
            
            logger.info(f"Built user-item matrix: {self.user_item_matrix.shape}")
            return self.user_item_matrix
            
        except Exception as e:
            logger.error(f"Error building user-item matrix: {e}")
            return pd.DataFrame()
    
    def train_matrix_factorization(self, n_components: int = 20, random_state: int = 42) -> None:
        """Train matrix factorization model"""
        try:
            if self.user_item_matrix is None or self.user_item_matrix.empty:
                self.build_user_item_matrix()
            
            if self.user_item_matrix.empty:
                logger.warning("No data available for matrix factorization")
                return
            
            # Prepare data for NMF (ensure non-negative values)
            matrix_data = self.user_item_matrix.fillna(0)
            matrix_data = matrix_data.abs()  # Ensure non-negative values
            
            # Train NMF model
            self.model = NMF(
                n_components=min(n_components, min(matrix_data.shape) - 1),  # Ensure valid component count
                random_state=random_state,
                max_iter=500,
                alpha_W=0.1,
                alpha_H=0.1,
                init='random'
            )
            
            self.user_factors = self.model.fit_transform(matrix_data)
            self.item_factors = self.model.components_
            
            logger.info(f"Trained matrix factorization model with {n_components} components")
            
        except Exception as e:
            logger.error(f"Error training matrix factorization: {e}")
    
    def get_collaborative_recommendations(self, user_id: str, n_recommendations: int = 10) -> List[Dict]:
        """Get recommendations using collaborative filtering"""
        try:
            if self.model is None or self.user_item_matrix is None:
                self.train_matrix_factorization()
            
            if (self.model is None or self.user_factors is None or 
                self.item_factors is None or user_id not in self.user_item_matrix.index):
                return []
            
            # Get user index
            user_idx = self.user_item_matrix.index.get_loc(user_id)
            
            # Check if user index is valid
            if user_idx >= len(self.user_factors):
                return []
            
            # Predict scores for all items
            user_vector = self.user_factors[user_idx].reshape(1, -1)
            predicted_scores = np.dot(user_vector, self.item_factors).flatten()
            
            # Get items user hasn't interacted with
            user_items = self.user_item_matrix.loc[user_id]
            unrated_items = user_items[user_items == 0].index
            
            # Get recommendations
            recommendations = []
            for item_idx, item in enumerate(self.user_item_matrix.columns):
                if item in unrated_items:
                    score = predicted_scores[item_idx]
                    recommendations.append({
                        'item': item,
                        'predicted_score': float(score),
                        'type': 'collaborative_filtering'
                    })
            
            # Sort by predicted score
            recommendations.sort(key=lambda x: x['predicted_score'], reverse=True)
            
            return recommendations[:n_recommendations]
            
        except Exception as e:
            logger.error(f"Error getting collaborative recommendations: {e}")
            return []

class ContentBasedEngine:
    """Content-based recommendation engine"""
    
    def __init__(self):
        self.artist_features = None
        self.feature_matrix = None
        self.similarity_matrix = None
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
    
    def build_content_features(self, artists_data: List[Dict]) -> None:
        """Build content features for artists"""
        try:
            if not artists_data:
                return
            
            # Create feature strings for each artist
            artist_features = []
            artist_ids = []
            
            for artist in artists_data:
                # Combine textual features
                features = []
                
                # Add genres
                genres = artist.get('genres', [])
                features.extend(genres)
                
                # Add language
                language = artist.get('language', 'english')
                features.append(f"language_{language}")
                
                # Add popularity tier
                popularity = artist.get('popularity', 0)
                if popularity >= 80:
                    features.append('tier_popular')
                elif popularity >= 60:
                    features.append('tier_mainstream')
                elif popularity >= 40:
                    features.append('tier_emerging')
                else:
                    features.append('tier_niche')
                
                # Add follower tier
                followers = artist.get('followers', 0)
                if followers >= 1000000:
                    features.append('followers_massive')
                elif followers >= 100000:
                    features.append('followers_large')
                elif followers >= 10000:
                    features.append('followers_medium')
                else:
                    features.append('followers_small')
                
                feature_string = ' '.join(features)
                artist_features.append(feature_string)
                artist_ids.append(artist.get('artist_id', ''))
            
            # Create TF-IDF matrix
            self.feature_matrix = self.vectorizer.fit_transform(artist_features)
            
            # Calculate similarity matrix
            self.similarity_matrix = cosine_similarity(self.feature_matrix)
            
            self.artist_features = {
                'artist_ids': artist_ids,
                'features': artist_features
            }
            
            logger.info(f"Built content features for {len(artist_ids)} artists")
            
        except Exception as e:
            logger.error(f"Error building content features: {e}")
    
    def get_content_recommendations(self, liked_artists: List[str], n_recommendations: int = 10) -> List[Dict]:
        """Get content-based recommendations"""
        try:
            if self.similarity_matrix is None or not self.artist_features:
                return []
            
            artist_ids = self.artist_features['artist_ids']
            
            # Find indices of liked artists
            liked_indices = []
            for artist in liked_artists:
                if artist in artist_ids:
                    liked_indices.append(artist_ids.index(artist))
            
            if not liked_indices:
                return []
            
            # Calculate average similarity scores
            avg_similarities = np.mean(self.similarity_matrix[liked_indices], axis=0)
            
            # Get recommendations
            recommendations = []
            for i, similarity in enumerate(avg_similarities):
                artist_id = artist_ids[i]
                if artist_id not in liked_artists:  # Don't recommend already liked artists
                    recommendations.append({
                        'artist_id': artist_id,
                        'similarity_score': float(similarity),
                        'type': 'content_based'
                    })
            
            # Sort by similarity score
            recommendations.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return recommendations[:n_recommendations]
            
        except Exception as e:
            logger.error(f"Error getting content recommendations: {e}")
            return []

class PredictiveAnalysisEngine:
    """Main predictive analysis engine combining multiple approaches"""
    
    def __init__(self, db):
        self.db = db
        self.behavior_tracker = UserBehaviorTracker(db)
        self.collaborative_engine = CollaborativeFilteringEngine(db)
        self.content_engine = ContentBasedEngine()
    
    def predict_user_preferences(self, user_id: str) -> Dict:
        """Predict what genres/artists user might like"""
        try:
            # Get user behavior patterns
            behavior = self.behavior_tracker.get_user_behavior_patterns(user_id)
            
            # Get current preferences
            user_ref = self.db.collection('user_preferences').document(user_id)
            user_doc = user_ref.get()
            current_prefs = user_doc.to_dict() if user_doc.exists else {}
            
            predictions = {
                'predicted_genres': [],
                'predicted_artists': [],
                'predicted_languages': [],
                'confidence_scores': {},
                'reasoning': []
            }
            
            # Analyze behavior patterns
            if behavior:
                # Predict genres based on search patterns
                search_patterns = behavior.get('search_patterns', {})
                genre_preferences = behavior.get('genre_preferences', {})
                language_preferences = behavior.get('language_preferences', {})
                
                # Extract potential new interests from search patterns
                common_genres = ['pop', 'rock', 'hip hop', 'electronic', 'jazz', 'classical', 'country', 
                               'r&b', 'indie', 'alternative', 'folk', 'metal', 'blues', 'reggae', 'latin']
                
                for search_term, frequency in search_patterns.items():
                    if frequency >= 2:  # Lowered threshold
                        # Check if search term contains genre keywords
                        search_lower = search_term.lower()
                        for genre in common_genres:
                            if genre in search_lower and genre not in [g['genre'] for g in predictions['predicted_genres']]:
                                current_genres = current_prefs.get('favorite_genres', [])
                                if genre not in current_genres:
                                    confidence = min(frequency / 5, 0.8)
                                    predictions['predicted_genres'].append({
                                        'genre': genre,
                                        'confidence': confidence,
                                        'reason': f'Based on search patterns for {search_term}'
                                    })
                                break
                
                # Add some default predictions if none found
                if not predictions['predicted_genres'] and genre_preferences:
                    # Use existing genre preferences to suggest similar ones
                    for genre, count in list(genre_preferences.items())[:3]:
                        if genre in common_genres:
                            confidence = min(count / 10, 0.7)
                            predictions['predicted_genres'].append({
                                'genre': genre,
                                'confidence': confidence,
                                'reason': f'Based on your interaction with {genre} music'
                            })
                
                # Predict languages based on behavior
                for language, frequency in language_preferences.items():
                    if frequency >= 2:
                        confidence = min(frequency / 5, 0.8)
                        predictions['predicted_languages'].append({
                            'language': language,
                            'confidence': confidence,
                            'reason': f'Viewed {frequency} {language} artists'
                        })
                
                # Add behavioral insights
                total_interactions = behavior.get('total_interactions', 0)
                discovery_rate = behavior.get('discovery_rate', 0)
                
                if discovery_rate > 0.3:
                    predictions['reasoning'].append("User shows high discovery rate - likely to try new genres")
                
                if total_interactions > 50:
                    predictions['reasoning'].append("User is highly active - provide diverse recommendations")
            
            # Add fallback predictions if none found
            if not predictions['predicted_genres']:
                # Get user's current preferences as fallback
                current_genres = current_prefs.get('favorite_genres', [])
                if current_genres:
                    for genre in current_genres[:2]:  # Top 2 genres
                        predictions['predicted_genres'].append({
                            'genre': genre,
                            'confidence': 0.6,
                            'reason': 'Based on your current preferences'
                        })
                else:
                    # Ultimate fallback - popular genres
                    fallback_genres = ['pop', 'rock', 'electronic']
                    for genre in fallback_genres:
                        predictions['predicted_genres'].append({
                            'genre': genre,
                            'confidence': 0.4,
                            'reason': 'Popular genre suggestion'
                        })
            
            # Get collaborative filtering predictions
            collab_recs = self.collaborative_engine.get_collaborative_recommendations(user_id, 5)
            for rec in collab_recs:
                if rec['predicted_score'] > 0.5:
                    predictions['predicted_artists'].append({
                        'artist': rec['item'],
                        'confidence': rec['predicted_score'],
                        'reason': 'Similar users also liked this artist'
                    })
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error predicting user preferences: {e}")
            return {}
    
    def get_hybrid_recommendations(self, user_id: str, available_artists: List[Dict], 
                                 n_recommendations: int = 10, language_filter: str = None) -> List[Dict]:
        """Get hybrid recommendations combining multiple approaches"""
        try:
            # Build content features if not already done
            if self.content_engine.similarity_matrix is None:
                self.content_engine.build_content_features(available_artists)
            
            # Get user preferences
            user_ref = self.db.collection('user_preferences').document(user_id)
            user_doc = user_ref.get()
            user_prefs = user_doc.to_dict() if user_doc.exists else {}
            
            liked_artists = user_prefs.get('favorite_artists', [])
            favorite_genres = user_prefs.get('favorite_genres', [])
            
            # Get content-based recommendations
            content_recs = self.content_engine.get_content_recommendations(liked_artists, n_recommendations)
            
            # Get collaborative filtering recommendations
            collab_recs = self.collaborative_engine.get_collaborative_recommendations(user_id, n_recommendations)
            
            # Get behavior-based predictions
            predictions = self.predict_user_preferences(user_id)
            
            # Combine recommendations with hybrid scoring
            hybrid_scores = defaultdict(float)
            reasoning = defaultdict(list)
            
            # Score content-based recommendations
            for rec in content_recs:
                artist_id = rec['artist_id']
                score = rec['similarity_score'] * 0.4  # 40% weight
                hybrid_scores[artist_id] += score
                reasoning[artist_id].append(f"Content similarity: {score:.2f}")
            
            # Score collaborative filtering recommendations
            for rec in collab_recs:
                item = rec['item']
                if item.startswith('genre_') or item.startswith('search_'):
                    continue  # Skip non-artist items
                
                score = rec['predicted_score'] * 0.3  # 30% weight
                hybrid_scores[item] += score
                reasoning[item].append(f"User similarity: {score:.2f}")
            
            # Boost scores based on predictions
            predicted_genres = [p['genre'] for p in predictions.get('predicted_genres', [])]
            predicted_languages = [p['language'] for p in predictions.get('predicted_languages', [])]
            
            for artist in available_artists:
                artist_id = artist.get('artist_id', '')
                artist_genres = artist.get('genres', [])
                artist_language = artist.get('language', 'english')
                
                # Boost for predicted genres
                genre_boost = 0
                for genre in artist_genres:
                    if genre in predicted_genres:
                        genre_boost += 0.2
                
                # Boost for predicted languages
                language_boost = 0
                if artist_language in predicted_languages:
                    language_boost += 0.1
                
                total_boost = genre_boost + language_boost
                if total_boost > 0:
                    hybrid_scores[artist_id] += total_boost
                    reasoning[artist_id].append(f"Prediction boost: {total_boost:.2f}")
            
            # Create final recommendations
            recommendations = []
            for artist in available_artists:
                artist_id = artist.get('artist_id', '')
                if artist_id in hybrid_scores and artist.get('name', '') not in liked_artists:
                    rec = {
                        'artist_id': artist_id,
                        'artist_name': artist.get('name', ''),
                        'genres': artist.get('genres', []),
                        'similarity_score': hybrid_scores[artist_id],
                        'reasoning': '; '.join(reasoning[artist_id]),
                        'recommended_tracks': [],  # Could be populated from Spotify API
                        'prediction_type': 'hybrid',
                        'confidence': min(hybrid_scores[artist_id], 1.0)
                    }
                    recommendations.append(rec)
            
            # Sort by score
            recommendations.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return recommendations[:n_recommendations]
            
        except Exception as e:
            logger.error(f"Error getting hybrid recommendations: {e}")
            return []
    
    def track_recommendation_feedback(self, user_id: str, recommendation_id: str, 
                                    feedback: str, artist_data: Dict) -> None:
        """Track user feedback on recommendations for model improvement"""
        try:
            feedback_data = {
                'user_id': user_id,
                'recommendation_id': recommendation_id,
                'feedback': feedback,  # 'like', 'dislike', 'save', 'skip'
                'artist_data': artist_data,
                'timestamp': datetime.now().isoformat()
            }
            
            self.db.collection('recommendation_feedback').add(feedback_data)
            
            # Track as user interaction
            self.behavior_tracker.track_interaction(
                user_id,
                'recommendation_feedback',
                {
                    'feedback': feedback,
                    'artist_name': artist_data.get('name', ''),
                    'genres': artist_data.get('genres', []),
                    'language': artist_data.get('language', 'english')
                }
            )
            
            logger.info(f"Tracked recommendation feedback: {feedback} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error tracking recommendation feedback: {e}") 