#!/usr/bin/env python3
"""
Data seeding script for the LLM-Driven Artist Recommendation Engine
Seeds sample artists into Algolia and user preferences into Firestore
"""

import os
import json
import random
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any

from google.cloud import firestore
from algoliasearch.search_client import SearchClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize clients
db = firestore.Client()
algolia_client = SearchClient.create(
    os.getenv('ALGOLIA_APP_ID'),
    os.getenv('ALGOLIA_API_KEY')
)
search_index = algolia_client.init_index('artists')

# Sample artist data
SAMPLE_ARTISTS = [
    {
        "objectID": "artist_001",
        "artist_id": "artist_001",
        "name": "The Weeknd",
        "genres": ["r&b", "pop", "alternative r&b"],
        "popularity": 95,
        "followers": 45000000,
        "country": "Canada",
        "bio": "Canadian singer-songwriter known for his distinctive voice and dark R&B style",
        "image_url": "https://example.com/weeknd.jpg",
        "spotify_id": "1Xyo4u8uXC1ZmMpatF05PJ"
    },
    {
        "objectID": "artist_002",
        "artist_id": "artist_002",
        "name": "Drake",
        "genres": ["hip hop", "rap", "r&b"],
        "popularity": 98,
        "followers": 55000000,
        "country": "Canada",
        "bio": "Canadian rapper, singer, and actor known for his versatile style",
        "image_url": "https://example.com/drake.jpg",
        "spotify_id": "3TVXtAsR1Inumwj472S9r4"
    },
    {
        "objectID": "artist_003",
        "artist_id": "artist_003",
        "name": "Taylor Swift",
        "genres": ["pop", "country", "folk"],
        "popularity": 97,
        "followers": 52000000,
        "country": "United States",
        "bio": "American singer-songwriter known for her narrative songwriting",
        "image_url": "https://example.com/taylor.jpg",
        "spotify_id": "06HL4z0CvFAxyc27GXpf02"
    },
    {
        "objectID": "artist_004",
        "artist_id": "artist_004",
        "name": "Ed Sheeran",
        "genres": ["pop", "folk", "acoustic"],
        "popularity": 96,
        "followers": 48000000,
        "country": "United Kingdom",
        "bio": "English singer-songwriter known for his acoustic sound",
        "image_url": "https://example.com/ed.jpg",
        "spotify_id": "6eUKZXaKkcviH0Ku9w2n3V"
    },
    {
        "objectID": "artist_005",
        "artist_id": "artist_005",
        "name": "Post Malone",
        "genres": ["hip hop", "pop", "trap"],
        "popularity": 94,
        "followers": 42000000,
        "country": "United States",
        "bio": "American rapper, singer, and songwriter known for his melodic style",
        "image_url": "https://example.com/post.jpg",
        "spotify_id": "246dkjvS1zLTtiykXe5h60"
    },
    {
        "objectID": "artist_006",
        "artist_id": "artist_006",
        "name": "Ariana Grande",
        "genres": ["pop", "r&b", "dance pop"],
        "popularity": 96,
        "followers": 46000000,
        "country": "United States",
        "bio": "American singer and actress known for her powerful vocals",
        "image_url": "https://example.com/ariana.jpg",
        "spotify_id": "66CXWjxzNUsdJxJ2JdwvnR"
    },
    {
        "objectID": "artist_007",
        "artist_id": "artist_007",
        "name": "Bad Bunny",
        "genres": ["reggaeton", "latin", "trap"],
        "popularity": 93,
        "followers": 38000000,
        "country": "Puerto Rico",
        "bio": "Puerto Rican rapper and singer known for reggaeton and Latin trap",
        "image_url": "https://example.com/badbunny.jpg",
        "spotify_id": "4q3ewBCX7sLwd24euuV69X"
    },
    {
        "objectID": "artist_008",
        "artist_id": "artist_008",
        "name": "Billie Eilish",
        "genres": ["pop", "alternative", "indie pop"],
        "popularity": 92,
        "followers": 35000000,
        "country": "United States",
        "bio": "American singer-songwriter known for her whisper vocals and dark pop",
        "image_url": "https://example.com/billie.jpg",
        "spotify_id": "6qqNVTkY8uBg9cP3Jd7DAH"
    },
    {
        "objectID": "artist_009",
        "artist_id": "artist_009",
        "name": "Dua Lipa",
        "genres": ["pop", "dance pop", "disco"],
        "popularity": 91,
        "followers": 32000000,
        "country": "United Kingdom",
        "bio": "English singer-songwriter known for her disco-influenced pop",
        "image_url": "https://example.com/dua.jpg",
        "spotify_id": "6M2wZ9GZgrQXHCFfjv46we"
    },
    {
        "objectID": "artist_010",
        "artist_id": "artist_010",
        "name": "The Kid LAROI",
        "genres": ["hip hop", "pop", "trap"],
        "popularity": 89,
        "followers": 28000000,
        "country": "Australia",
        "bio": "Australian rapper and singer known for his melodic rap style",
        "image_url": "https://example.com/laroi.jpg",
        "spotify_id": "2tIP7SsRs7vjIcLrU85W8J"
    },
    {
        "objectID": "artist_011",
        "artist_id": "artist_011",
        "name": "Olivia Rodrigo",
        "genres": ["pop", "pop rock", "indie pop"],
        "popularity": 88,
        "followers": 25000000,
        "country": "United States",
        "bio": "American singer-songwriter known for her emotional pop songs",
        "image_url": "https://example.com/olivia.jpg",
        "spotify_id": "1McMsnEElThX1knmY4oliG"
    },
    {
        "objectID": "artist_012",
        "artist_id": "artist_012",
        "name": "Doja Cat",
        "genres": ["pop", "hip hop", "r&b"],
        "popularity": 90,
        "followers": 30000000,
        "country": "United States",
        "bio": "American rapper and singer known for her versatile style",
        "image_url": "https://example.com/doja.jpg",
        "spotify_id": "5cj0lLjcoR7YOSnhnX0Po5"
    },
    {
        "objectID": "artist_013",
        "artist_id": "artist_013",
        "name": "Lil Nas X",
        "genres": ["hip hop", "pop", "country rap"],
        "popularity": 87,
        "followers": 22000000,
        "country": "United States",
        "bio": "American rapper and singer known for blending genres",
        "image_url": "https://example.com/lilnasx.jpg",
        "spotify_id": "7jVv8c5Fj3E9VhNjxT4snq"
    },
    {
        "objectID": "artist_014",
        "artist_id": "artist_014",
        "name": "Megan Thee Stallion",
        "genres": ["hip hop", "rap", "trap"],
        "popularity": 86,
        "followers": 20000000,
        "country": "United States",
        "bio": "American rapper known for her confident and empowering lyrics",
        "image_url": "https://example.com/megan.jpg",
        "spotify_id": "181bsRPaVXVlUKXrxwZfHK"
    },
    {
        "objectID": "artist_015",
        "artist_id": "artist_015",
        "name": "Roddy Ricch",
        "genres": ["hip hop", "rap", "trap"],
        "popularity": 85,
        "followers": 18000000,
        "country": "United States",
        "bio": "American rapper and singer known for his melodic trap style",
        "image_url": "https://example.com/roddy.jpg",
        "spotify_id": "757aE44tKEUQEqRuT6GnEB"
    }
]

# Sample user preferences
SAMPLE_USER_PREFERENCES = [
    {
        "user_id": "user_001",
        "favorite_genres": ["pop", "r&b", "hip hop"],
        "favorite_artists": ["The Weeknd", "Drake", "Ariana Grande"],
        "listening_history": ["Blinding Lights", "God's Plan", "7 rings"],
        "mood_preferences": ["energetic", "romantic", "confident"],
        "tempo_preferences": ["medium", "fast"]
    },
    {
        "user_id": "user_002",
        "favorite_genres": ["country", "folk", "acoustic"],
        "favorite_artists": ["Taylor Swift", "Ed Sheeran"],
        "listening_history": ["Shake It Off", "Shape of You", "All Too Well"],
        "mood_preferences": ["nostalgic", "peaceful", "romantic"],
        "tempo_preferences": ["slow", "medium"]
    },
    {
        "user_id": "user_003",
        "favorite_genres": ["hip hop", "trap", "rap"],
        "favorite_artists": ["Drake", "Post Malone", "The Kid LAROI"],
        "listening_history": ["Circles", "Rockstar", "Stay"],
        "mood_preferences": ["confident", "energetic", "chill"],
        "tempo_preferences": ["fast", "medium"]
    },
    {
        "user_id": "user_004",
        "favorite_genres": ["reggaeton", "latin", "pop"],
        "favorite_artists": ["Bad Bunny", "Dua Lipa"],
        "listening_history": ["Dákiti", "Levitating", "Me Porto Bonito"],
        "mood_preferences": ["energetic", "romantic", "fun"],
        "tempo_preferences": ["fast", "medium"]
    },
    {
        "user_id": "user_005",
        "favorite_genres": ["alternative", "indie pop", "pop"],
        "favorite_artists": ["Billie Eilish", "Olivia Rodrigo"],
        "listening_history": ["bad guy", "drivers license", "Happier Than Ever"],
        "mood_preferences": ["melancholic", "introspective", "emotional"],
        "tempo_preferences": ["slow", "medium"]
    }
]

def seed_artists_to_algolia():
    """Seed sample artists to Algolia search index"""
    print("Seeding artists to Algolia...")
    
    try:
        # Clear existing data
        search_index.clear_objects()
        print("Cleared existing artist data")
        
        # Add sample artists
        search_index.save_objects(SAMPLE_ARTISTS)
        print(f"Successfully seeded {len(SAMPLE_ARTISTS)} artists to Algolia")
        
        # Configure search settings for better performance
        search_index.set_settings({
            'searchableAttributes': [
                'name',
                'genres',
                'country',
                'bio'
            ],
            'attributesForFaceting': [
                'genres',
                'country',
                'popularity'
            ],
            'ranking': [
                'typo',
                'geo',
                'words',
                'filters',
                'proximity',
                'attribute',
                'exact',
                'custom'
            ],
            'customRanking': [
                'desc(popularity)',
                'desc(followers)'
            ]
        })
        print("Configured Algolia search settings")
        
    except Exception as e:
        print(f"Error seeding artists to Algolia: {e}")
        raise

def seed_user_preferences_to_firestore():
    """Seed sample user preferences to Firestore"""
    print("Seeding user preferences to Firestore...")
    
    try:
        batch = db.batch()
        
        for user_pref in SAMPLE_USER_PREFERENCES:
            doc_ref = db.collection('user_preferences').document(user_pref['user_id'])
            
            # Add timestamps
            user_pref['created_at'] = datetime.now(timezone.utc)
            user_pref['updated_at'] = datetime.now(timezone.utc)
            
            batch.set(doc_ref, user_pref)
        
        batch.commit()
        print(f"Successfully seeded {len(SAMPLE_USER_PREFERENCES)} user preferences to Firestore")
        
    except Exception as e:
        print(f"Error seeding user preferences to Firestore: {e}")
        raise

def create_algolia_index():
    """Create Algolia index if it doesn't exist"""
    print("Creating Algolia index...")
    
    try:
        # Check if index exists
        try:
            search_index.get_settings()
            print("Algolia index already exists")
        except Exception:
            # Create new index
            search_index.save_object({
                "objectID": "init",
                "name": "Initialization"
            })
            search_index.delete_object("init")
            print("Created new Algolia index")
            
    except Exception as e:
        print(f"Error creating Algolia index: {e}")
        raise

def verify_data():
    """Verify that data was seeded correctly"""
    print("Verifying seeded data...")
    
    try:
        # Verify Algolia
        algolia_results = search_index.search("", {'hitsPerPage': 1})
        algolia_count = algolia_results.get('nbHits', 0)
        print(f"Algolia: Found {algolia_count} artists")
        
        # Verify Firestore
        firestore_docs = db.collection('user_preferences').limit(1).stream()
        firestore_count = len(list(firestore_docs))
        print(f"Firestore: Found {firestore_count} user preferences")
        
        if algolia_count > 0 and firestore_count > 0:
            print("✅ Data seeding completed successfully!")
        else:
            print("❌ Data seeding verification failed")
            
    except Exception as e:
        print(f"Error verifying data: {e}")

def main():
    """Main function to seed all data"""
    print("🚀 Starting data seeding for LLM-Driven Artist Recommendation Engine")
    print("=" * 60)
    
    try:
        # Create Algolia index
        create_algolia_index()
        
        # Seed artists to Algolia
        seed_artists_to_algolia()
        
        # Seed user preferences to Firestore
        seed_user_preferences_to_firestore()
        
        # Verify data
        verify_data()
        
        print("=" * 60)
        print("🎉 Data seeding completed successfully!")
        print("\nNext steps:")
        print("1. Test the API endpoints")
        print("2. Run load testing")
        print("3. Monitor performance metrics")
        
    except Exception as e:
        print(f"❌ Data seeding failed: {e}")
        raise

if __name__ == "__main__":
    main() 