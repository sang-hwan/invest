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

if __name__ == "__main__":
    print("=== 코인 자동매매 프로그램 시작 ===")
    
    # 초기값 설정
    last_price = None
    average_sentiment = 0.0  # 최근 감성분석 결과를 저장할 변수
    average_confidence = 0.0

    while True:
        try:
            print("[INFO] 트레이딩 알고리즘 실행 중...")

            # 1. 현재 시세 데이터 조회
            df = fetch_ohlc_data(config.SYMBOL, config.TIMEFRAME, limit=config.MAX_CANDLE)
            current_price = df['close'].iloc[-1]

            # 2. 가격 변동률 체크
            if last_price is not None:
                # 변동률(%) = ((현재가 - 이전가) / 이전가) * 100
                price_change_percent = ((current_price - last_price) / last_price) * 100
                abs_change = abs(price_change_percent)
            else:
                # 프로그램 첫 실행 시엔 변동률 계산 불가하므로 0으로 세팅
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
            print(f"[INFO] 현재 가격: {current_price:.2f}, 총 자산: {total_value:.2f}")

            # 5. RSI 기반 매매 시그널 + 감성 점수
            rsi_latest = df['RSI_14'].iloc[-1]
            print(f"[INFO] 최근 RSI: {rsi_latest:.2f}, 평균 감성: {average_sentiment:.4f}")

            # --- 예시: RSI + 감성 점수를 함께 고려 ---
            # 감성이 매우 긍정(0.5 이상)이고 RSI가 낮으면 => 매수 신호
            # 감성이 매우 부정(-0.5 이하)이고 RSI가 높으면 => 매도 신호
            if rsi_latest < 30 and average_sentiment > 0.5:
                print("[INFO] RSI가 낮고, 감성도 상당히 긍정적입니다. 강한 매수 신호!")
                # 실제 매수 로직 구현
            elif rsi_latest > 70 and average_sentiment < -0.5:
                print("[INFO] RSI가 높고, 감성도 상당히 부정적입니다. 강한 매도 신호!")
                # 실제 매도 로직 구현
            else:
                # 기존 RSI 단독 신호
                if rsi_latest < 30:
                    print("[INFO] RSI가 낮습니다. 매수 신호 감지.")
                elif rsi_latest > 70:
                    print("[INFO] RSI가 높습니다. 매도 신호 감지.")
                else:
                    print("[INFO] 특별한 신호 없음 (관망).")

            # 6. last_price 갱신
            last_price = current_price

            # 7. 일정 시간 대기(1분)
            time.sleep(60)

        except Exception as e:
            print(f"[ERROR] 트레이딩 중 오류 발생: {e}")
            time.sleep(60)
