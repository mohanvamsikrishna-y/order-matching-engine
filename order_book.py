import heapq
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import threading
from enum import Enum

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class OrderNode:
    """Node for order book with price-time priority"""
    order_id: str
    user_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime
    filled_quantity: int = 0
    
    def __lt__(self, other):
        """For BUY orders: higher price first, then earlier timestamp
           For SELL orders: lower price first, then earlier timestamp"""
        if self.side == OrderSide.BUY:
            if self.price != other.price:
                return self.price > other.price  # Higher price first
            return self.timestamp < other.timestamp  # Earlier timestamp first
        else:  # SELL
            if self.price != other.price:
                return self.price < other.price  # Lower price first
            return self.timestamp < other.timestamp  # Earlier timestamp first
    
    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity
    
    def is_filled(self) -> bool:
        return self.remaining_quantity <= 0

class OrderBook:
    """Efficient order book implementation using heaps for price-time priority"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.buy_orders = []  # Max heap for buy orders (highest price first)
        self.sell_orders = []  # Min heap for sell orders (lowest price first)
        self.orders_by_id: Dict[str, OrderNode] = {}
        self.lock = threading.RLock()
    
    def add_order(self, order: OrderNode) -> bool:
        """Add a new order to the order book"""
        with self.lock:
            if order.order_id in self.orders_by_id:
                return False  # Order already exists
            
            self.orders_by_id[order.order_id] = order
            
            if order.side == OrderSide.BUY:
                heapq.heappush(self.buy_orders, order)
            else:
                heapq.heappush(self.sell_orders, order)
            
            return True
    
    def remove_order(self, order_id: str) -> bool:
        """Remove an order from the order book"""
        with self.lock:
            if order_id not in self.orders_by_id:
                return False
            
            order = self.orders_by_id[order_id]
            del self.orders_by_id[order_id]
            
            # Note: We don't actually remove from heap here for efficiency
            # Instead, we mark the order as filled and check during matching
            order.filled_quantity = order.quantity  # Mark as fully filled
            
            return True
    
    def modify_order(self, order_id: str, new_quantity: int, new_price: float) -> bool:
        """Modify an existing order's quantity and price"""
        with self.lock:
            order = self.orders_by_id.get(order_id)
            if not order:
                return False

            # Mark old order as filled (lazy removal from heaps)
            order.filled_quantity = order.quantity

            # Insert a replacement order node with updated values
            new_order = OrderNode(
                order_id=order.order_id,
                user_id=order.user_id,
                symbol=order.symbol,
                side=order.side,
                quantity=new_quantity,
                price=new_price,
                timestamp=datetime.utcnow()
            )

            # Replace mapping and push into corresponding heap
            self.orders_by_id[order_id] = new_order
            if new_order.side == OrderSide.BUY:
                heapq.heappush(self.buy_orders, new_order)
            else:
                heapq.heappush(self.sell_orders, new_order)

            return True
    
    def get_best_buy_price(self) -> Optional[float]:
        """Get the best (highest) buy price"""
        with self.lock:
            while self.buy_orders:
                order = self.buy_orders[0]
                if not order.is_filled():
                    return order.price
                heapq.heappop(self.buy_orders)
            return None
    
    def get_best_sell_price(self) -> Optional[float]:
        """Get the best (lowest) sell price"""
        with self.lock:
            while self.sell_orders:
                order = self.sell_orders[0]
                if not order.is_filled():
                    return order.price
                heapq.heappop(self.sell_orders)
            return None
    
    def get_market_depth(self, levels: int = 10) -> Dict[str, List[Tuple[float, int]]]:
        """Get market depth for both buy and sell sides"""
        with self.lock:
            buy_depth = []
            sell_depth = []
            
            # Get buy orders (highest price first)
            temp_buy = []
            while self.buy_orders and len(buy_depth) < levels:
                order = heapq.heappop(self.buy_orders)
                if not order.is_filled():
                    buy_depth.append((order.price, order.remaining_quantity))
                temp_buy.append(order)
            
            # Restore buy orders
            for order in temp_buy:
                heapq.heappush(self.buy_orders, order)
            
            # Get sell orders (lowest price first)
            temp_sell = []
            while self.sell_orders and len(sell_depth) < levels:
                order = heapq.heappop(self.sell_orders)
                if not order.is_filled():
                    sell_depth.append((order.price, order.remaining_quantity))
                temp_sell.append(order)
            
            # Restore sell orders
            for order in temp_sell:
                heapq.heappush(self.sell_orders, order)
            
            return {
                'buy': buy_depth,
                'sell': sell_depth
            }
    
    def get_order(self, order_id: str) -> Optional[OrderNode]:
        """Get order by ID"""
        return self.orders_by_id.get(order_id)
    
    def get_orders_for_user(self, user_id: str) -> List[OrderNode]:
        """Get all orders for a specific user"""
        with self.lock:
            return [order for order in self.orders_by_id.values() 
                   if order.user_id == user_id and not order.is_filled()]
    
    def cleanup_filled_orders(self):
        """Remove filled orders from heaps to maintain efficiency"""
        with self.lock:
            # Clean up buy orders
            temp_buy = []
            while self.buy_orders:
                order = heapq.heappop(self.buy_orders)
                if not order.is_filled():
                    temp_buy.append(order)
            
            for order in temp_buy:
                heapq.heappush(self.buy_orders, order)
            
            # Clean up sell orders
            temp_sell = []
            while self.sell_orders:
                order = heapq.heappop(self.sell_orders)
                if not order.is_filled():
                    temp_sell.append(order)
            
            for order in temp_sell:
                heapq.heappush(self.sell_orders, order)

