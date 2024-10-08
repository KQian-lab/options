from flask import Flask, jsonify
import redis
import json
import math
import time
import threading
import schedule
import os
from options import get_contracts
from flasgger import Swagger

app = Flask(__name__)
swagger = Swagger(app)
redis_password = os.getenv('REDIS_PASSWORD')
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_db = int(os.getenv('REDIS_DB', 0))
initial_ttl = int(os.getenv('INITIAL_TTL', 60))

redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, password = redis_password)


def _refresh_options_chain(ticker):
    options_chain = get_contracts(ticker.upper())

    options_data = {}
    expiration_time = time.time() + initial_ttl
    
    for expiration_data in options_chain:
        expiration_date = expiration_data['expiration']
        contracts = expiration_data['call_options']
        redis_key = f"options_chain:{ticker}:{expiration_date}"
        contracts_json = json.dumps(contracts)
        redis_client.set(redis_key, contracts_json)
        redis_client.expire(redis_key, initial_ttl)
        
        options_data[expiration_date] = {
            "call_options": contracts,
            "delay": 0 
        }

    redis_client.hset("options_chain_ttl", ticker, expiration_time)

    return options_data

def _update_all_symbols():
    print("Starting Update")
    
    # Get all tickers from the TTL tracking hash
    tickers_with_ttl = redis_client.hgetall("options_chain_ttl")
    
    for ticker, expiration_timestamp in tickers_with_ttl.items():
        ticker = ticker.decode('utf-8')
        expiration_timestamp = float(expiration_timestamp)
        remaining_time = expiration_timestamp - time.time()
        
        if remaining_time < 10:  # Refresh data if less than 30 seconds remain
            print(f"TTL for {ticker} is low ({remaining_time} seconds), refreshing options chain...")
            _refresh_options_chain(ticker)
        else:
            print(f"{ticker} has sufficient TTL ({remaining_time} seconds).")

def get_options_chain(ticker):
    keys = redis_client.keys(f"options_chain:{ticker}:*")
    
    if keys:
        expiration_delays = []
        options_data = {}
        for key in keys:
            expiration_date = key.decode('utf-8').split(":")[-1]
            contracts_json = redis_client.get(key)

            ttl = redis_client.ttl(key)

            delay = initial_ttl - ttl if ttl > 0 else 0
            expiration_delays.append(delay)

            if contracts_json:
                options_data[expiration_date] = {
                    "call_options": json.loads(contracts_json),
                }
        ticker_delay = math.ceil(max(expiration_delays)) if expiration_delays else 0
        options_data["delay"] = ticker_delay
        return options_data
    
    options_data = _refresh_options_chain(ticker)
    
    return options_data

@app.route('/options-chain/<ticker>', methods=['GET'])
def options_chain(ticker):
    """
    Get the options chain for a specific ticker
    ---
    parameters:
      - name: ticker
        in: path
        required: true
        description: The stock ticker symbol (e.g., AAPL, TSLA, etc.)
        schema:
          type: string
          example: "AAPL"
    responses:
      '200':
        description: A JSON object with options chain data, organized by expiration dates
        content:
          application/json:
            schema:
              type: object
              description: A dictionary where the key is the expiration date, and the value is an object containing a `call_options` array.
              additionalProperties:
                type: object
                properties:
                  call_options:
                    type: array
                    items:
                      type: object
                      properties:
                        ask:
                          type: number
                          example: 0.0
                        bid:
                          type: number
                          example: 0.0
                        contractSymbol:
                          type: string
                          example: "AAPL241011C00100000"
                        contract_price_estimate:
                          type: number
                          example: 0.0
                        delta:
                          type: number
                          example: 1.0
                        impliedVolatility:
                          type: number
                          example: 1.0000000000000003e-05
                        inTheMoney:
                          type: boolean
                          example: true
                        lastPrice:
                          type: number
                          example: 124.05
                        openInterest:
                          type: integer
                          example: 0
                        stock_price:
                          type: number
                          example: 221.69
                        strike:
                          type: number
                          example: 100.0
                        volume:
                          type: number
                          example: 2
      '404':
        description: Ticker not found or no options data available for the given ticker
      '500':
        description: Internal server error
    """
    options_data = get_options_chain(ticker.upper())
    return jsonify(options_data)

@app.route('/stock-price/<ticker>', methods=['GET'])
def stock_price(ticker):
    """
    Get the stock price for a specific ticker
    ---
    parameters:
      - name: ticker
        in: path
        type: string
        required: true
        description: The stock ticker symbol
    responses:
      200:
        description: Stock price for the given ticker
        schema:
          type: object
          properties:
            ticker:
              type: string
              description: The stock ticker symbol
            stock_price:
              type: number
              description: The current stock price
    """
    options_data = get_options_chain(ticker.upper())
    
    if options_data:

        first_date = list(options_data.keys())[0]
        first_options = options_data[first_date]["call_options"]
        first_option = first_options[0]
        stock_price = first_option['stock_price']

        return {"ticker": ticker.upper(), "stock_price": stock_price}, 200
    else:
        return {"message": "Stock price not found"}, 200


@app.route('/options-chain/<ticker>/expirations', methods=['GET'])
def get_expiration_dates(ticker):
    """
    Get all expiration dates for a specific ticker
    ---
    parameters:
      - name: ticker
        in: path
        type: string
        required: true
        description: The stock ticker symbol
    responses:
      200:
        description: A list of expiration dates for the options chain
        schema:
          type: object
          properties:
            ticker:
              type: string
              description: The stock ticker symbol
            expirations:
              type: array
              items:
                type: string
                description: Expiration dates
    """
    keys = redis_client.keys(f"options_chain:{ticker}:*")


    expiration_dates = [key.split(':')[-1] for key in keys]

    if expiration_dates:
        return jsonify({
            "ticker": ticker,
            "expirations": expiration_dates
        }), 200
    else:
        return jsonify({
            "message": f"No expiration dates found for ticker {ticker}"
        }), 404

schedule.every(10).seconds.do(_update_all_symbols)

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=run_schedule)
    scheduler_thread.daemon = True 
    scheduler_thread.start()

    app.run(debug=True, host='0.0.0.0', port=8080)
