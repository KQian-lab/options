import yfinance as yf
treasury_10yr = yf.Ticker("^TNX")
treasury_yield = treasury_10yr.history(period="1d")
risk_free_rate = treasury_yield['Close'].values[0] / 100
print(treasury_yield)