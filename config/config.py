# config.py
import ccxt
import os

# ----- 거래소 설정 (예: 업비트)
EXCHANGE = ccxt.upbit({
    "apiKey": os.getenv("UPBIT_ACCESS_KEY", ""),
    "secret": os.getenv("UPBIT_SECRET_KEY", "")
})

# ----- 거래 대상
SYMBOL = 'BTC/KRW'
TIMEFRAME = '5m'
MAX_CANDLE = 50

# ----- 트레이딩 환경 파라미터
TARGET_BTC_RATIO = 0.5
REBALANCE_THRESHOLD = 5000

balance = 1_000_000.0
position = 0.0
buy_price = 0.0

MAKER_FEE = 0.0005
TAKER_FEE = 0.00139
CURRENT_FEE = TAKER_FEE

MIN_ORDER_AMOUNT = 5000
MAX_ORDER_AMOUNT = 1_000_000_000