# main.py
import time
import datetime
import os

from trading_utils import fetch_ohlc_data, calculate_sma, calculate_rsi, calculate_macd
import config

# ---- 메모리 기반 import
from data_collector import main as data_collector_main
from summarize_content import main as summarize_content_main
from sentiment_analysis import main as sentiment_analysis_main

# DB 관련 함수에서 decision_logs 로깅 지원
from db_utils import (
    init_db, 
    load_last_state, 
    write_trade_log_db,       # 실제 매수/매도 체결 로그
    write_decision_log_db     # 모든 의사결정 (buy/sell/hold)
)

THRESHOLD_PERCENT = 5.0  # 예: 5% 이상 변동 시에만 감성 분석 실행

############################
# Paper Trading 보조 함수 #
############################
def paper_trade_rebalance(target_ratio: float, current_price: float, rsi_latest: float, average_sentiment: float):
    """
    목표 비중(target_ratio)에 맞춰 보유 자산을 리밸런싱(Paper Trading)하고,
    매매 발생 여부에 따라 trade_logs / decision_logs 둘 다 기록한다.
    """
    total_value = config.balance + (config.position * current_price)
    target_value = total_value * target_ratio
    current_value = config.position * current_price
    diff_value = target_value - current_value

    # 리밸런싱 최소 거래량/금액 조건
    if abs(diff_value) < config.REBALANCE_THRESHOLD:
        print(f"[INFO] 차이가 작아 매매하지 않음. diff_value={diff_value:.2f}")
        # --- 의사결정 로그 (hold) ---
        write_decision_log_db(
            current_price=current_price,
            rsi=rsi_latest,
            sentiment=average_sentiment,
            decision="hold",
            reason=f"diff_value={diff_value:.2f} < REBALANCE_THRESHOLD"
        )
        return

    # 기본 결정값
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

        # --- 매수 체결 로그 ---
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

        # --- 매도 체결 로그 ---
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

    # --- 의사결정 로그 (decision_logs) ---
    write_decision_log_db(
        current_price=current_price,
        rsi=rsi_latest,
        sentiment=average_sentiment,
        decision=decision,
        reason=reason_msg
    )


def adjust_target_ratio_with_signals(base_ratio: float, rsi_value: float, sentiment: float) -> float:
    """
    초기 TARGET_BTC_RATIO(기본값 0.5)에서
    RSI와 감성 점수를 함께 고려해 +/- 가중치를 부여.
    sentiment 범위: -1.0 ~ +1.0
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

    # 0 ~ 1.0 사이로 제한
    new_ratio = max(0.0, min(1.0, new_ratio))
    return new_ratio

####################
# 메인 루프 시작   #
####################
if __name__ == "__main__":
    print("=== 코인 자동매매 프로그램 (Paper Trading) 시작 ===")

    # 1) DB 초기화 (trade_logs & decision_logs)
    init_db()

    # 2) DB에서 마지막 상태 불러오기
    last_state = load_last_state()
    if last_state is not None:
        balance_from_db, position_from_db = last_state
        config.balance = balance_from_db
        config.position = position_from_db
        print(f"[INFO] 이전 기록 불러오기 성공! balance={config.balance:.2f}, position={config.position:.6f}")
    else:
        # 로그가 없으면 config.py의 기본값 사용
        print(f"[INFO] 이전 기록이 없습니다. 기본 시드값 사용: balance={config.balance:.2f}, position={config.position:.6f}")

    # 3) 메인 루프
    last_price = None
    average_sentiment = 0.0  # 변동이 없으면 직전 감성점수 유지
    while True:
        try:
            print("[INFO] 트레이딩 알고리즘 실행 중...")

            # (1) 현재 시세 데이터 조회
            df = fetch_ohlc_data(config.SYMBOL, config.TIMEFRAME, limit=config.MAX_CANDLE)
            current_price = df['close'].iloc[-1]

            # (2) 가격 변동률 체크
            if last_price is not None:
                price_change_percent = ((current_price - last_price) / last_price) * 100
                abs_change = abs(price_change_percent)
            else:
                price_change_percent = 0.0
                abs_change = 0.0

            print(f"[INFO] 이전 가격: {last_price}, 현재 가격: {current_price:.2f}, 변동률: {price_change_percent:.2f}%")

            # (3) 변동률이 일정 임계치 이상이면 감성 분석
            if last_price is None or abs_change >= THRESHOLD_PERCENT:
                print("[INFO] 변동률이 임계치를 초과했습니다. 뉴스 감성 분석 수행...")

                # Step A: 데이터 수집
                collected_data = data_collector_main()
                print("[INFO] 데이터 수집 완료. RSS={}, CryptoPanic={}, Reddit={}".format(
                    len(collected_data["rss"]), len(collected_data["cryptopanic"]), len(collected_data["reddit"])
                ))

                # Step B: 데이터 요약
                all_summaries = summarize_content_main(collected_data)
                print("[INFO] 데이터 요약 완료. 총 요약 개수:", len(all_summaries))

                # Step C: 감성 분석
                analysis_results = sentiment_analysis_main(all_summaries)
                print("[INFO] 감성 분석 완료. 분석 결과 개수:", len(analysis_results))

                if analysis_results:
                    average_sentiment = sum(r["sentiment_score"] for r in analysis_results) / len(analysis_results)
                    average_confidence = sum(r["confidence"] for r in analysis_results) / len(analysis_results)
                else:
                    average_sentiment = 0.0
                    average_confidence = 0.0

                print(f"[INFO] 전체 평균 감성 점수: {average_sentiment:.4f}, 평균 확신도: {average_confidence:.2f}")
            else:
                print("[INFO] 큰 변동이 없어 감성 분석을 건너뜁니다. (기존 감성 점수 유지)")

            # (4) 보조지표 계산 (기술적 지표)
            df = calculate_sma(df, window=20)  # SMA(20)
            df = calculate_rsi(df, period=14)  # RSI(14)
            df = calculate_macd(df)            # MACD(기본값: 12, 26, 9)

            # (5) 잔고 및 자산 평가
            total_value = config.balance + (config.position * current_price)
            print(f"[INFO] 현재 가격: {current_price:.2f}, 총 자산(Paper): {total_value:.2f}")

            # (6) RSI + 감성 점수 기반 목표 비중 도출
            rsi_latest = df['RSI_14'].iloc[-1]
            print(f"[INFO] 최근 RSI: {rsi_latest:.2f}, 평균 감성: {average_sentiment:.4f}")

            new_target_ratio = adjust_target_ratio_with_signals(
                base_ratio=config.TARGET_BTC_RATIO,
                rsi_value=rsi_latest,
                sentiment=average_sentiment
            )
            print(f"[INFO] 최종 계산된 목표 BTC 비중: {new_target_ratio:.2f} (기본={config.TARGET_BTC_RATIO})")

            # (7) Paper Trading: 리밸런싱 + (decision_logs 기록)
            paper_trade_rebalance(new_target_ratio, current_price, rsi_latest, average_sentiment)

            # (8) last_price 갱신
            last_price = current_price

            # (9) 일정 시간 대기(1분)
            time.sleep(60)

        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(60)
