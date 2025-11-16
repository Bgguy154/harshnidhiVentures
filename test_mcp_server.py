import pytest
import time
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from mcp_server import app, TickerResponse, OHLCVResponse, data_cache

# Pytest fixture to run the FastAPI app asynchronously for testing
@pytest.fixture(scope="module")
async def client():
    """Async client for testing FastAPI endpoints."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# --- MOCK DATA ---

MOCK_TICKER_DATA = {
    'symbol': 'BTC/USDT',
    'last': 65000.50,
    'bid': 64999.00,
    'ask': 65001.00,
    'timestamp': 1678886400000,
    'info': {'a': 1, 'b': 2}
}

# CCXT OHLCV format: [timestamp, open, high, low, close, volume]
MOCK_OHLCV_DATA = [
    [1678886400000, 60000.0, 60500.0, 59900.0, 60400.0, 10.5],
    [1678890000000, 60400.0, 60700.0, 60300.0, 60650.0, 8.2],
]

# --- UNIT TESTS ---

@pytest.mark.asyncio
async def test_get_ticker_success(client: AsyncClient):
    """Tests successful fetching and correct Pydantic serialization for /ticker."""
    # We mock the external CCXT method to return our predictable test data
    with patch('mcp_server.EXCHANGE.fetch_ticker', new=AsyncMock(return_value=MOCK_TICKER_DATA)) as mock_fetch:
        # Ensure cache is empty before the test
        data_cache._cache.clear()

        # 1. First call (Cache Miss)
        response = await client.get("/ticker/BTC/USDT")
        assert response.status_code == 200
        assert mock_fetch.call_count == 1
        
        data = response.json()
        TickerResponse.model_validate(data) # Validate response shape
        assert data['symbol'] == 'BTC/USDT'
        assert data['last'] == 65000.50

@pytest.mark.asyncio
@patch('mcp_server.time.time', side_effect=[100, 101, 106, 107]) # Mock time for cache test
async def test_get_ticker_caching_and_expiry(mock_time, client: AsyncClient):
    """Tests the cache hit and cache expiration logic."""
    from ccxt.base.exchange import ExchangeError
    
    # Mock CCXT to return different data on subsequent *actual* fetches
    mock_ticker_data_v1 = dict(MOCK_TICKER_DATA, last=60000.0)
    mock_ticker_data_v2 = dict(MOCK_TICKER_DATA, last=70000.0)

    # Sequence of mock returns for fetch_ticker
    mock_fetch = AsyncMock(side_effect=[mock_ticker_data_v1, mock_ticker_data_v2])

    with patch('mcp_server.EXCHANGE.fetch_ticker', new=mock_fetch):
        data_cache._cache.clear()
        
        # 1. First call (t=100). Cache miss. Calls CCXT. Stores v1.
        response1 = await client.get("/ticker/ETH/USDT")
        assert response1.status_code == 200
        assert response1.json()['last'] == 60000.0
        assert mock_fetch.call_count == 1

        # 2. Second call (t=101). Cache hit (TTL=5s). Does NOT call CCXT. Returns v1.
        response2 = await client.get("/ticker/ETH/USDT")
        assert response2.status_code == 200
        assert response2.json()['last'] == 60000.0
        assert mock_fetch.call_count == 1 # Still 1

        # 3. Third call (t=106). Cache expired. Calls CCXT. Stores v2.
        response3 = await client.get("/ticker/ETH/USDT")
        assert response3.status_code == 200
        assert response3.json()['last'] == 70000.0
        assert mock_fetch.call_count == 2 # Called again

        # 4. Fourth call (t=107). Cache hit. Does NOT call CCXT. Returns v2.
        response4 = await client.get("/ticker/ETH/USDT")
        assert response4.status_code == 200
        assert response4.json()['last'] == 70000.0
        assert mock_fetch.call_count == 2

@pytest.mark.asyncio
async def test_get_ticker_symbol_not_found(client: AsyncClient):
    """Tests error handling for a symbol not supported by the exchange."""
    from ccxt.base.exchange import BadSymbol
    # CCXT raises a BadSymbol exception for unsupported symbols
    with patch('mcp_server.EXCHANGE.fetch_ticker', new=AsyncMock(side_effect=BadSymbol('The symbol XYZ/ABC is not supported'))):
        response = await client.get("/ticker/XYZ/ABC")
        assert response.status_code == 404
        assert "Symbol XYZ/ABC not found" in response.json()['detail']

@pytest.mark.asyncio
async def test_get_ohlcv_success(client: AsyncClient):
    """Tests successful fetching and correct Pydantic serialization for /ohlcv."""
    with patch('mcp_server.EXCHANGE.fetch_ohlcv', new=AsyncMock(return_value=MOCK_OHLCV_DATA)) as mock_fetch:
        response = await client.get("/ohlcv/BTC/USDT?timeframe=1h&limit=2")
        assert response.status_code == 200
        assert mock_fetch.call_count == 1
        
        data = response.json()
        OHLCVResponse.model_validate(data) # Validate response shape
        assert data['symbol'] == 'BTC/USDT'
        assert len(data['data']) == 2
        assert data['data'][0]['open'] == 60000.0
        assert data['data'][1]['volume'] == 8.2

@pytest.mark.asyncio
async def test_get_ohlcv_invalid_limit_and_timeframe(client: AsyncClient):
    """Tests request validation for limit and timeframe."""
    
    # 1. Invalid limit
    response_limit = await client.get("/ohlcv/BTC/USDT?limit=1001")
    assert response_limit.status_code == 400
    assert "Limit must not exceed 1000" in response_limit.json()['detail']

    # 2. Invalid timeframe
    response_tf = await client.get("/ohlcv/BTC/USDT?timeframe=20min")
    assert response_tf.status_code == 400
    assert "Invalid timeframe" in response_tf.json()['detail']