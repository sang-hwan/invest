import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import ccxt

# ----------------------
# 1) 테스트할 코인 심볼 & SMA 파라미터 목록 설정
# ----------------------
symbols = ['BTC/USDT', 'ETH/USDT']  # 여러 코인으로도 확장 가능
sma_param_list = [(5, 20), (7, 15), (10, 30)]
limit_days = 500  # 데이터 범위(일봉 기준 500개)

# ----------------------
# 2) 반복문으로 여러 조건 백테스트
# ----------------------
for symbol in symbols:
    print(f"\n=== Backtest for {symbol} ===")
    # (a) 시세 데이터 불러오기
    binance = ccxt.binance()
    ohlcv = binance.fetch_ohlcv(symbol, timeframe='1d', limit=limit_days)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)

    # (b) 심볼의 초기 종가, 전체 일봉 개수 등 간단히 확인
    print("Data sample:", df[['open','high','low','close','volume']].head(2), "\n")

    # (c) 각 SMA 파라미터 조합에 대해 백테스트
    for short_window, long_window in sma_param_list:
        test_df = df.copy()  # 원본 df 복사

        # -- (1) SMA 계산 --
        test_df[f'SMA_{short_window}'] = test_df['close'].rolling(short_window).mean()
        test_df[f'SMA_{long_window}'] = test_df['close'].rolling(long_window).mean()

        # -- (2) 매매 신호(signal) 생성 --
        # 골든크로스: SMA_short > SMA_long, 데드크로스: SMA_short < SMA_long
        test_df['signal'] = 0
        test_df['signal'] = np.where(
            (test_df[f'SMA_{short_window}'] > test_df[f'SMA_{long_window}']) &
            (test_df[f'SMA_{short_window}'].shift(1) <= test_df[f'SMA_{long_window}'].shift(1)),
            1,  # 매수
            test_df['signal']
        )
        test_df['signal'] = np.where(
            (test_df[f'SMA_{short_window}'] < test_df[f'SMA_{long_window}']) &
            (test_df[f'SMA_{short_window}'].shift(1) >= test_df[f'SMA_{long_window}'].shift(1)),
            -1, # 매도
            test_df['signal']
        )

        # -- (3) 포지션 (position) 설정 --
        test_df['position'] = test_df['signal'].replace(to_replace=0, method='ffill').fillna(0)

        # -- (4) 일별 수익률 계산(전략 수익) --
        # position이 1인 날: 매수 포지션, -1인 날: 공매도 가정(여기서는 단순히 1/-1 모두 반영)
        # shift(1)은 '어제 포지션'으로 '오늘 수익률'을 얻기 위함
        test_df['strategy_return'] = test_df['position'].shift(1) * test_df['close'].pct_change()

        # -- (5) 수수료(거래 비용) 0.1% 반영 --
        # 매매 발생일(signal != 0)에 수수료 차감
        fee_rate = 0.001  # 0.1%
        test_df.loc[test_df['signal'] != 0, 'strategy_return'] -= fee_rate

        # -- (6) 누적수익률 계산 --
        test_df['cum_strategy_return'] = (1 + test_df['strategy_return']).cumprod()
        test_df['cum_buy_and_hold'] = test_df['close'] / test_df['close'].iloc[0]

        # -- (7) 최종 결과 --
        final_strategy = test_df['cum_strategy_return'].iloc[-1]
        final_buyhold = test_df['cum_buy_and_hold'].iloc[-1]

        # -- (8) 결과 출력 --
        print(f"SMA({short_window},{long_window}) | Final Strategy: {final_strategy:.2f}, "
              f"Buy&Hold: {final_buyhold:.2f}")