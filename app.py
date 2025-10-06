from flask import Flask, request, jsonify, Blueprint
import os
import argparse
import time
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
import threading
from config import Config
from models import db, Order, Trade, OrderStatus, OrderSide
from matching_engine import matching_engine
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(get_remote_address, default_limits=["200 per minute"])  # module-level so decorators can reference it
bp = Blueprint('api', __name__)

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize database
    db.init_app(app)
    Migrate(app, db)

    # Rate limiting and API key
    limiter.init_app(app)
    app.config['API_KEY'] = os.environ.get('API_KEY')
    
    @app.before_request
    def _enforce_api_key():
        # Require API key only for mutating endpoints
        if request.method in ('POST', 'PUT', 'DELETE'):
            expected = app.config.get('API_KEY')
            if expected:
                provided = request.headers.get('X-API-Key') or request.args.get('api_key')
                if provided != expected:
                    return jsonify({'error': 'Unauthorized'}), 401

    # Structured request logging and latency metrics
    @app.before_request
    def _start_timer():
        request._start_time = time.time()

    @app.after_request
    def _log_request(response):
        try:
            duration = (time.time() - getattr(request, '_start_time', time.time()))
            app.logger.info({
                'method': request.method,
                'path': request.path,
                'status': response.status_code,
                'duration_ms': int(duration * 1000),
                'remote_addr': request.remote_addr,
            })
        except Exception:
            pass
        return response

    # Create tables
    with app.app_context():
        db.create_all()
        # Rebuild in-memory order books and start snapshots
        from matching_engine import matching_engine
        loaded = matching_engine.rebuild_from_db()
        app.logger.info({'event': 'rebuild_from_db', 'loaded_orders': loaded})
        matching_engine.start_snapshot_scheduler()

    # Register API blueprint
    app.register_blueprint(bp)
    
    return app

@bp.route('/', methods=['GET'])
def index():
    """Root endpoint with quick links/documentation hint"""
    return jsonify({
        'service': 'Order Matching Engine',
        'message': 'Welcome. See available endpoints below.',
        'endpoints': {
            'health': '/health',
            'submit_order': 'POST /orders',
            'order_status': 'GET /orders/<order_id>?symbol=<SYMBOL>',
            'cancel_order': 'DELETE /orders/<order_id>?symbol=<SYMBOL>',
            'modify_order': 'PUT /orders/<order_id>?symbol=<SYMBOL>',
            'user_orders': 'GET /orders/user/<user_id>?symbol=<SYMBOL>&status=<STATUS>',
            'trades': 'GET /trades?symbol=<SYMBOL>&user_id=<USER_ID>&limit=<N>',
            'market': 'GET /market/<symbol>',
            'market_depth': 'GET /market/<symbol>/depth?levels=<N>'
        }
    })

@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'Order Matching Engine'
    })

@bp.route('/orders', methods=['POST'])
@limiter.limit("60/minute")
def submit_order():
    """Submit a new order"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['user_id', 'symbol', 'side', 'quantity', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate data types and values
        if data['side'] not in ['BUY', 'SELL']:
            return jsonify({'error': 'Side must be BUY or SELL'}), 400
        
        if data['quantity'] <= 0:
            return jsonify({'error': 'Quantity must be positive'}), 400
        
        if data['price'] <= 0:
            return jsonify({'error': 'Price must be positive'}), 400
        
        # Generate order ID
        order_id = str(uuid.uuid4())
        
        # Create order data
        order_data = {
            'order_id': order_id,
            'user_id': data['user_id'],
            'symbol': data['symbol'].upper(),
            'side': data['side'],
            'quantity': int(data['quantity']),
            'price': float(data['price'])
        }
        
        # Create order in database
        order = Order(
            id=order_id,
            user_id=data['user_id'],
            symbol=data['symbol'].upper(),
            side=OrderSide(data['side']),
            quantity=int(data['quantity']),
            price=float(data['price']),
            status=OrderStatus.PENDING
        )
        
        db.session.add(order)
        db.session.commit()
        
        # Submit to matching engine
        success, message, executed_trades = matching_engine.submit_order(order_data)
        
        if success:
            return jsonify({
                'message': message,
                'order_id': order_id,
                'executed_trades': executed_trades,
                'status': 'success'
            }), 201
        else:
            return jsonify({
                'error': message,
                'order_id': order_id,
                'status': 'failed'
            }), 400
            
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@bp.route('/orders/<order_id>', methods=['GET'])
def get_order_status(order_id):
    """Get order status"""
    try:
        # Try to get from matching engine first
        symbol = request.args.get('symbol')
        if symbol:
            order_status = matching_engine.get_order_status(order_id, symbol.upper())
            if order_status:
                return jsonify(order_status)
        
        # Fallback to database
        order = Order.query.get(order_id)
        if order:
            return jsonify(order.to_dict())
        else:
            return jsonify({'error': 'Order not found'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@bp.route('/orders/<order_id>', methods=['DELETE'])
@limiter.limit("60/minute")
def cancel_order():
    """Cancel an order"""
    try:
        order_id = request.view_args['order_id']
        symbol = request.args.get('symbol')
        
        if not symbol:
            return jsonify({'error': 'Symbol parameter is required'}), 400
        
        success, message = matching_engine.cancel_order(order_id, symbol.upper())
        
        if success:
            return jsonify({'message': message, 'status': 'success'})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@bp.route('/orders/<order_id>', methods=['PUT'])
@limiter.limit("60/minute")
def modify_order():
    """Modify an existing order"""
    try:
        order_id = request.view_args['order_id']
        data = request.get_json()
        
        if not data or 'quantity' not in data or 'price' not in data:
            return jsonify({'error': 'Quantity and price are required'}), 400
        
        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({'error': 'Symbol parameter is required'}), 400
        
        success, message = matching_engine.modify_order(
            order_id, 
            symbol.upper(), 
            int(data['quantity']), 
            float(data['price'])
        )
        
        if success:
            return jsonify({'message': message, 'status': 'success'})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@bp.route('/orders/user/<user_id>', methods=['GET'])
def get_user_orders(user_id):
    """Get all orders for a user"""
    try:
        symbol = request.args.get('symbol')
        status = request.args.get('status')
        
        query = Order.query.filter_by(user_id=user_id)
        
        if symbol:
            query = query.filter_by(symbol=symbol.upper())
        
        if status:
            query = query.filter_by(status=OrderStatus(status))
        
        orders = query.order_by(Order.created_at.desc()).all()
        
        return jsonify({
            'orders': [order.to_dict() for order in orders],
            'count': len(orders)
        })
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@bp.route('/trades', methods=['GET'])
def get_trades():
    """Get trade history"""
    try:
        symbol = request.args.get('symbol')
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 100))
        
        query = Trade.query
        
        if symbol:
            query = query.filter_by(symbol=symbol.upper())
        
        if user_id:
            # Get trades where user was either buyer or seller
            query = query.join(Order, Trade.buy_order_id == Order.id).filter(
                Order.user_id == user_id
            ).union(
                query.join(Order, Trade.sell_order_id == Order.id).filter(
                    Order.user_id == user_id
                )
            )
        
        trades = query.order_by(Trade.executed_at.desc()).limit(limit).all()
        
        return jsonify({
            'trades': [trade.to_dict() for trade in trades],
            'count': len(trades)
        })
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@bp.route('/market/<symbol>', methods=['GET'])
def get_market_data(symbol):
    """Get market data for a symbol"""
    try:
        market_data = matching_engine.get_market_data(symbol.upper())
        return jsonify(market_data)
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@bp.route('/market/<symbol>/depth', methods=['GET'])
def get_market_depth(symbol):
    """Get market depth for a symbol"""
    try:
        levels = int(request.args.get('levels', 10))
        order_book = matching_engine.get_order_book(symbol.upper())
        depth = order_book.get_market_depth(levels)
        
        return jsonify({
            'symbol': symbol.upper(),
            'depth': depth,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@bp.route('/market/<symbol>/stream', methods=['GET'])
def market_stream(symbol):
    """Simple Server-Sent Events (SSE) stream for market data."""
    from flask import Response
    import json as _json
    import time as _time

    def event_stream():
        while True:
            data = matching_engine.get_market_data(symbol.upper())
            yield f"data: {_json.dumps(data)}\n\n"
            _time.sleep(1)

    headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
    }
    return Response(event_stream(), headers=headers)

@bp.app_errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@bp.app_errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app = create_app()
    parser = argparse.ArgumentParser(description='Order Matching Engine API Server')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 5000)), help='Port to run the server on')
    args = parser.parse_args()
    app.run(host='0.0.0.0', port=args.port, debug=True, threaded=True)

