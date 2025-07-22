#!/usr/bin/env python3
"""
Simple API test script for the LLM-Driven Artist Recommendation Engine
"""

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv('RECOMMENDATION_SERVICE_URL', 'http://localhost:8080')

def test_health_endpoint():
    """Test the health check endpoint"""
    print("🔍 Testing health endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data.get('status')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_search_endpoint():
    """Test the artist search endpoint"""
    print("🔍 Testing search endpoint...")
    
    try:
        params = {
            "q": "pop",
            "limit": 5
        }
        
        response = requests.get(f"{BASE_URL}/api/v1/artists/search", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            artists = data.get('artists', [])
            print(f"✅ Search test passed: Found {len(artists)} artists")
            return True
        else:
            print(f"❌ Search test failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Search test error: {e}")
        return False

def test_recommendation_endpoint():
    """Test the recommendation endpoint"""
    print("🔍 Testing recommendation endpoint...")
    
    try:
        payload = {
            "user_id": "test_user_001",
            "limit": 3,
            "include_reasoning": True
        }
        
        response = requests.post(f"{BASE_URL}/api/v1/recommendations", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            recommendations = data.get('recommendations', [])
            print(f"✅ Recommendation test passed: Generated {len(recommendations)} recommendations")
            return True
        else:
            print(f"❌ Recommendation test failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Recommendation test error: {e}")
        return False

def test_preferences_endpoint():
    """Test the preferences endpoint"""
    print("🔍 Testing preferences endpoint...")
    
    try:
        # Test creating preferences
        payload = {
            "user_id": "test_user_002",
            "favorite_genres": ["pop", "r&b"],
            "favorite_artists": ["The Weeknd", "Drake"],
            "mood_preferences": ["energetic", "romantic"]
        }
        
        response = requests.post(f"{BASE_URL}/api/v1/preferences", json=payload, timeout=10)
        
        if response.status_code == 200:
            print("✅ Preferences creation test passed")
            
            # Test getting preferences
            response = requests.get(f"{BASE_URL}/api/v1/preferences?user_id=test_user_002", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Preferences retrieval test passed: Found preferences for {data.get('user_id')}")
                return True
            else:
                print(f"❌ Preferences retrieval test failed: {response.status_code}")
                return False
        else:
            print(f"❌ Preferences creation test failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Preferences test error: {e}")
        return False

def run_performance_test():
    """Run a simple performance test"""
    print("🔍 Running performance test...")
    
    start_time = datetime.utcnow()
    
    # Test search performance
    search_start = datetime.utcnow()
    response = requests.get(f"{BASE_URL}/api/v1/artists/search?q=pop&limit=10", timeout=10)
    search_time = (datetime.utcnow() - search_start).total_seconds()
    
    if response.status_code == 200:
        print(f"✅ Search performance: {search_time:.3f}s (< 100ms target: {'✅' if search_time < 0.1 else '❌'})")
    else:
        print(f"❌ Search performance test failed")
    
    # Test recommendation performance
    rec_start = datetime.utcnow()
    payload = {"user_id": "test_user_001", "limit": 5, "include_reasoning": False}
    response = requests.post(f"{BASE_URL}/api/v1/recommendations", json=payload, timeout=30)
    rec_time = (datetime.utcnow() - rec_start).total_seconds()
    
    if response.status_code == 200:
        print(f"✅ Recommendation performance: {rec_time:.3f}s (< 5s target: {'✅' if rec_time < 5 else '❌'})")
    else:
        print(f"❌ Recommendation performance test failed")
    
    total_time = (datetime.utcnow() - start_time).total_seconds()
    print(f"⏱️  Total test time: {total_time:.3f}s")

def main():
    """Main test function"""
    print("🎵 LLM-Driven Artist Recommendation Engine - API Test")
    print("=" * 60)
    print(f"🌐 Testing against: {BASE_URL}")
    print("=" * 60)
    
    tests = [
        ("Health Check", test_health_endpoint),
        ("Search API", test_search_endpoint),
        ("Recommendations API", test_recommendation_endpoint),
        ("Preferences API", test_preferences_endpoint)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 {test_name}")
        print("-" * 40)
        
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 All tests passed! The API is working correctly.")
        
        # Run performance test
        print("\n" + "=" * 60)
        print("⚡ PERFORMANCE TEST")
        print("=" * 60)
        run_performance_test()
        
    else:
        print("\n⚠️  Some tests failed. Please check the configuration and try again.")
    
    print("\n" + "=" * 60)
    print("🏁 Test completed!")

if __name__ == "__main__":
    main() 