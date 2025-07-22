import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List

from google.cloud import firestore
from google.cloud import pubsub_v1
from google.cloud import monitoring_v3
from google.cloud import logging as cloud_logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
db = firestore.Client()
publisher = pubsub_v1.PublisherClient()
monitoring_client = monitoring_v3.MetricServiceClient()
cloud_logger = cloud_logging.Client()

# Configuration
RECOMMENDATION_SERVICE_URL = os.getenv('RECOMMENDATION_SERVICE_URL')
TOPIC_NAME = os.getenv('PUBSUB_TOPIC_NAME', 'artist-recommendations')
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')

class APIMonitoring:
    """Monitor API performance and health"""
    
    def __init__(self):
        self.monitoring_client = monitoring_client
        self.project_name = f"projects/{PROJECT_ID}"
    
    def record_api_call(self, endpoint: str, response_time: float, status_code: int):
        """Record API call metrics"""
        try:
            # Create time series for response time
            time_series = monitoring_v3.TimeSeries()
            time_series.metric.type = f"custom.googleapis.com/api/response_time"
            time_series.metric.labels["endpoint"] = endpoint
            
            time_series.resource.type = "global"
            time_series.resource.labels["project_id"] = PROJECT_ID
            
            # Add data point
            point = monitoring_v3.Point()
            point.value.double_value = response_time
            point.interval.end_time.seconds = int(datetime.utcnow().timestamp())
            time_series.points = [point]
            
            self.monitoring_client.create_time_series(
                request={
                    "name": self.project_name,
                    "time_series": [time_series]
                }
            )
            
            # Record status code
            status_series = monitoring_v3.TimeSeries()
            status_series.metric.type = f"custom.googleapis.com/api/status_code"
            status_series.metric.labels["endpoint"] = endpoint
            status_series.metric.labels["status"] = str(status_code)
            
            status_series.resource.type = "global"
            status_series.resource.labels["project_id"] = PROJECT_ID
            
            status_point = monitoring_v3.Point()
            status_point.value.int64_value = 1
            status_point.interval.end_time.seconds = int(datetime.utcnow().timestamp())
            status_series.points = [status_point]
            
            self.monitoring_client.create_time_series(
                request={
                    "name": self.project_name,
                    "time_series": [status_series]
                }
            )
            
        except Exception as e:
            logger.error(f"Error recording metrics: {e}")

class LoadBalancer:
    """Load balancing and failover for recommendation service"""
    
    def __init__(self):
        self.service_urls = [
            RECOMMENDATION_SERVICE_URL,
            # Add backup service URLs here
        ]
        self.current_index = 0
        self.health_check_interval = 30  # seconds
        self.last_health_check = datetime.utcnow()
        self.service_health = {url: True for url in self.service_urls}
    
    def get_healthy_service_url(self) -> str:
        """Get a healthy service URL with round-robin load balancing"""
        # Perform health check if needed
        if (datetime.utcnow() - self.last_health_check).seconds > self.health_check_interval:
            self._perform_health_checks()
            self.last_health_check = datetime.utcnow()
        
        # Find next healthy service
        attempts = 0
        while attempts < len(self.service_urls):
            url = self.service_urls[self.current_index]
            if self.service_health.get(url, False):
                self.current_index = (self.current_index + 1) % len(self.service_urls)
                return url
            
            self.current_index = (self.current_index + 1) % len(self.service_urls)
            attempts += 1
        
        # If no healthy services, return primary
        return self.service_urls[0]
    
    def _perform_health_checks(self):
        """Check health of all services"""
        for url in self.service_urls:
            try:
                response = requests.get(f"{url}/health", timeout=5)
                self.service_health[url] = response.status_code == 200
            except Exception as e:
                logger.warning(f"Health check failed for {url}: {e}")
                self.service_health[url] = False

class RecommendationOrchestrator:
    """Orchestrate recommendation requests with caching and optimization"""
    
    def __init__(self):
        self.db = db
        self.load_balancer = LoadBalancer()
        self.monitoring = APIMonitoring()
        self.cache_ttl = 300  # 5 minutes
    
    def get_recommendations(self, user_id: str, limit: int = 10, 
                          include_reasoning: bool = True, 
                          filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get recommendations with caching and load balancing"""
        
        # Check cache first
        cache_key = self._generate_cache_key(user_id, limit, include_reasoning, filters)
        cached_result = self._get_from_cache(cache_key)
        
        if cached_result:
            logger.info(f"Cache hit for user {user_id}")
            return cached_result
        
        # Get service URL
        service_url = self.load_balancer.get_healthy_service_url()
        
        # Make request to recommendation service
        start_time = datetime.utcnow()
        
        try:
            response = requests.post(
                f"{service_url}/api/v1/recommendations",
                json={
                    'user_id': user_id,
                    'limit': limit,
                    'include_reasoning': include_reasoning,
                    'filters': filters
                },
                timeout=30
            )
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self.monitoring.record_api_call('/api/v1/recommendations', response_time, response.status_code)
            
            if response.status_code == 200:
                result = response.json()
                
                # Cache the result
                self._cache_result(cache_key, result)
                
                # Publish to Pub/Sub for analytics
                self._publish_recommendation_event(user_id, result)
                
                return result
            else:
                logger.error(f"Recommendation service error: {response.status_code}")
                return {'error': 'Service temporarily unavailable'}
                
        except Exception as e:
            logger.error(f"Error calling recommendation service: {e}")
            return {'error': 'Service temporarily unavailable'}
    
    def _generate_cache_key(self, user_id: str, limit: int, 
                          include_reasoning: bool, filters: Dict[str, Any]) -> str:
        """Generate cache key for recommendations"""
        filter_str = json.dumps(filters, sort_keys=True) if filters else ""
        return f"rec_{user_id}_{limit}_{include_reasoning}_{hash(filter_str)}"
    
    def _get_from_cache(self, cache_key: str) -> Dict[str, Any]:
        """Get result from cache"""
        try:
            doc_ref = self.db.collection('recommendation_cache').document(cache_key)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                cached_at = data.get('cached_at')
                
                # Check if cache is still valid
                if cached_at and (datetime.utcnow() - cached_at).seconds < self.cache_ttl:
                    return data.get('result')
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache recommendation result"""
        try:
            doc_ref = self.db.collection('recommendation_cache').document(cache_key)
            doc_ref.set({
                'result': result,
                'cached_at': datetime.utcnow()
            })
            
        except Exception as e:
            logger.error(f"Error caching result: {e}")
    
    def _publish_recommendation_event(self, user_id: str, result: Dict[str, Any]):
        """Publish recommendation event to Pub/Sub for analytics"""
        try:
            topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
            
            event_data = {
                'user_id': user_id,
                'recommendation_count': result.get('total_count', 0),
                'generated_at': result.get('generated_at'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            future = publisher.publish(topic_path, json.dumps(event_data).encode('utf-8'))
            future.result()
            
        except Exception as e:
            logger.error(f"Error publishing event: {e}")

class UserPreferenceManager:
    """Manage user preferences with validation and optimization"""
    
    def __init__(self):
        self.db = db
    
    def update_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """Update user preferences with validation"""
        try:
            # Validate preferences
            validated_prefs = self._validate_preferences(preferences)
            
            # Update in Firestore
            doc_ref = self.db.collection('user_preferences').document(user_id)
            doc_ref.set(validated_prefs, merge=True)
            
            # Clear related caches
            self._clear_user_caches(user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return False
    
    def _validate_preferences(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize user preferences"""
        validated = {}
        
        # Validate genres
        if 'favorite_genres' in preferences:
            genres = preferences['favorite_genres']
            if isinstance(genres, list):
                validated['favorite_genres'] = [str(g).lower() for g in genres[:20]]
        
        # Validate artists
        if 'favorite_artists' in preferences:
            artists = preferences['favorite_artists']
            if isinstance(artists, list):
                validated['favorite_artists'] = [str(a).strip() for a in artists[:50]]
        
        # Validate mood preferences
        if 'mood_preferences' in preferences:
            moods = preferences['mood_preferences']
            if isinstance(moods, list):
                validated['mood_preferences'] = [str(m).lower() for m in moods[:10]]
        
        # Validate tempo preferences
        if 'tempo_preferences' in preferences:
            tempos = preferences['tempo_preferences']
            if isinstance(tempos, list):
                validated['tempo_preferences'] = [str(t).lower() for t in tempos[:5]]
        
        # Add timestamp
        validated['updated_at'] = datetime.utcnow()
        
        return validated
    
    def _clear_user_caches(self, user_id: str):
        """Clear all caches related to a user"""
        try:
            # Get all cache documents for this user
            cache_refs = self.db.collection('recommendation_cache').where('user_id', '==', user_id).stream()
            
            batch = self.db.batch()
            for doc in cache_refs:
                batch.delete(doc.reference)
            
            batch.commit()
            
        except Exception as e:
            logger.error(f"Error clearing user caches: {e}")

# Initialize orchestrator
orchestrator = RecommendationOrchestrator()
preference_manager = UserPreferenceManager()

def get_recommendations_http(request):
    """HTTP Cloud Function for getting recommendations"""
    try:
        # Parse request
        if request.method != 'POST':
            return json.dumps({'error': 'Method not allowed'}), 405
        
        request_data = request.get_json()
        if not request_data:
            return json.dumps({'error': 'No request data'}), 400
        
        user_id = request_data.get('user_id')
        limit = request_data.get('limit', 10)
        include_reasoning = request_data.get('include_reasoning', True)
        filters = request_data.get('filters')
        
        if not user_id:
            return json.dumps({'error': 'user_id required'}), 400
        
        # Get recommendations
        result = orchestrator.get_recommendations(
            user_id=user_id,
            limit=limit,
            include_reasoning=include_reasoning,
            filters=filters
        )
        
        return json.dumps(result), 200
        
    except Exception as e:
        logger.error(f"Error in get_recommendations_http: {e}")
        return json.dumps({'error': 'Internal server error'}), 500

def update_preferences_http(request):
    """HTTP Cloud Function for updating user preferences"""
    try:
        if request.method not in ['POST', 'PUT']:
            return json.dumps({'error': 'Method not allowed'}), 405
        
        request_data = request.get_json()
        if not request_data:
            return json.dumps({'error': 'No request data'}), 400
        
        user_id = request_data.get('user_id')
        preferences = request_data.get('preferences', {})
        
        if not user_id:
            return json.dumps({'error': 'user_id required'}), 400
        
        # Update preferences
        success = preference_manager.update_preferences(user_id, preferences)
        
        if success:
            return json.dumps({'message': 'Preferences updated successfully'}), 200
        else:
            return json.dumps({'error': 'Failed to update preferences'}), 500
        
    except Exception as e:
        logger.error(f"Error in update_preferences_http: {e}")
        return json.dumps({'error': 'Internal server error'}), 500

def health_check_http(request):
    """HTTP Cloud Function for health checks"""
    try:
        # Check all dependencies
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'dependencies': {
                'firestore': True,
                'pubsub': True,
                'monitoring': True
            }
        }
        
        # Test Firestore
        try:
            self.db.collection('health_check').document('test').get()
        except Exception:
            health_status['dependencies']['firestore'] = False
            health_status['status'] = 'degraded'
        
        # Test Pub/Sub
        try:
            topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
            publisher.get_topic(request={'topic': topic_path})
        except Exception:
            health_status['dependencies']['pubsub'] = False
            health_status['status'] = 'degraded'
        
        return json.dumps(health_status), 200
        
    except Exception as e:
        logger.error(f"Error in health_check_http: {e}")
        return json.dumps({'status': 'unhealthy', 'error': str(e)}), 500

def process_recommendation_analytics(event, context):
    """Background Cloud Function for processing recommendation analytics"""
    try:
        # Parse Pub/Sub message
        data = json.loads(event['data'].decode('utf-8'))
        
        # Process analytics
        user_id = data.get('user_id')
        recommendation_count = data.get('recommendation_count', 0)
        timestamp = data.get('timestamp')
        
        # Store analytics in Firestore
        analytics_ref = self.db.collection('recommendation_analytics').document()
        analytics_ref.set({
            'user_id': user_id,
            'recommendation_count': recommendation_count,
            'timestamp': timestamp,
            'processed_at': datetime.utcnow()
        })
        
        # Update user statistics
        user_stats_ref = self.db.collection('user_statistics').document(user_id)
        user_stats_ref.set({
            'total_recommendations': firestore.Increment(recommendation_count),
            'last_recommendation_at': timestamp,
            'updated_at': datetime.utcnow()
        }, merge=True)
        
        logger.info(f"Processed analytics for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error processing analytics: {e}")
        raise

def cleanup_cache(event, context):
    """Scheduled Cloud Function for cache cleanup"""
    try:
        # Delete expired cache entries
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        cache_refs = self.db.collection('recommendation_cache').where(
            'cached_at', '<', cutoff_time
        ).stream()
        
        batch = self.db.batch()
        deleted_count = 0
        
        for doc in cache_refs:
            batch.delete(doc.reference)
            deleted_count += 1
            
            # Commit in batches of 500
            if deleted_count % 500 == 0:
                batch.commit()
                batch = self.db.batch()
        
        # Commit remaining
        if deleted_count % 500 != 0:
            batch.commit()
        
        logger.info(f"Cleaned up {deleted_count} expired cache entries")
        
    except Exception as e:
        logger.error(f"Error cleaning up cache: {e}")
        raise 