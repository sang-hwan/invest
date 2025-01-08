# sentiment_analysis.py
import os
import json
from openai import OpenAI
from typing import Dict, List

print("[LOG] sentiment_analysis.py module is being imported...")

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

def analyze_summary(summary_text: str) -> Dict:
    """
    Perform sentiment analysis based on the provided summary_text,
    extracting sentiment_score, confidence, analysis_summary, and recommendation.
    """
    system_prompt = (
        "You are a helpful crypto market analyst. "
        "When you respond, you must output valid JSON with no additional text."
    )

    user_prompt_template = f"""
Please analyze the following summary:

\"\"\"{summary_text}\"\"\"


Return your response **only** in valid JSON format, with **no extra text**, using this exact schema:

{{
  "sentiment_score": float,          // range -1.0 to +1.0
  "confidence": int,                 // range 0 to 100
  "analysis_summary": "string",      // short comment about the sentiment
  "recommendation": "buy" | "sell" | "hold"
}}

Important rules:
1. Do not include any keys other than the four specified.
2. Output must be valid JSON, parseable by Python's json.loads().
3. Do not include backticks, markdown, or any extra text.
"""

    max_retries = 2

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt_template},
                ],
                temperature=0.0,
                max_tokens=300,
            )

            content = response.choices[0].message.content.strip()
            data = json.loads(content)  # JSON 파싱 시도

            sentiment_score = data.get("sentiment_score", 0.0)
            confidence = data.get("confidence", 50)
            analysis_summary = data.get("analysis_summary", "")
            recommendation = data.get("recommendation", "hold")

            # 간단 검증
            if not isinstance(sentiment_score, float):
                raise ValueError("sentiment_score must be float.")
            if not isinstance(confidence, int):
                raise ValueError("confidence must be int.")
            if not isinstance(analysis_summary, str):
                raise ValueError("analysis_summary must be string.")
            if recommendation not in ["buy", "sell", "hold"]:
                raise ValueError("recommendation must be buy/sell/hold.")

            return {
                "sentiment_score": sentiment_score,
                "confidence": confidence,
                "analysis_summary": analysis_summary,
                "recommendation": recommendation
            }

        except (json.JSONDecodeError, ValueError) as e:
            if attempt < max_retries - 1:
                print(f"[WARN] JSON parse failed (attempt {attempt+1}), retrying... Error: {e}")
            else:
                print(f"[ERROR] JSON parse failed after {max_retries} attempts. Using default values.")

    # 파싱 실패 시 기본값
    return {
        "sentiment_score": 0.0,
        "confidence": 50,
        "analysis_summary": "Failed to parse JSON",
        "recommendation": "hold"
    }

def main(summaries: List[Dict]) -> List[Dict]:
    """
    summarize_content.py 에서 생성된 summaries를 받아 감성분석을 하고,
    결과를 리스트로 반환.
    """
    print("[START] sentiment_analysis.py main()")

    results = []
    for i, item in enumerate(summaries, start=1):
        summary_text = item.get("summary_text", "")
        analysis = analyze_summary(summary_text)
        results.append({
            "chunk_index": item.get("chunk_index", i),
            "analysis_summary": analysis["analysis_summary"],
            "sentiment_score": analysis["sentiment_score"],
            "confidence": analysis["confidence"],
            "recommendation": analysis["recommendation"],
        })

    print(f"[INFO] Sentiment analysis complete. total results: {len(results)}")
    print("[END] sentiment_analysis.py main()")
    return results

if __name__ == "__main__":
    dummy_summaries = [
        {"chunk_index": 1, "summary_text": "Bitcoin is soaring. Some analysts think it will go higher."}
    ]
    analysis_results = main(dummy_summaries)
    print("[LOG] analysis_results:", analysis_results)
