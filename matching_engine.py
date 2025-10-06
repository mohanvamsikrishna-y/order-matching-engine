from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
import threading
import heapq
import json
import os
from order_book import OrderBook, OrderNode, OrderSide
from models import db, Order, Trade, OrderStatus

class MatchingEngine:
    """Core order matching engine with price-time priority"""
    
    def __init__(self):
        self.order_books: dict = {}  # symbol -> OrderBook
        self.lock = threading.RLock()
        self._snapshot_thread: Optional[threading.Timer] = None
        self._snapshot_interval_sec: int = int(os.environ.get('SNAPSHOT_INTERVAL_SEC', '60'))
        self._snapshot_dir: str = os.path.join(os.getcwd(), 'snapshots')
    
    def get_order_book(self, symbol: str) -> OrderBook:
        """Get or create order book for a symbol"""
        with self.lock:
            if symbol not in self.order_books:
                self.order_books[symbol] = OrderBook(symbol)
            return self.order_books[symbol]

    def rebuild_from_db(self) -> int:
        """Rebuild in-memory order books from database for active orders.
        Returns count of orders loaded."""
        count = 0
        try:
            active_orders = Order.query.filter(Order.status.in_([OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED])).all()
            for o in active_orders:
                side_value = o.side.value if hasattr(o.side, 'value') else str(o.side)
                order_node = OrderNode(
                    order_id=o.id,
                    user_id=o.user_id,
                    symbol=o.symbol,
                    side=OrderSide(side_value),
                    quantity=o.quantity,
                    price=o.price,
                    timestamp=o.created_at or datetime.utcnow(),
                )
                order_node.filled_quantity = o.filled_quantity or 0
                ob = self.get_order_book(o.symbol)
                ob.add_order(order_node)
                count += 1
            return count
        except Exception as e:
            print(f"Error rebuilding order books: {str(e)}")
            return count

    def _serialize(self) -> Dict[str, Any]:
        data: Dict[str, Any] = { 'symbols': {} }
        for symbol, ob in self.order_books.items():
            depth = ob.get_market_depth(levels=1000)
            orders = []
            for oid, onode in ob.orders_by_id.items():
                orders.append({
                    'order_id': onode.order_id,
                    'user_id': onode.user_id,
                    'symbol': onode.symbol,
                    'side': onode.side.value,
                    'quantity': onode.quantity,
                    'price': onode.price,
                    'filled_quantity': onode.filled_quantity,
                    'timestamp': onode.timestamp.isoformat(),
                })
            data['symbols'][symbol] = {
                'best_bid': ob.get_best_buy_price(),
                'best_ask': ob.get_best_sell_price(),
                'depth': depth,
                'orders': orders,
            }
        data['timestamp'] = datetime.utcnow().isoformat()
        return data

    def snapshot_to_disk(self) -> Optional[str]:
        """Write current order books to a JSON snapshot file."""
        try:
            os.makedirs(self._snapshot_dir, exist_ok=True)
            payload = self._serialize()
            filename = os.path.join(self._snapshot_dir, f"order_books_{int(datetime.utcnow().timestamp())}.json")
            with open(filename, 'w') as f:
                json.dump(payload, f, separators=(',', ':'))
            return filename
        except Exception as e:
            print(f"Error writing snapshot: {str(e)}")
            return None

    def _schedule_next_snapshot(self):
        if self._snapshot_interval_sec <= 0:
            return
        self._snapshot_thread = threading.Timer(self._snapshot_interval_sec, self._snapshot_tick)
        self._snapshot_thread.daemon = True
        self._snapshot_thread.start()

    def _snapshot_tick(self):
        try:
            self.snapshot_to_disk()
        finally:
            self._schedule_next_snapshot()

    def start_snapshot_scheduler(self):
        """Begin periodic snapshots based on SNAPSHOT_INTERVAL_SEC env var."""
        if self._snapshot_thread is None:
            self._schedule_next_snapshot()
    
    def submit_order(self, order_data: dict) -> Tuple[bool, str, List[dict]]:
        """
        Submit a new order and attempt to match it
        Returns: (success, message, executed_trades)
        """
        try:
            # Create order node
            order_node = OrderNode(
                order_id=order_data['order_id'],
                user_id=order_data['user_id'],
                symbol=order_data['symbol'],
                side=OrderSide(order_data['side']),
                quantity=order_data['quantity'],
                price=order_data['price'],
                timestamp=datetime.utcnow()
            )
            
            # Get order book for this symbol
            order_book = self.get_order_book(order_data['symbol'])
            
            # Add order to book
            if not order_book.add_order(order_node):
                return False, "Order already exists", []
            
            # Attempt to match the order
            executed_trades = self._match_order(order_book, order_node)
            
            return True, "Order submitted successfully", executed_trades
            
        except Exception as e:
            return False, f"Error submitting order: {str(e)}", []
    
    def _match_order(self, order_book: OrderBook, incoming_order: OrderNode) -> List[dict]:
        """Match an incoming order against the order book"""
        executed_trades = []
        
        if incoming_order.side == OrderSide.BUY:
            executed_trades = self._match_buy_order(order_book, incoming_order)
        else:
            executed_trades = self._match_sell_order(order_book, incoming_order)
        
        return executed_trades
    
    def _match_buy_order(self, order_book: OrderBook, buy_order: OrderNode) -> List[dict]:
        """Match a buy order against sell orders"""
        executed_trades = []
        
        while (not buy_order.is_filled() and 
               order_book.sell_orders and 
               order_book.sell_orders[0].price <= buy_order.price):
            
            sell_order = order_book.sell_orders[0]
            
            if sell_order.is_filled():
                heapq.heappop(order_book.sell_orders)
                continue
            
            # Calculate trade quantity
            trade_quantity = min(buy_order.remaining_quantity, sell_order.remaining_quantity)
            trade_price = sell_order.price  # Sell order price (market maker)
            
            # Execute the trade
            trade_data = self._execute_trade(buy_order, sell_order, trade_quantity, trade_price)
            if trade_data:
                executed_trades.append(trade_data)
            
            # Update quantities
            buy_order.filled_quantity += trade_quantity
            sell_order.filled_quantity += trade_quantity
            
            # Remove fully filled sell order
            if sell_order.is_filled():
                heapq.heappop(order_book.sell_orders)
        
        return executed_trades
    
    def _match_sell_order(self, order_book: OrderBook, sell_order: OrderNode) -> List[dict]:
        """Match a sell order against buy orders"""
        executed_trades = []
        
        while (not sell_order.is_filled() and 
               order_book.buy_orders and 
               order_book.buy_orders[0].price >= sell_order.price):
            
            buy_order = order_book.buy_orders[0]
            
            if buy_order.is_filled():
                heapq.heappop(order_book.buy_orders)
                continue
            
            # Calculate trade quantity
            trade_quantity = min(sell_order.remaining_quantity, buy_order.remaining_quantity)
            trade_price = buy_order.price  # Buy order price (market maker)
            
            # Execute the trade
            trade_data = self._execute_trade(buy_order, sell_order, trade_quantity, trade_price)
            if trade_data:
                executed_trades.append(trade_data)
            
            # Update quantities
            sell_order.filled_quantity += trade_quantity
            buy_order.filled_quantity += trade_quantity
            
            # Remove fully filled buy order
            if buy_order.is_filled():
                heapq.heappop(order_book.buy_orders)
        
        return executed_trades
    
    def _execute_trade(self, buy_order: OrderNode, sell_order: OrderNode, 
                      quantity: int, price: float) -> Optional[dict]:
        """Execute a trade between two orders"""
        try:
            # Create trade record in database
            trade = Trade(
                buy_order_id=buy_order.order_id,
                sell_order_id=sell_order.order_id,
                symbol=buy_order.symbol,
                quantity=quantity,
                price=price
            )
            
            db.session.add(trade)
            
            # Update order statuses in database
            self._update_order_status(buy_order)
            self._update_order_status(sell_order)
            
            db.session.commit()
            
            return {
                'trade_id': trade.id,
                'buy_order_id': buy_order.order_id,
                'sell_order_id': sell_order.order_id,
                'symbol': buy_order.symbol,
                'quantity': quantity,
                'price': price,
                'executed_at': trade.executed_at.isoformat()
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"Error executing trade: {str(e)}")
            return None
    
    def _update_order_status(self, order_node: OrderNode):
        """Update order status in database"""
        try:
            order = Order.query.get(order_node.order_id)
            if order:
                order.filled_quantity = order_node.filled_quantity
                
                if order_node.is_filled():
                    order.status = OrderStatus.FILLED
                elif order_node.filled_quantity > 0:
                    order.status = OrderStatus.PARTIALLY_FILLED
                else:
                    order.status = OrderStatus.PENDING
                
                order.updated_at = datetime.utcnow()
        except Exception as e:
            print(f"Error updating order status: {str(e)}")
    
    def cancel_order(self, order_id: str, symbol: str) -> Tuple[bool, str]:
        """Cancel an order"""
        try:
            order_book = self.get_order_book(symbol)
            
            if order_book.remove_order(order_id):
                # Update database
                order = Order.query.get(order_id)
                if order:
                    order.status = OrderStatus.CANCELLED
                    order.updated_at = datetime.utcnow()
                    db.session.commit()
                
                return True, "Order cancelled successfully"
            else:
                return False, "Order not found or already filled"
                
        except Exception as e:
            return False, f"Error cancelling order: {str(e)}"
    
    def modify_order(self, order_id: str, symbol: str, new_quantity: int, new_price: float) -> Tuple[bool, str]:
        """Modify an existing order"""
        try:
            order_book = self.get_order_book(symbol)
            
            if order_book.modify_order(order_id, new_quantity, new_price):
                # Update database
                order = Order.query.get(order_id)
                if order:
                    order.quantity = new_quantity
                    order.price = new_price
                    order.updated_at = datetime.utcnow()
                    db.session.commit()
                
                return True, "Order modified successfully"
            else:
                return False, "Order not found or already filled"
                
        except Exception as e:
            return False, f"Error modifying order: {str(e)}"
    
    def get_order_status(self, order_id: str, symbol: str) -> Optional[dict]:
        """Get order status"""
        try:
            order_book = self.get_order_book(symbol)
            order_node = order_book.get_order(order_id)
            
            if order_node:
                return {
                    'order_id': order_node.order_id,
                    'user_id': order_node.user_id,
                    'symbol': order_node.symbol,
                    'side': order_node.side.value,
                    'quantity': order_node.quantity,
                    'price': order_node.price,
                    'filled_quantity': order_node.filled_quantity,
                    'remaining_quantity': order_node.remaining_quantity,
                    'status': 'FILLED' if order_node.is_filled() else 'PARTIALLY_FILLED' if order_node.filled_quantity > 0 else 'PENDING',
                    'timestamp': order_node.timestamp.isoformat()
                }
            else:
                # Check database for historical orders
                order = Order.query.get(order_id)
                if order:
                    return order.to_dict()
                return None
                
        except Exception as e:
            print(f"Error getting order status: {str(e)}")
            return None
    
    def get_market_data(self, symbol: str) -> dict:
        """Get market data for a symbol"""
        try:
            order_book = self.get_order_book(symbol)
            depth = order_book.get_market_depth()
            
            return {
                'symbol': symbol,
                'best_bid': order_book.get_best_buy_price(),
                'best_ask': order_book.get_best_sell_price(),
                'market_depth': depth,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {'error': f"Error getting market data: {str(e)}"}

# Global matching engine instance
matching_engine = MatchingEngine()
