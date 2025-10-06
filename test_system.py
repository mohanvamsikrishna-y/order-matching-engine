#!/usr/bin/env python3
"""
Simple test script to verify the Order Matching Engine functionality
"""

import requests
import time
import json

def test_basic_functionality():
    """Test basic order matching functionality"""
    base_url = "http://localhost:5000"
    
    print("Testing Order Matching Engine...")
    print("="*40)
    
    # Test 1: Health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✓ Health check passed")
        else:
            print("✗ Health check failed")
            return False
    except Exception as e:
        print(f"✗ Cannot connect to server: {e}")
        return False
    
    # Test 2: Submit buy order
    print("\n2. Submitting buy order...")
    buy_order = {
        "user_id": "test_user_1",
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": 100,
        "price": 150.00
    }
    
    try:
        response = requests.post(f"{base_url}/orders", json=buy_order)
        if response.status_code == 201:
            buy_data = response.json()
            buy_order_id = buy_data['order_id']
            print(f"✓ Buy order submitted: {buy_order_id}")
        else:
            print(f"✗ Buy order failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Buy order error: {e}")
        return False
    
    # Test 3: Submit sell order (should match)
    print("\n3. Submitting matching sell order...")
    sell_order = {
        "user_id": "test_user_2",
        "symbol": "AAPL",
        "side": "SELL",
        "quantity": 100,
        "price": 150.00
    }
    
    try:
        response = requests.post(f"{base_url}/orders", json=sell_order)
        if response.status_code == 201:
            sell_data = response.json()
            sell_order_id = sell_data['order_id']
            executed_trades = sell_data.get('executed_trades', [])
            print(f"✓ Sell order submitted: {sell_order_id}")
            print(f"✓ Executed trades: {len(executed_trades)}")
        else:
            print(f"✗ Sell order failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Sell order error: {e}")
        return False
    
    # Test 4: Check order status
    print("\n4. Checking order status...")
    try:
        response = requests.get(f"{base_url}/orders/{buy_order_id}?symbol=AAPL")
        if response.status_code == 200:
            order_data = response.json()
            print(f"✓ Buy order status: {order_data['status']}")
            print(f"✓ Filled quantity: {order_data['filled_quantity']}")
        else:
            print(f"✗ Order status check failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Order status error: {e}")
    
    # Test 5: Get market data
    print("\n5. Getting market data...")
    try:
        response = requests.get(f"{base_url}/market/AAPL")
        if response.status_code == 200:
            market_data = response.json()
            print(f"✓ Market data retrieved")
            print(f"  Best bid: {market_data.get('best_bid', 'N/A')}")
            print(f"  Best ask: {market_data.get('best_ask', 'N/A')}")
        else:
            print(f"✗ Market data failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Market data error: {e}")
    
    # Test 6: Get trade history
    print("\n6. Getting trade history...")
    try:
        response = requests.get(f"{base_url}/trades?symbol=AAPL")
        if response.status_code == 200:
            trades_data = response.json()
            print(f"✓ Trade history retrieved: {trades_data['count']} trades")
        else:
            print(f"✗ Trade history failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Trade history error: {e}")
    
    # Test 7: Test order cancellation
    print("\n7. Testing order cancellation...")
    cancel_order = {
        "user_id": "test_user_3",
        "symbol": "GOOGL",
        "side": "BUY",
        "quantity": 50,
        "price": 2500.00
    }
    
    try:
        # Submit order
        response = requests.post(f"{base_url}/orders", json=cancel_order)
        if response.status_code == 201:
            cancel_data = response.json()
            cancel_order_id = cancel_data['order_id']
            print(f"✓ Order submitted for cancellation test: {cancel_order_id}")
            
            # Cancel order
            response = requests.delete(f"{base_url}/orders/{cancel_order_id}?symbol=GOOGL")
            if response.status_code == 200:
                print("✓ Order cancelled successfully")
            else:
                print(f"✗ Order cancellation failed: {response.status_code}")
        else:
            print(f"✗ Order submission for cancellation test failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Order cancellation error: {e}")
    
    print("\n" + "="*40)
    print("Basic functionality test completed!")
    return True

def test_concurrent_orders():
    """Test concurrent order submission"""
    print("\nTesting concurrent order submission...")
    print("="*40)
    
    base_url = "http://localhost:5000"
    import threading
    import random
    
    results = []
    lock = threading.Lock()
    
    def submit_random_order():
        order = {
            "user_id": f"concurrent_user_{random.randint(1, 100)}",
            "symbol": random.choice(["AAPL", "GOOGL", "MSFT"]),
            "side": random.choice(["BUY", "SELL"]),
            "quantity": random.randint(1, 100),
            "price": round(random.uniform(100.0, 300.0), 2)
        }
        
        try:
            response = requests.post(f"{base_url}/orders", json=order)
            with lock:
                results.append({
                    'success': response.status_code == 201,
                    'status_code': response.status_code,
                    'order': order
                })
        except Exception as e:
            with lock:
                results.append({
                    'success': False,
                    'error': str(e),
                    'order': order
                })
    
    # Submit 50 concurrent orders
    threads = []
    for _ in range(50):
        thread = threading.Thread(target=submit_random_order)
        thread.start()
        threads.append(thread)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Analyze results
    successful = sum(1 for r in results if r['success'])
    total = len(results)
    
    print(f"Concurrent test results:")
    print(f"  Total orders: {total}")
    print(f"  Successful: {successful}")
    print(f"  Success rate: {successful/total*100:.1f}%")
    
    if successful < total * 0.9:  # Less than 90% success
        print("⚠ Warning: Low success rate in concurrent test")
    else:
        print("✓ Concurrent test passed")

if __name__ == "__main__":
    print("Order Matching Engine Test Suite")
    print("="*50)
    
    # Run basic functionality test
    if test_basic_functionality():
        # Run concurrent test
        test_concurrent_orders()
        print("\n🎉 All tests completed successfully!")
    else:
        print("\n❌ Basic functionality test failed. Please check the server.")

