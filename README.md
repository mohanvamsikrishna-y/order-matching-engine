# Order Matching Engine

A high-performance, real-time order matching engine built with Python Flask and SQLAlchemy. This system implements a complete trading engine with efficient data structures, REST APIs, and comprehensive stress testing capabilities.

## Features

### Core Functionality
- **Real-Time Limit Order Book**: Efficient heap-based data structures for price-time priority
- **Order Matching Engine**: Automatic matching of buy/sell orders with proper priority rules
- **REST API**: Complete set of endpoints for order management and market data
- **Database Integration**: Persistent storage for all orders and trades (defaults to SQLite for local dev; supports PostgreSQL via `DATABASE_URL`)
- **Concurrent Processing**: Thread-safe operations for high-frequency trading

### Advanced Features
- **Price-Time Priority**: Orders with better prices execute first; equal prices use time priority
- **Order Management**: Submit, cancel, and modify orders
- **Market Data**: Real-time market depth and best bid/ask prices
- **Trade History**: Complete audit trail of all executed trades
- **Stress Testing**: Comprehensive testing suite for 200,000+ concurrent trades

## Architecture

### Data Structures
- **OrderBook**: Heap-based implementation for O(log n) insertions and O(1) best price lookups
- **OrderNode**: Efficient order representation with price-time priority comparison
- **MatchingEngine**: Core matching logic with thread-safe operations

### API Endpoints
- `POST /orders` - Submit new orders
- `GET /orders/{order_id}` - Get order status
- `DELETE /orders/{order_id}` - Cancel orders
- `PUT /orders/{order_id}` - Modify orders
- `GET /orders/user/{user_id}` - Get user's orders
- `GET /trades` - Get trade history
- `GET /market/{symbol}` - Get market data
- `GET /market/{symbol}/depth` - Get market depth

## Installation

### Prerequisites
- Python 3.8+
- pip
- Optional: PostgreSQL 12+ (or run with Docker)

### Setup

1. **Clone and navigate to the project directory:**
   ```bash
   cd order_matching_engine
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Database options:**

   By default, the app uses a local SQLite file `order_matching.db` (zero-config).

   To use PostgreSQL, set `DATABASE_URL` (compose file provided below):
   ```sql
   CREATE DATABASE order_matching_db;
   CREATE USER order_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE order_matching_db TO order_user;
   ```

4. **Configure environment variables:**
   Write endpoints require an API key if `API_KEY` is set (recommended). Example env:
   ```bash
   export API_KEY=devkey
   export SNAPSHOT_INTERVAL_SEC=60
   # Optional Postgres
   # export DATABASE_URL=postgresql://order_user:your_password@localhost:5432/order_matching_db
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

The server will start on `http://localhost:5000`

## Usage

### Basic Order Submission

```python
import requests

# Submit a buy order
order_data = {
    "user_id": "user123",
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 100,
    "price": 150.50
}

response = requests.post("http://localhost:5000/orders", json=order_data)
print(response.json())
```

### Order Management

```python
# Get order status
response = requests.get("http://localhost:5000/orders/order_id?symbol=AAPL")

# Cancel order
response = requests.delete("http://localhost:5000/orders/order_id?symbol=AAPL")

# Modify order
modify_data = {"quantity": 200, "price": 151.00}
response = requests.put("http://localhost:5000/orders/order_id?symbol=AAPL", json=modify_data)
```

### Market Data

```python
# Get market data
response = requests.get("http://localhost:5000/market/AAPL")

# Get market depth
response = requests.get("http://localhost:5000/market/AAPL/depth?levels=10")
```

### Demo UI

- Launch the server and open `http://localhost:5000/` to view a minimal demo UI.
- Use the form to submit BUY/SELL orders (set the `API_KEY` field if your server enforces it).
- The panel shows best bid/ask and top 10 levels of depth. Use the refresh button to update.

## Stress Testing

The included stress testing suite can simulate high-frequency trading scenarios:

```bash
python stress_test.py
```

### Test Scenarios
1. **Concurrent Orders**: 1,000 orders with 50 concurrent workers
2. **High Frequency**: 60 seconds at 50 orders/second
3. **Market Simulation**: 2,000 balanced buy/sell orders for realistic matching

### Performance Metrics
- Order submission latency
- Throughput (orders/second)
- Success rate
- Trade execution statistics
- System resource utilization

## Database Schema

### Orders Table
- `id`: Unique order identifier
- `user_id`: User who placed the order
- `symbol`: Trading symbol
- `side`: BUY or SELL
- `quantity`: Order quantity
- `price`: Order price
- `status`: Order status (PENDING, FILLED, etc.)
- `filled_quantity`: Quantity that has been filled
- `created_at`: Order creation timestamp
- `updated_at`: Last update timestamp

### Trades Table
- `id`: Unique trade identifier
- `buy_order_id`: Reference to buy order
- `sell_order_id`: Reference to sell order
- `symbol`: Trading symbol
- `quantity`: Trade quantity
- `price`: Execution price
- `executed_at`: Trade execution timestamp

## Performance Characteristics

### Time Complexity
- Order insertion: O(log n)
- Best price lookup: O(1)
- Order matching: O(k) where k is number of matching orders
- Order cancellation: O(1)

### Space Complexity
- Order book storage: O(n) where n is number of active orders
- Trade history: O(m) where m is number of executed trades

### Concurrency
- Thread-safe operations using RLock
- Concurrent order processing
- Database connection pooling
- Optimistic locking for data consistency

## Error Handling

The system includes comprehensive error handling:
- Input validation for all API endpoints
- Database transaction rollback on errors
- Graceful degradation under high load
- Detailed error messages and logging

## Monitoring and Logging

- Health check endpoint (`/health`)
- Request/response logging
- Performance metrics collection
- Error tracking and reporting

## Scalability Considerations

- Horizontal scaling with load balancers
- Database read replicas for market data
- Redis caching for frequently accessed data
- Microservices architecture for different components

## Security Features

- Input sanitization and validation
- SQL injection prevention
- Rate limiting (can be added)
- Authentication/authorization (can be added)

## Future Enhancements

- WebSocket support for real-time updates
- Advanced order types (stop-loss, trailing stops)
- Risk management and position limits
- Market data streaming
- Order book snapshots
- Historical data analysis

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Docker

Build and run the API (SQLite by default):

```bash
docker build -t order-matching-engine .
docker run -p 5000:5000 -e API_KEY=devkey order-matching-engine
```

Use PostgreSQL with Docker Compose for the DB:

```bash
docker compose up -d db
docker run -p 5000:5000 \
  -e API_KEY=devkey \
  -e DATABASE_URL=postgresql://order_user:your_password@host.docker.internal:5432/order_matching_db \
  order-matching-engine
```

## Support

For questions or issues, please create an issue in the repository or contact the development team.

