# trading_utils.py
import pandas as pd
import datetime
import time

print("[LOG] trading_utils.py module is being imported...")

from config import EXCHANGE

def fetch_ohlc_data(symbol, timeframe='5m', limit=50):
    """ccxt를 통해 OHLCV 데이터를 받아오는 함수"""
    print(f"[LOG] fetch_ohlc_data() -> symbol={symbol}, timeframe={timeframe}, limit={limit}")
    ohlcv = EXCHANGE.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def calculate_sma(df, window=14, column='close'):
    """ 단순 이동평균(SMA) """
    print(f"[LOG] calculate_sma() -> window={window}")
    df[f'SMA_{window}'] = df[column].rolling(window=window).mean()
    return df

def calculate_rsi(df, period=14, column='close'):
    """
    RSI(Relative Strength Index) 계산
    """
    print(f"[LOG] calculate_rsi() -> period={period}")
    delta = df[column].diff(1)
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df[f'RSI_{period}'] = rsi
    return df

def calculate_macd(df, fast_period=12, slow_period=26, signal_period=9, column='close'):
    """
    MACD(Moving Average Convergence Divergence) 계산
    """
    print(f"[LOG] calculate_macd() -> fast={fast_period}, slow={slow_period}, signal={signal_period}")
    df['EMA_fast'] = df[column].ewm(span=fast_period, adjust=False).mean()
    df['EMA_slow'] = df[column].ewm(span=slow_period, adjust=False).mean()

    df['MACD'] = df['EMA_fast'] - df['EMA_slow']
    df['MACD_signal'] = df['MACD'].ewm(span=signal_period, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    return df

if __name__ == "__main__":
    print("[START] trading_utils.py main()")
    # 간단 테스트 코드를 작성해도 됩니다.
    print("[END] trading_utils.py main()")
