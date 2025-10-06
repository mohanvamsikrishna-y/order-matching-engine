import os
import json

# Configure environment BEFORE importing app
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SNAPSHOT_INTERVAL_SEC'] = '0'
os.environ['API_KEY'] = 'testkey'

from app import create_app  # noqa: E402
from models import db  # noqa: E402


def make_app():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def test_health():
    app = make_app()
    client = app.test_client()
    res = client.get('/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'healthy'


def test_write_requires_api_key():
    app = make_app()
    client = app.test_client()
    payload = {
        'user_id': 'u1', 'symbol': 'AAPL', 'side': 'BUY', 'quantity': 1, 'price': 10.0
    }
    res = client.post('/orders', json=payload)
    assert res.status_code == 401


def test_order_match_flow():
    app = make_app()
    client = app.test_client()
    headers = {'X-API-Key': 'testkey'}

    buy = {
        'user_id': 'u1', 'symbol': 'AAPL', 'side': 'BUY', 'quantity': 5, 'price': 100.0
    }
    res_buy = client.post('/orders', json=buy, headers=headers)
    assert res_buy.status_code == 201
    buy_id = res_buy.get_json()['order_id']

    sell = {
        'user_id': 'u2', 'symbol': 'AAPL', 'side': 'SELL', 'quantity': 5, 'price': 100.0
    }
    res_sell = client.post('/orders', json=sell, headers=headers)
    assert res_sell.status_code == 201
    trades = res_sell.get_json().get('executed_trades', [])
    assert len(trades) == 1

    # Verify order status is FILLED
    res_status = client.get(f'/orders/{buy_id}?symbol=AAPL')
    assert res_status.status_code == 200
    status = res_status.get_json()
    assert status['status'] in ('FILLED', 'filled', 'FILLED')
    assert status['filled_quantity'] == 5


