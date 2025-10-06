#!/usr/bin/env python3
"""
Stress testing script for the Order Matching Engine
Tests concurrent order submission and system performance
"""

import requests
import threading
import time
import random
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import statistics

class StressTester:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.results = []
        self.lock = threading.Lock()
        self.symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
        self.users = [f'user_{i}' for i in range(1000)]  # 1000 different users
        
    def create_order_data(self, user_id=None, symbol=None):
        """Generate random order data"""
        return {
            'user_id': user_id or random.choice(self.users),
            'symbol': symbol or random.choice(self.symbols),
            'side': random.choice(['BUY', 'SELL']),
            'quantity': random.randint(1, 1000),
            'price': round(random.uniform(50.0, 500.0), 2)
        }
    
    def submit_order(self, order_data):
        """Submit a single order and measure performance"""
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/orders",
                json=order_data,
                timeout=10
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            result = {
                'success': response.status_code == 201,
                'status_code': response.status_code,
                'response_time': response_time,
                'timestamp': datetime.utcnow().isoformat(),
                'order_data': order_data
            }
            
            if response.status_code == 201:
                response_data = response.json()
                result['order_id'] = response_data.get('order_id')
                result['executed_trades'] = len(response_data.get('executed_trades', []))
            
            with self.lock:
                self.results.append(result)
            
            return result
            
        except requests.exceptions.RequestException as e:
            end_time = time.time()
            result = {
                'success': False,
                'error': str(e),
                'response_time': end_time - start_time,
                'timestamp': datetime.utcnow().isoformat(),
                'order_data': order_data
            }
            
            with self.lock:
                self.results.append(result)
            
            return result
    
    def run_concurrent_test(self, num_orders=1000, max_workers=50):
        """Run concurrent order submission test"""
        print(f"Starting concurrent test with {num_orders} orders and {max_workers} workers...")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all orders
            futures = []
            for _ in range(num_orders):
                order_data = self.create_order_data()
                future = executor.submit(self.submit_order, order_data)
                futures.append(future)
            
            # Wait for completion
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 100 == 0:
                    print(f"Completed {completed}/{num_orders} orders...")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"Test completed in {total_time:.2f} seconds")
        return total_time
    
    def run_high_frequency_test(self, duration_seconds=60, orders_per_second=100):
        """Run high-frequency order submission test"""
        print(f"Starting high-frequency test for {duration_seconds} seconds at {orders_per_second} orders/second...")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        def order_worker():
            while time.time() < end_time:
                order_data = self.create_order_data()
                self.submit_order(order_data)
                time.sleep(1.0 / orders_per_second)
        
        # Start multiple workers
        workers = []
        for _ in range(10):  # 10 concurrent workers
            worker = threading.Thread(target=order_worker)
            worker.start()
            workers.append(worker)
        
        # Wait for all workers to complete
        for worker in workers:
            worker.join()
        
        actual_duration = time.time() - start_time
        print(f"High-frequency test completed in {actual_duration:.2f} seconds")
        return actual_duration
    
    def run_market_simulation(self, num_orders=5000):
        """Run realistic market simulation with order matching"""
        print(f"Starting market simulation with {num_orders} orders...")
        
        # Create balanced buy/sell orders for better matching
        orders = []
        
        for i in range(num_orders):
            symbol = random.choice(self.symbols)
            base_price = random.uniform(100.0, 200.0)
            
            # Create buy order
            buy_order = {
                'user_id': f'buyer_{i}',
                'symbol': symbol,
                'side': 'BUY',
                'quantity': random.randint(1, 100),
                'price': round(base_price + random.uniform(-5.0, 0.0), 2)
            }
            orders.append(buy_order)
            
            # Create sell order
            sell_order = {
                'user_id': f'seller_{i}',
                'symbol': symbol,
                'side': 'SELL',
                'quantity': random.randint(1, 100),
                'price': round(base_price + random.uniform(0.0, 5.0), 2)
            }
            orders.append(sell_order)
        
        # Shuffle orders for realistic timing
        random.shuffle(orders)
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(self.submit_order, order) for order in orders]
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 200 == 0:
                    print(f"Completed {completed}/{len(orders)} orders...")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"Market simulation completed in {total_time:.2f} seconds")
        return total_time
    
    def analyze_results(self):
        """Analyze test results and generate report"""
        if not self.results:
            print("No results to analyze")
            return
        
        successful_orders = [r for r in self.results if r['success']]
        failed_orders = [r for r in self.results if not r['success']]
        
        response_times = [r['response_time'] for r in successful_orders]
        
        print("\n" + "="*60)
        print("STRESS TEST RESULTS")
        print("="*60)
        
        print(f"Total Orders: {len(self.results)}")
        print(f"Successful Orders: {len(successful_orders)}")
        print(f"Failed Orders: {len(failed_orders)}")
        print(f"Success Rate: {len(successful_orders)/len(self.results)*100:.2f}%")
        
        if response_times:
            print(f"\nResponse Time Statistics:")
            print(f"  Average: {statistics.mean(response_times):.4f}s")
            print(f"  Median: {statistics.median(response_times):.4f}s")
            print(f"  Min: {min(response_times):.4f}s")
            print(f"  Max: {max(response_times):.4f}s")
            print(f"  95th Percentile: {sorted(response_times)[int(len(response_times)*0.95)]:.4f}s")
        
        # Count executed trades
        total_trades = sum(r.get('executed_trades', 0) for r in successful_orders)
        print(f"\nTotal Executed Trades: {total_trades}")
        
        # Error analysis
        if failed_orders:
            print(f"\nError Analysis:")
            error_types = {}
            for order in failed_orders:
                error = order.get('error', 'Unknown error')
                error_types[error] = error_types.get(error, 0) + 1
            
            for error, count in error_types.items():
                print(f"  {error}: {count}")
        
        print("="*60)
    
    def test_api_endpoints(self):
        """Test all API endpoints for functionality"""
        print("Testing API endpoints...")
        
        # Health check
        try:
            response = requests.get(f"{self.base_url}/health")
            print(f"Health check: {response.status_code}")
        except Exception as e:
            print(f"Health check failed: {e}")
        
        # Submit test order
        test_order = self.create_order_data()
        try:
            response = requests.post(f"{self.base_url}/orders", json=test_order)
            if response.status_code == 201:
                order_data = response.json()
                order_id = order_data['order_id']
                print(f"Order submission: SUCCESS (Order ID: {order_id})")
                
                # Test order status
                response = requests.get(f"{self.base_url}/orders/{order_id}?symbol={test_order['symbol']}")
                print(f"Order status: {response.status_code}")
                
                # Test market data
                response = requests.get(f"{self.base_url}/market/{test_order['symbol']}")
                print(f"Market data: {response.status_code}")
                
            else:
                print(f"Order submission: FAILED ({response.status_code})")
        except Exception as e:
            print(f"API test failed: {e}")

def main():
    """Main function to run stress tests"""
    print("Order Matching Engine Stress Tester")
    print("="*40)
    
    # Check if server is running
    tester = StressTester()
    
    try:
        response = requests.get(f"{tester.base_url}/health", timeout=5)
        if response.status_code != 200:
            print("Server is not responding properly")
            return
    except Exception as e:
        print(f"Cannot connect to server: {e}")
        print("Please make sure the Flask app is running on localhost:5000")
        return
    
    # Test API endpoints
    tester.test_api_endpoints()
    
    # Run stress tests
    print("\nStarting stress tests...")
    
    # Test 1: Concurrent orders
    print("\n1. Concurrent Order Test (1000 orders)")
    tester.run_concurrent_test(num_orders=1000, max_workers=50)
    
    # Test 2: High frequency
    print("\n2. High Frequency Test (60 seconds)")
    tester.run_high_frequency_test(duration_seconds=60, orders_per_second=50)
    
    # Test 3: Market simulation
    print("\n3. Market Simulation Test (2000 orders)")
    tester.run_market_simulation(num_orders=2000)
    
    # Analyze results
    tester.analyze_results()

if __name__ == "__main__":
    main()

