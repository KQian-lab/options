import json
from datetime import datetime
import yfinance as yf
from scipy.stats import norm
import pandas as pd
import numpy as np

# Black-Scholes delta function
def _black_scholes_delta(S, K, r, T, sigma, option_type='call', q=0, precision=3):
    S = np.asarray(S)
    K = np.asarray(K)
    T = np.asarray(T)
    sigma = np.asarray(sigma)
    
    S = np.maximum(S, 1e-10)
    K = np.maximum(K, 1e-10)
    T = np.maximum(T, 1e-10)

    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

    if option_type == 'call':
        delta = norm.cdf(d1)
    elif option_type == 'put':
        delta = norm.cdf(d1) - 1
    else:
        raise ValueError("Option type must be either 'call' or 'put'")


    return delta


def get_contracts(ticker):
    stock = yf.Ticker(ticker)
    options_data = []
    
    # Fetch stock info and price
    stock_info = stock.fast_info

    # Get the risk-free rate from the 10-year treasury yield
    treasury_10yr = yf.Ticker("^TNX")
    treasury_yield = treasury_10yr.history(period="1d")
    risk_free_rate = treasury_yield['Close'].values[0] / 100

    q = stock_info.get('dividendYield', 0)
    stock_price = stock.fast_info['last_price']

    # Fetch all available expirations
    all_expirations = stock.options

    for expiration in all_expirations:
        dt_expiration = datetime.strptime(expiration, "%Y-%m-%d")
        current_date = datetime.now()
        days_left = (dt_expiration - current_date).days
        T = days_left / 365  # Time to expiration in years

        # Get option chain data for each expiration
        opt = stock.option_chain(expiration)
        opt_calls = opt.calls
        
        # Drop unnecessary columns
        opt_calls = opt_calls.drop(columns=['lastTradeDate', 'change', 'percentChange', 'contractSize', 'currency'])
        
        # Calculate contract price estimate
        opt_calls['contract_price_estimate'] = (opt_calls['bid'] + opt_calls['ask']) / 2
        opt_calls['stock_price'] = stock_price
        
        # Calculate delta
        implied_volatilities = opt_calls['impliedVolatility']
        strike_prices = opt_calls['strike']
        valid_rows = pd.notna(implied_volatilities)

        if valid_rows.any():
            opt_calls.loc[valid_rows, 'delta'] = _black_scholes_delta(
                S=stock_price,
                K=strike_prices[valid_rows],
                r=risk_free_rate,
                T=T,
                sigma=implied_volatilities[valid_rows],
                option_type='call',
                q=q
            )

        # Replace NaN values in 'volume' with 0
        opt_calls['volume'] = opt_calls['volume'].fillna(0)

        # Convert dataframe to list of dictionaries (JSON structure)
        opt_json = opt_calls.to_dict(orient='records')

        # Append expiration and options data to the result
        options_data.append({
            'expiration': expiration,
            'call_options': opt_json
        })

    options_json = options_data

    return options_json

