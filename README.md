Cryptocurrency Market Data Platform (MCP) Server

This project implements a robust, structured market data server using Python, FastAPI, and the CCXT library for real-time and historical cryptocurrency market data retrieval.

Key Features

FastAPI: Provides a modern, asynchronous framework for high-performance API endpoints.

CCXT: Used as the backend to connect to major cryptocurrency exchanges (e.g., Binance, in this example).

Real-time Ticker: /ticker/{symbol} endpoint with a 5-second in-memory Time-To-Live (TTL) cache to reduce external API calls.

Historical Data: /ohlcv/{symbol} endpoint for retrieving candlestick data.

Robust Testing: Separate unit tests that mock the external CCXT dependency to ensure rapid, reliable validation.

Prerequisites

You need Python 3.8+ installed on your system.

Setup and Installation

Clone the repository (if applicable) and navigate to the project directory.

Create and activate a virtual environment:

python -m venv venv
source venv/bin/activate  # On Linux/macOS
# .\venv\Scripts\activate  # On Windows


Install dependencies:

pip install fastapi uvicorn ccxt pydantic pytest httpx pytest-asyncio


Running the Server

Use uvicorn to start the FastAPI application:

uvicorn mcp_server:app --reload


The server will start at http://127.0.0.1:8000. You can access the automatic interactive documentation (Swagger UI) at http://127.0.0.1:8000/docs.

API Endpoints

Method

Endpoint

Description

GET

/ticker/{symbol}

Get real-time price data (e.g., /ticker/BTC/USDT)

GET

/ohlcv/{symbol}

Get historical candlestick data (e.g., /ohlcv/ETH/USDT?timeframe=1h&limit=100)

Running Tests

The test_mcp_server.py file contains unit tests to validate the endpoints, including success cases, error handling, and the caching logic.

Ensure your virtual environment is active.

Run pytest:

pytest


This command will automatically discover and run all tests, providing a detailed report on the server's functionality and robustness against simulated exchange responses.

Interactive Documentation (Recommended Start): Go here to see all the endpoints and test them directly

http://127.0.0.1:8000/docs