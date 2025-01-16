# main.py
import time
import datetime
import os

from modules.trading_utils import (
    fetch_ohlc_data,
    calculate_sma,
    calculate_rsi,
    calculate_macd
)

# ---- 메모리 기반 import
from modules.data_collector import main as data_collector_main
from modules.summarize_content import main as summarize_content_main
from modules.sentiment_analysis import main as sentiment_analysis_main

# DB 관련 함수
from modules.db_utils import (
    init_db, 
    load_last_state, 
    load_last_sentiment,  # ### ADD
    write_trade_log_db,
    write_decision_log_db,
    save_meta_info,
    load_meta_info
)

import config.config as config

THRESHOLD_PERCENT = 5.0  # 5% 이상 변동 시 감성 분석

############################
# Paper Trading 보조 함수 #
############################
def paper_trade_rebalance(target_ratio: float, current_price: float, rsi_latest: float, average_sentiment: float):
    """
    목표 비중(target_ratio)에 맞춰 보유 자산을 리밸런싱(Paper Trading) 후
    trade_logs / decision_logs 모두 기록.
    """
    total_value = config.balance + (config.position * current_price)
    target_value = total_value * target_ratio
    current_value = config.position * current_price
    diff_value = target_value - current_value

    if abs(diff_value) < config.REBALANCE_THRESHOLD:
        print(f"[INFO] 차이가 작아 매매하지 않음. diff_value={diff_value:.2f}")
        write_decision_log_db(
            current_price=current_price,
            rsi=rsi_latest,
            sentiment=average_sentiment,
            decision="hold",
            reason=f"diff_value={diff_value:.2f} < REBALANCE_THRESHOLD"
        )
        return

    decision = "hold"
    reason_msg = ""

    if diff_value > 0:
        # 매수
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

        # 기록
        write_trade_log_db(
            current_price=current_price,
            rsi=rsi_latest,
            sentiment=average_sentiment,
            action="buy",
            trade_amount=buy_amount,
            trade_price=current_price,
            balance=config.balance,
            position=config.position,
            reason=f"PaperTrading rebalancing (buy). target_ratio={target_ratio:.2f}"
        )

        decision = "buy"
        if not reason_msg:
            reason_msg = f"PaperTrading rebalancing. target_ratio={target_ratio:.2f}"

    else:
        # 매도
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

        # 기록
        write_trade_log_db(
            current_price=current_price,
            rsi=rsi_latest,
            sentiment=average_sentiment,
            action="sell",
            trade_amount=sell_btc_amount,
            trade_price=current_price,
            balance=config.balance,
            position=config.position,
            reason=f"PaperTrading rebalancing (sell). target_ratio={target_ratio:.2f}"
        )

        decision = "sell"
        if not reason_msg:
            reason_msg = f"PaperTrading rebalancing. target_ratio={target_ratio:.2f}"

    # 의사결정 로그
    write_decision_log_db(
        current_price=current_price,
        rsi=rsi_latest,
        sentiment=average_sentiment,
        decision=decision,
        reason=reason_msg
    )


def adjust_target_ratio_with_signals(base_ratio: float, rsi_value: float, sentiment: float) -> float:
    """
    RSI & 감성 점수 기반으로 target_ratio를 조정.
    """
    new_ratio = base_ratio

    # RSI 로직
    if rsi_value < 30:
        new_ratio += 0.1
    elif rsi_value > 70:
        new_ratio -= 0.1

    # 감성 점수 로직
    if sentiment > 0.5:
        new_ratio += 0.1
    elif sentiment < -0.5:
        new_ratio -= 0.1

    return max(0.0, min(1.0, new_ratio))


######################
# 메인 루프 시작점   #
######################
if __name__ == "__main__":
    print("=== 코인 자동매매 프로그램 (Paper Trading) 시작 ===")

    # 1) DB 초기화
    init_db()

    # 2) 마지막 잔고/포지션 상태 불러오기
    last_state = load_last_state()
    if last_state is not None:
        balance_from_db, position_from_db = last_state
        config.balance = balance_from_db
        config.position = position_from_db
        print(f"[INFO] 이전 기록 불러오기 성공! balance={config.balance:.2f}, position={config.position:.6f}")
    else:
        print(f"[INFO] 이전 기록 없음. 기본 시드값 사용: balance={config.balance:.2f}, position={config.position:.6f}")

    # 3) last_price 불러오기 (meta_info)
    stored_last_price = load_meta_info("last_price")
    if stored_last_price is not None:
        last_price = float(stored_last_price)
        print(f"[INFO] meta_info에서 last_price={last_price} 불러옴.")
    else:
        last_price = None
        print("[INFO] 저장된 last_price가 없어 None으로 초기화.")

    # 4) 최근 감성 점수 불러오기 (decision_logs)
    last_sentiment = load_last_sentiment()  # ### ADD
    if last_sentiment is not None:
        average_sentiment = last_sentiment
        print(f"[INFO] DB에서 최근 감성점수를 복원: {average_sentiment:.4f}")
    else:
        average_sentiment = 0.0
        print("[INFO] 이전 감성점수가 없어 기본값(0.0) 사용.")

    # 메인 루프
    while True:
        try:
            print("[INFO] 트레이딩 알고리즘 실행 중...")

            # (1) 현재 시세
            df = fetch_ohlc_data(config.SYMBOL, config.TIMEFRAME, limit=config.MAX_CANDLE)
            current_price = df['close'].iloc[-1]

            # (2) 가격 변동 체크
            if last_price is not None:
                price_change_percent = ((current_price - last_price) / last_price) * 100
                abs_change = abs(price_change_percent)
            else:
                price_change_percent = 0.0
                abs_change = 0.0

            print(f"[INFO] 이전 가격: {last_price}, 현재 가격: {current_price:.2f}, 변동률: {price_change_percent:.2f}%")

            # (3) 감성 분석 조건
            if last_price is None or abs_change >= THRESHOLD_PERCENT:
                print("[INFO] 변동률 임계초과 or last_price=None -> 감성 분석 수행...")
                # 데이터 수집 -> 요약 -> 감성분석
                collected_data = data_collector_main()
                all_summaries = summarize_content_main(collected_data)
                analysis_results = sentiment_analysis_main(all_summaries)

                if analysis_results:
                    average_sentiment = sum(r["sentiment_score"] for r in analysis_results) / len(analysis_results)
                    average_confidence = sum(r["confidence"] for r in analysis_results) / len(analysis_results)
                else:
                    average_sentiment = 0.0
                    average_confidence = 0.0

                print(f"[INFO] 평균 감성: {average_sentiment:.4f}, 평균 확신도: {average_confidence:.2f}")
            else:
                print("[INFO] 큰 변동 없음 -> 감성 분석 스킵 (이전 감성점수 유지)")

            # (4) 기술적 지표 계산
            df = calculate_sma(df, window=20)
            df = calculate_rsi(df, period=14)
            df = calculate_macd(df)

            # (5) 자산 평가
            total_value = config.balance + (config.position * current_price)
            print(f"[INFO] 현재 가격: {current_price:.2f}, 총 자산(Paper): {total_value:.2f}")

            # (6) 목표 비중 계산
            rsi_latest = df['RSI_14'].iloc[-1]
            new_target_ratio = adjust_target_ratio_with_signals(
                base_ratio=config.TARGET_BTC_RATIO,
                rsi_value=rsi_latest,
                sentiment=average_sentiment
            )
            print(f"[INFO] RSI={rsi_latest:.2f}, 감성={average_sentiment:.4f} -> 목표비중={new_target_ratio:.2f}")

            # (7) 리밸런싱
            paper_trade_rebalance(new_target_ratio, current_price, rsi_latest, average_sentiment)

            # (8) last_price 갱신 & DB 저장
            last_price = current_price
            save_meta_info("last_price", last_price)

            # (9) 주기적 대기
            time.sleep(60)

        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(60)
