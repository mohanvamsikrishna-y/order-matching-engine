from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum
import uuid

db = SQLAlchemy()

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class Order(db.Model):
    """Order model for storing order information in the database"""
    __tablename__ = 'orders'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(50), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    side = db.Column(db.Enum(OrderSide), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PENDING)
    filled_quantity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Order {self.id}: {self.side} {self.quantity} {self.symbol} @ {self.price}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': self.quantity,
            'price': self.price,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Trade(db.Model):
    """Trade model for storing executed trades"""
    __tablename__ = 'trades'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    buy_order_id = db.Column(db.String(36), db.ForeignKey('orders.id'), nullable=False)
    sell_order_id = db.Column(db.String(36), db.ForeignKey('orders.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    buy_order = db.relationship('Order', foreign_keys=[buy_order_id], backref='buy_trades')
    sell_order = db.relationship('Order', foreign_keys=[sell_order_id], backref='sell_trades')
    
    def __repr__(self):
        return f'<Trade {self.id}: {self.quantity} {self.symbol} @ {self.price}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'buy_order_id': self.buy_order_id,
            'sell_order_id': self.sell_order_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'executed_at': self.executed_at.isoformat()
        }

