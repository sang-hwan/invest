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

THRESHOLD_PERCENT = 5.0  # 예: 5% 이상 변동 시에만 감성 분석 실행

############################
# Paper Trading 보조 함수 #
############################
def paper_trade_rebalance(target_ratio: float, current_price: float):
    """
    현재 잔고(config.balance), 보유 포지션(config.position)을 기준으로
    target_ratio(예: 0.5 = 50%)만큼 BTC를 보유하도록 가상 매매를 수행.
    REBALANCE_THRESHOLD보다 차이가 적으면 매매하지 않음.
    """
    total_value = config.balance + (config.position * current_price)
    target_value = total_value * target_ratio
    current_value = config.position * current_price
    diff_value = target_value - current_value

    # 차이가 REBALANCE_THRESHOLD 이하라면 굳이 거래하지 않음
    if abs(diff_value) < config.REBALANCE_THRESHOLD:
        print(f"[INFO] 현재 BTC 비중과 목표 비중의 차이가 작아 매매하지 않습니다. (차이: {diff_value:.2f})")
        return

    if diff_value > 0:
        # BTC를 더 사야 함
        # 실제 매수 체결액 = diff_value * (1 + 수수료)
        buy_cost = diff_value * (1 + config.CURRENT_FEE)
        # 최소 주문액 체크
        if buy_cost < config.MIN_ORDER_AMOUNT:
            print("[WARN] 매수가격이 MIN_ORDER_AMOUNT보다 작아서 매수하지 않음.")
            return
        if buy_cost > config.balance:
            print("[WARN] 잔고가 부족하여 전체 매수를 진행할 수 없음.")
            buy_cost = config.balance  # 잔고 최대치로만 매수

        # 매수 가능한 BTC 수량
        buy_amount = (buy_cost * (1 - config.CURRENT_FEE)) / current_price
        # 잔고 및 포지션 업데이트
        config.balance -= buy_cost
        config.position += buy_amount

        print(f"[TRADE] 매수 체결 (PaperTrading): 매수액={buy_cost:.2f}원, 수량={buy_amount:.6f} BTC, 새 잔고={config.balance:.2f}원")

    else:
        # BTC를 줄여야 함(diff_value < 0)
        sell_value = abs(diff_value)
        # 실제 받게 될 금액 = sell_value * (1 - 수수료)
        receive_amount = sell_value * (1 - config.CURRENT_FEE)
        if sell_value > current_value:
            print("[WARN] 보유 BTC보다 더 큰 금액을 팔려고 함. 전체만 매도합니다.")
            sell_value = current_value
            receive_amount = sell_value * (1 - config.CURRENT_FEE)

        # 매도할 BTC 수량
        sell_btc_amount = sell_value / current_price
        if sell_btc_amount > config.position:
            sell_btc_amount = config.position

        # 포지션 및 잔고 업데이트
        config.position -= sell_btc_amount
        config.balance += receive_amount

        print(f"[TRADE] 매도 체결 (PaperTrading): 매도액={sell_value:.2f}원 -> 실수령={receive_amount:.2f}원, 수량={sell_btc_amount:.6f} BTC, 새 잔고={config.balance:.2f}원")

def adjust_target_ratio_with_signals(base_ratio: float, rsi_value: float, sentiment: float) -> float:
    """
    초기 TARGET_BTC_RATIO(기본값 0.5)에서
    RSI와 감성 점수를 함께 고려해 +/- 가중치를 부여.
    """
    new_ratio = base_ratio

    # RSI 로직 예시
    if rsi_value < 30:
        # 매수 신호 -> 목표 비중 +0.1
        new_ratio += 0.1
    elif rsi_value > 70:
        # 매도 신호 -> 목표 비중 -0.1
        new_ratio -= 0.1

    # 감성 점수 로직 예시
    # sentiment 범위: -1.0 ~ +1.0
    if sentiment > 0.5:
        # 매우 긍정 -> 목표 비중 +0.1
        new_ratio += 0.1
    elif sentiment < -0.5:
        # 매우 부정 -> 목표 비중 -0.1
        new_ratio -= 0.1

    # 0 ~ 1.0 사이로 클램핑
    new_ratio = max(0.0, min(1.0, new_ratio))

    return new_ratio

####################
# 메인 루프 시작   #
####################
if __name__ == "__main__":
    print("=== 코인 자동매매 프로그램 (Paper Trading) 시작 ===")
    
    # 초기값 설정
    last_price = None
    average_sentiment = 0.0  # 최근 감성분석 결과
    average_confidence = 0.0

    while True:
        try:
            print("[INFO] 트레이딩 알고리즘 실행 중...")

            # 1. 현재 시세 데이터 조회
            df = fetch_ohlc_data(config.SYMBOL, config.TIMEFRAME, limit=config.MAX_CANDLE)
            current_price = df['close'].iloc[-1]

            # 2. 가격 변동률 체크
            if last_price is not None:
                price_change_percent = ((current_price - last_price) / last_price) * 100
                abs_change = abs(price_change_percent)
            else:
                price_change_percent = 0.0
                abs_change = 0.0

            print(f"[INFO] 이전 가격: {last_price}, 현재 가격: {current_price:.2f}, 변동률: {price_change_percent:.2f}%")

            # (중요) 변동률이 5% 이상 급등/급락인 경우에만 감성분석 실행
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
                print("[INFO] 큰 변동이 없어 감성 분석을 건너뜁니다. (기존 감성 점수 사용)")

            # 3. 보조지표 계산 (기술적 지표)
            df = calculate_sma(df, window=20)  # SMA(20)
            df = calculate_rsi(df, period=14)  # RSI(14)
            df = calculate_macd(df)            # MACD(기본값: 12, 26, 9)

            # 4. 잔고 및 자산 평가
            total_value = config.balance + (config.position * current_price)
            print(f"[INFO] 현재 가격: {current_price:.2f}, 총 자산(Paper): {total_value:.2f}")

            # 5. RSI + 감성 점수 기반 목표 비중 도출
            rsi_latest = df['RSI_14'].iloc[-1]
            print(f"[INFO] 최근 RSI: {rsi_latest:.2f}, 평균 감성: {average_sentiment:.4f}")

            new_target_ratio = adjust_target_ratio_with_signals(
                base_ratio=config.TARGET_BTC_RATIO,
                rsi_value=rsi_latest,
                sentiment=average_sentiment
            )

            print(f"[INFO] 최종 계산된 목표 BTC 비중: {new_target_ratio:.2f} (기본={config.TARGET_BTC_RATIO})")

            # 6. Paper Trading: 리밸런싱
            paper_trade_rebalance(new_target_ratio, current_price)

            # 7. last_price 갱신
            last_price = current_price

            # 8. 일정 시간 대기(1분)
            time.sleep(60)

        except Exception as e:
            print(f"[ERROR] 트레이딩 중 오류 발생: {e}")
            time.sleep(60)
