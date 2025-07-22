#!/usr/bin/env python3
"""
Load testing script for the LLM-Driven Artist Recommendation Engine
Tests performance and uptime under various load conditions
"""

import os
import time
import json
import random
import asyncio
import aiohttp
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import threading
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv('RECOMMENDATION_SERVICE_URL', 'http://localhost:8080')
TEST_DURATION = 300  # 5 minutes
CONCURRENT_USERS = 50
REQUESTS_PER_USER = 20
TARGET_UPTIME = 99.9

@dataclass
class TestResult:
    """Test result data class"""
    endpoint: str
    response_time: float
    status_code: int
    success: bool
    timestamp: datetime
    user_id: str

class LoadTester:
    """Load testing class for the recommendation engine"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.lock = threading.Lock()
        self.test_users = [f"test_user_{i:03d}" for i in range(1, 101)]
        
    async def test_recommendation_endpoint(self, session: aiohttp.ClientSession, user_id: str) -> TestResult:
        """Test the recommendation endpoint"""
        start_time = time.time()
        
        try:
            payload = {
                "user_id": user_id,
                "limit": random.randint(5, 15),
                "include_reasoning": random.choice([True, False]),
                "filters": {
                    "genres": random.choice([["pop"], ["hip hop"], ["r&b"], None]),
                    "min_popularity": random.choice([80, 85, 90, None])
                } if random.random() > 0.5 else None
            }
            
            async with session.post(
                f"{self.base_url}/api/v1/recommendations",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_time = time.time() - start_time
                response_text = await response.text()
                
                success = response.status == 200
                
                result = TestResult(
                    endpoint="/api/v1/recommendations",
                    response_time=response_time,
                    status_code=response.status,
                    success=success,
                    timestamp=datetime.utcnow(),
                    user_id=user_id
                )
                
                with self.lock:
                    self.results.append(result)
                
                return result
                
        except Exception as e:
            response_time = time.time() - start_time
            result = TestResult(
                endpoint="/api/v1/recommendations",
                response_time=response_time,
                status_code=0,
                success=False,
                timestamp=datetime.utcnow(),
                user_id=user_id
            )
            
            with self.lock:
                self.results.append(result)
            
            return result
    
    async def test_search_endpoint(self, session: aiohttp.ClientSession) -> TestResult:
        """Test the artist search endpoint"""
        start_time = time.time()
        
        try:
            search_queries = ["pop", "hip hop", "r&b", "taylor", "drake", "weeknd"]
            query = random.choice(search_queries)
            
            params = {
                "q": query,
                "limit": random.randint(10, 30)
            }
            
            if random.random() > 0.7:
                params["genres"] = random.choice(["pop", "hip hop", "r&b"])
            
            async with session.get(
                f"{self.base_url}/api/v1/artists/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response_time = time.time() - start_time
                await response.text()
                
                success = response.status == 200
                
                result = TestResult(
                    endpoint="/api/v1/artists/search",
                    response_time=response_time,
                    status_code=response.status,
                    success=success,
                    timestamp=datetime.utcnow(),
                    user_id="search_test"
                )
                
                with self.lock:
                    self.results.append(result)
                
                return result
                
        except Exception as e:
            response_time = time.time() - start_time
            result = TestResult(
                endpoint="/api/v1/artists/search",
                response_time=response_time,
                status_code=0,
                success=False,
                timestamp=datetime.utcnow(),
                user_id="search_test"
            )
            
            with self.lock:
                self.results.append(result)
            
            return result
    
    async def test_health_endpoint(self, session: aiohttp.ClientSession) -> TestResult:
        """Test the health check endpoint"""
        start_time = time.time()
        
        try:
            async with session.get(
                f"{self.base_url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                response_time = time.time() - start_time
                await response.text()
                
                success = response.status == 200
                
                result = TestResult(
                    endpoint="/health",
                    response_time=response_time,
                    status_code=response.status,
                    success=success,
                    timestamp=datetime.utcnow(),
                    user_id="health_test"
                )
                
                with self.lock:
                    self.results.append(result)
                
                return result
                
        except Exception as e:
            response_time = time.time() - start_time
            result = TestResult(
                endpoint="/health",
                response_time=response_time,
                status_code=0,
                success=False,
                timestamp=datetime.utcnow(),
                user_id="health_test"
            )
            
            with self.lock:
                self.results.append(result)
            
            return result
    
    async def simulate_user_session(self, session: aiohttp.ClientSession, user_id: str):
        """Simulate a user session with multiple requests"""
        tasks = []
        
        # Mix of different request types
        for i in range(REQUESTS_PER_USER):
            if i % 3 == 0:
                # Recommendation request
                task = self.test_recommendation_endpoint(session, user_id)
            elif i % 3 == 1:
                # Search request
                task = self.test_search_endpoint(session)
            else:
                # Health check
                task = self.test_health_endpoint(session)
            
            tasks.append(task)
            
            # Add small delay between requests
            await asyncio.sleep(random.uniform(0.1, 0.5))
        
        await asyncio.gather(*tasks)
    
    async def run_load_test(self):
        """Run the main load test"""
        print(f"🚀 Starting load test for {TEST_DURATION} seconds")
        print(f"📊 Target: {CONCURRENT_USERS} concurrent users, {REQUESTS_PER_USER} requests per user")
        print(f"🎯 Target uptime: {TARGET_UPTIME}%")
        print("=" * 60)
        
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=TEST_DURATION)
        
        async with aiohttp.ClientSession() as session:
            while datetime.utcnow() < end_time:
                # Create concurrent user sessions
                user_tasks = []
                for i in range(CONCURRENT_USERS):
                    user_id = random.choice(self.test_users)
                    task = self.simulate_user_session(session, user_id)
                    user_tasks.append(task)
                
                # Run all user sessions concurrently
                await asyncio.gather(*user_tasks)
                
                # Progress update
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                progress = (elapsed / TEST_DURATION) * 100
                print(f"⏱️  Progress: {progress:.1f}% ({elapsed:.0f}s / {TEST_DURATION}s)")
        
        print("✅ Load test completed!")
        return self.analyze_results()
    
    def analyze_results(self) -> Dict[str, Any]:
        """Analyze test results and generate statistics"""
        if not self.results:
            return {"error": "No test results available"}
        
        total_requests = len(self.results)
        successful_requests = len([r for r in self.results if r.success])
        failed_requests = total_requests - successful_requests
        
        # Calculate uptime
        uptime_percentage = (successful_requests / total_requests) * 100
        
        # Response time statistics
        response_times = [r.response_time for r in self.results if r.success]
        
        # Status code distribution
        status_codes = {}
        for result in self.results:
            status = result.status_code
            status_codes[status] = status_codes.get(status, 0) + 1
        
        # Endpoint-specific statistics
        endpoint_stats = {}
        for endpoint in set(r.endpoint for r in self.results):
            endpoint_results = [r for r in self.results if r.endpoint == endpoint]
            endpoint_success = len([r for r in endpoint_results if r.success])
            endpoint_response_times = [r.response_time for r in endpoint_results if r.success]
            
            endpoint_stats[endpoint] = {
                "total_requests": len(endpoint_results),
                "successful_requests": endpoint_success,
                "success_rate": (endpoint_success / len(endpoint_results)) * 100,
                "avg_response_time": statistics.mean(endpoint_response_times) if endpoint_response_times else 0,
                "p95_response_time": statistics.quantiles(endpoint_response_times, n=20)[18] if len(endpoint_response_times) >= 20 else 0,
                "p99_response_time": statistics.quantiles(endpoint_response_times, n=100)[98] if len(endpoint_response_times) >= 100 else 0
            }
        
        analysis = {
            "test_summary": {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "uptime_percentage": uptime_percentage,
                "target_uptime": TARGET_UPTIME,
                "uptime_achieved": uptime_percentage >= TARGET_UPTIME
            },
            "response_time_stats": {
                "mean": statistics.mean(response_times) if response_times else 0,
                "median": statistics.median(response_times) if response_times else 0,
                "p95": statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else 0,
                "p99": statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else 0,
                "min": min(response_times) if response_times else 0,
                "max": max(response_times) if response_times else 0
            },
            "status_code_distribution": status_codes,
            "endpoint_statistics": endpoint_stats,
            "test_configuration": {
                "base_url": self.base_url,
                "test_duration": TEST_DURATION,
                "concurrent_users": CONCURRENT_USERS,
                "requests_per_user": REQUESTS_PER_USER
            }
        }
        
        return analysis
    
    def print_results(self, analysis: Dict[str, Any]):
        """Print formatted test results"""
        print("\n" + "=" * 60)
        print("📊 LOAD TEST RESULTS")
        print("=" * 60)
        
        # Test summary
        summary = analysis["test_summary"]
        print(f"🎯 Uptime Target: {summary['target_uptime']}%")
        print(f"✅ Actual Uptime: {summary['uptime_percentage']:.2f}%")
        print(f"🎉 Target Achieved: {'✅ YES' if summary['uptime_achieved'] else '❌ NO'}")
        print(f"📈 Total Requests: {summary['total_requests']:,}")
        print(f"✅ Successful: {summary['successful_requests']:,}")
        print(f"❌ Failed: {summary['failed_requests']:,}")
        
        # Response time statistics
        rt_stats = analysis["response_time_stats"]
        print(f"\n⏱️  Response Time Statistics:")
        print(f"   Mean: {rt_stats['mean']:.3f}s")
        print(f"   Median: {rt_stats['median']:.3f}s")
        print(f"   P95: {rt_stats['p95']:.3f}s")
        print(f"   P99: {rt_stats['p99']:.3f}s")
        print(f"   Min: {rt_stats['min']:.3f}s")
        print(f"   Max: {rt_stats['max']:.3f}s")
        
        # Status code distribution
        print(f"\n📋 Status Code Distribution:")
        for status, count in analysis["status_code_distribution"].items():
            percentage = (count / summary['total_requests']) * 100
            print(f"   {status}: {count:,} ({percentage:.1f}%)")
        
        # Endpoint statistics
        print(f"\n🔗 Endpoint Statistics:")
        for endpoint, stats in analysis["endpoint_statistics"].items():
            print(f"   {endpoint}:")
            print(f"     Success Rate: {stats['success_rate']:.1f}%")
            print(f"     Avg Response Time: {stats['avg_response_time']:.3f}s")
            print(f"     P95 Response Time: {stats['p95_response_time']:.3f}s")
        
        # Performance assessment
        print(f"\n🏆 Performance Assessment:")
        if summary['uptime_achieved']:
            print("   ✅ Uptime target achieved!")
        else:
            print("   ❌ Uptime target not achieved")
        
        if rt_stats['p95'] < 1.0:
            print("   ✅ P95 response time under 1 second")
        else:
            print("   ⚠️  P95 response time over 1 second")
        
        if rt_stats['mean'] < 0.5:
            print("   ✅ Average response time under 500ms")
        else:
            print("   ⚠️  Average response time over 500ms")

async def main():
    """Main function to run load test"""
    print("🎵 LLM-Driven Artist Recommendation Engine - Load Test")
    print("=" * 60)
    
    # Initialize load tester
    tester = LoadTester(BASE_URL)
    
    try:
        # Run load test
        analysis = await tester.run_load_test()
        
        # Print results
        tester.print_results(analysis)
        
        # Save results to file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"load_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {filename}")
        
        # Final assessment
        if analysis["test_summary"]["uptime_achieved"]:
            print("\n🎉 SUCCESS: Load test passed! 99.9% uptime achieved.")
        else:
            print("\n⚠️  WARNING: Load test did not achieve target uptime.")
        
    except Exception as e:
        print(f"❌ Load test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 