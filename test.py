# test.py
import time
import datetime
import os

from trading_utils import (
    fetch_ohlc_data,
    calculate_sma,
    calculate_rsi,
    calculate_macd
)
import config

from db_utils import init_db, load_last_state, write_trade_log_db, write_decision_log_db

THRESHOLD_PERCENT = 5.0

def paper_trade_rebalance(target_ratio: float, current_price: float, rsi_latest: float, average_sentiment: float):
    total_value = config.balance + (config.position * current_price)
    target_value = total_value * target_ratio
    current_value = config.position * current_price
    diff_value = target_value - current_value

    if abs(diff_value) < config.REBALANCE_THRESHOLD:
        print(f"[INFO] 차이가 작아 매매하지 않음. diff_value={diff_value:.2f}")
        # -------------------- 의사결정 로그 (hold) --------------------
        reason_msg = f"diff_value={diff_value:.2f} < REBALANCE_THRESHOLD"
        write_decision_log_db(
            current_price=current_price,
            rsi=rsi_latest,
            sentiment=average_sentiment,
            decision="hold",
            reason=reason_msg
        )
        # ------------------------------------------------------------
        return

    # 의사결정 초기값 (hold → buy/sell로 변경)
    decision = "hold"
    reason_msg = ""

    if diff_value > 0:
        # 매수 로직
        buy_cost = diff_value * (1 + config.CURRENT_FEE)
        if buy_cost < config.MIN_ORDER_AMOUNT:
            print("[WARN] 매수가격이 MIN_ORDER_AMOUNT보다 작아서 매수하지 않음.")
            decision = "hold"
            reason_msg = "buy_cost < MIN_ORDER_AMOUNT"
            write_decision_log_db(
                current_price=current_price,
                rsi=rsi_latest,
                sentiment=average_sentiment,
                decision=decision,
                reason=reason_msg
            )
            return
        if buy_cost > config.balance:
            print("[WARN] 잔고 부족. 잔고만큼만 매수.")
            buy_cost = config.balance
            reason_msg = "잔고 부족 -> 전액 매수"

        buy_amount = (buy_cost * (1 - config.CURRENT_FEE)) / current_price
        config.balance -= buy_cost
        config.position += buy_amount

        print(f"[TRADE] 매수 체결: {buy_cost:.2f}원 -> {buy_amount:.6f} BTC")

        # 실제 매수 체결 로그
        write_trade_log_db(
            current_price=current_price,
            rsi=rsi_latest,
            sentiment=average_sentiment,
            action="buy",
            trade_amount=buy_amount,
            trade_price=current_price,
            balance=config.balance,
            position=config.position,
            reason=f"Rebalancing buy. target_ratio={target_ratio:.2f}"
        )

        # 의사결정 로그
        decision = "buy"
        reason_msg = f"Rebalancing buy. target_ratio={target_ratio:.2f}"

    else:
        # 매도 로직
        sell_value = abs(diff_value)
        receive_amount = sell_value * (1 - config.CURRENT_FEE)
        if sell_value > current_value:
            print("[WARN] 보유량보다 큰 매도 요청 -> 전량 매도")
            sell_value = current_value
            receive_amount = sell_value * (1 - config.CURRENT_FEE)
            reason_msg = "보유량보다 큰 매도 요청 -> 전량 매도"

        sell_btc_amount = sell_value / current_price
        if sell_btc_amount > config.position:
            sell_btc_amount = config.position

        config.position -= sell_btc_amount
        config.balance += receive_amount

        print(f"[TRADE] 매도 체결: {sell_value:.2f}원 -> {receive_amount:.2f}원")

        # 실제 매도 체결 로그
        write_trade_log_db(
            current_price=current_price,
            rsi=rsi_latest,
            sentiment=average_sentiment,
            action="sell",
            trade_amount=sell_btc_amount,
            trade_price=current_price,
            balance=config.balance,
            position=config.position,
            reason=f"Rebalancing sell. target_ratio={target_ratio:.2f}"
        )

        # 의사결정 로그
        decision = "sell"
        reason_msg = f"Rebalancing sell. target_ratio={target_ratio:.2f}"

    # 최종적으로 buy/sell 결정이 났으면 decision_logs에도 기록
    write_decision_log_db(
        current_price=current_price,
        rsi=rsi_latest,
        sentiment=average_sentiment,
        decision=decision,
        reason=reason_msg
    )

def adjust_target_ratio_with_signals(base_ratio: float, rsi_value: float, sentiment: float) -> float:
    new_ratio = base_ratio
    if rsi_value < 30:
        new_ratio += 0.1
    elif rsi_value > 70:
        new_ratio -= 0.1
    
    # 감성 점수 사용시:
    # if sentiment > 0.5: new_ratio += 0.1
    # elif sentiment < -0.5: new_ratio -= 0.1
    
    new_ratio = max(0.0, min(1.0, new_ratio))
    return new_ratio

if __name__ == "__main__":
    print("=== 코인 자동매매 테스트 (Paper Trading) ===")

    # 1) DB 초기화 (decision_logs 포함)
    init_db()

    # 2) 마지막 상태 복구
    last_state = load_last_state()
    if last_state is not None:
        config.balance, config.position = last_state
        print(f"[INFO] 이전 기록 불러오기 성공! balance={config.balance:.2f}, position={config.position:.6f}")
    else:
        print(f"[INFO] 이전 기록이 없습니다. 기본 시드값 사용: balance={config.balance:.2f}, position={config.position:.6f}")

    last_price = None
    while True:
        try:
            print("[INFO] Paper Trading 테스트 실행 중...")

            # (A) 시세 데이터
            df = fetch_ohlc_data(config.SYMBOL, config.TIMEFRAME, limit=config.MAX_CANDLE)
            current_price = df['close'].iloc[-1]

            if last_price is not None:
                price_change_percent = ((current_price - last_price) / last_price) * 100
            else:
                price_change_percent = 0.0

            print(f"[INFO] 이전 가격: {last_price}, 현재 가격: {current_price:.2f}, 변동률: {price_change_percent:.2f}%")

            # (B) 감성 점수 없이(고정값) 진행 예시
            average_sentiment = 0.0

            # (C) 기술적 지표
            df = calculate_sma(df, window=20)
            df = calculate_rsi(df, period=14)
            df = calculate_macd(df)
            rsi_latest = df['RSI_14'].iloc[-1]

            # (D) 목표 비중
            new_target_ratio = adjust_target_ratio_with_signals(
                base_ratio=config.TARGET_BTC_RATIO,
                rsi_value=rsi_latest,
                sentiment=average_sentiment
            )

            paper_trade_rebalance(
                target_ratio=new_target_ratio,
                current_price=current_price,
                rsi_latest=rsi_latest,
                average_sentiment=average_sentiment
            )

            last_price = current_price
            time.sleep(60)

        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(60)
