import time
import ccxt.async_support as ccxt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# --- 1. CONFIGURATION AND INITIALIZATION ---

# Initialize the CCXT exchange client globally (using Binance as a reference)
# Note: For production use, credentials and settings should be managed via environment variables.
EXCHANGE_ID = 'binance'
EXCHANGE = getattr(ccxt, EXCHANGE_ID)({'enableRateLimit': True})

# --- 2. DATA MODELS (Pydantic) ---

class TickerResponse(BaseModel):
    """Schema for real-time ticker data response."""
    symbol: str = Field(..., example="BTC/USDT")
    last: float = Field(..., example=65000.50)
    bid: float = Field(..., example=65000.00)
    ask: float = Field(..., example=65001.00)
    timestamp: int = Field(..., example=1678886400000, description="Timestamp in milliseconds")
    info: Dict[str, Any] = Field(..., description="Original raw response from the exchange")

class OHLCVData(BaseModel):
    """Schema for a single OHLCV (Candlestick) bar."""
    timestamp: int = Field(..., example=1678886400000)
    open: float = Field(..., example=60000.00)
    high: float = Field(..., example=60500.00)
    low: float = Field(..., example=59900.00)
    close: float = Field(..., example=60400.00)
    volume: float = Field(..., example=10.5)

class OHLCVResponse(BaseModel):
    """Schema for historical OHLCV data response."""
    symbol: str = Field(..., example="BTC/USDT")
    timeframe: str = Field(..., example="1h")
    data: List[OHLCVData]

# --- 3. CACHING UTILITY ---

class SimpleCache:
    """In-memory cache with a Time-To-Live (TTL) mechanism."""
    def __init__(self, ttl_seconds: int = 5):
        self._cache: Dict[str, Any] = {}
        self._ttl = ttl_seconds

    def _is_expired(self, timestamp: float) -> bool:
        """Checks if the cached data is past its TTL."""
        return (time.time() - timestamp) > self._ttl

    def get(self, key: str) -> Optional[Any]:
        """Retrieves cached data if not expired."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if not self._is_expired(timestamp):
                print(f"Cache hit for key: {key}")
                return data
            else:
                print(f"Cache expired for key: {key}")
                del self._cache[key]
        print(f"Cache miss for key: {key}")
        return None

    def set(self, key: str, data: Any):
        """Stores data with the current timestamp."""
        self._cache[key] = (data, time.time())
        print(f"Cache set for key: {key}")

# Initialize the cache with a 5-second TTL for real-time data
data_cache = SimpleCache(ttl_seconds=5)

# --- 4. FASTAPI APPLICATION ---

app = FastAPI(
    title="Cryptocurrency Market Data Platform (MCP)",
    description="Real-time and historical market data server powered by CCXT.",
    version="1.0.0"
)

# --- 5. ENDPOINTS AND LOGIC ---

@app.on_event("shutdown")
async def shutdown_event():
    """Closes the CCXT connection pool on shutdown."""
    await EXCHANGE.close()

@app.get("/ticker/{symbol}", response_model=TickerResponse)
async def get_ticker(symbol: str):
    """
    Retrieves the real-time ticker data (last price, bid/ask) for a specific symbol.
    Uses a 5-second in-memory cache to reduce external API calls.
    """
    cache_key = f"ticker:{symbol}"
    cached_data = data_cache.get(cache_key)

    if cached_data:
        return cached_data

    try:
        # CCXT symbols are typically uppercase, e.g., 'BTC/USDT'
        ticker = await EXCHANGE.fetch_ticker(symbol.upper())

        response_data = TickerResponse(
            symbol=ticker['symbol'],
            last=ticker['last'],
            bid=ticker['bid'],
            ask=ticker['ask'],
            timestamp=ticker['timestamp'],
            info=ticker['info']
        )
        
        data_cache.set(cache_key, response_data)
        return response_data

    except ccxt.ExchangeError as e:
        raise HTTPException(
            status_code=500, detail=f"Exchange error while fetching ticker for {symbol}: {str(e)}"
        )
    except Exception as e:
        # Handle SymbolNotFound, BadSymbol, etc. from CCXT
        if 'symbol is not supported' in str(e).lower() or 'does not exist' in str(e).lower():
            raise HTTPException(
                status_code=404, detail=f"Symbol {symbol} not found on {EXCHANGE_ID}"
            )
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.get("/ohlcv/{symbol}", response_model=OHLCVResponse)
async def get_ohlcv(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 100
):
    """
    Retrieves historical OHLCV (candlestick) data for a given symbol and timeframe.
    Historical data is not cached by default in this example.
    """
    if limit > 1000:
        raise HTTPException(status_code=400, detail="Limit must not exceed 1000 for performance.")
    
    if timeframe not in ['1m', '5m', '15m', '1h', '4h', '1d']:
        raise HTTPException(status_code=400, detail="Invalid timeframe. Supported: 1m, 5m, 15m, 1h, 4h, 1d.")

    try:
        # OHLCV format: [timestamp, open, high, low, close, volume]
        ohlcv_data = await EXCHANGE.fetch_ohlcv(
            symbol=symbol.upper(),
            timeframe=timeframe,
            limit=limit
        )

        # Convert the CCXT list of lists into a list of Pydantic models
        formatted_data = [
            OHLCVData(
                timestamp=bar[0],
                open=bar[1],
                high=bar[2],
                low=bar[3],
                close=bar[4],
                volume=bar[5]
            )
            for bar in ohlcv_data
        ]

        return OHLCVResponse(
            symbol=symbol.upper(),
            timeframe=timeframe,
            data=formatted_data
        )

    except ccxt.ExchangeError as e:
        raise HTTPException(
            status_code=500, detail=f"Exchange error while fetching OHLCV for {symbol}: {str(e)}"
        )
    except Exception as e:
        if 'symbol is not supported' in str(e).lower() or 'does not exist' in str(e).lower():
            raise HTTPException(
                status_code=404, detail=f"Symbol {symbol} not found on {EXCHANGE_ID}"
            )
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# To run this file, you would typically use: uvicorn mcp_server:app --reload
# See README.md for complete instructions.