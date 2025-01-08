# summarize_content.py
from openai import OpenAI
import os
from typing import List, Dict

print("[LOG] summarize_content.py module is being imported...")

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

def summarize_chunk(chunk: List[Dict]) -> str:
    """
    Summarize a chunk of data (e.g. 5 articles/posts) at once using GPT.
    """
    system_prompt = "You are a helpful assistant that summarizes crypto news/posts in English."
    user_prompt = "The following are articles or posts related to cryptocurrency:\n\n"
    for i, item in enumerate(chunk, start=1):
        title = item.get("title", "(no title)")
        text = item.get("text", "(no text)")
        user_prompt += f"({i}) Title: {title}\nContent: {text}\n\n"

    user_prompt += (
        "Please provide a single concise English summary of the entire content above, "
        "keeping it under 300 words."
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=500,
        temperature=0.7
    )

    summary_text = response.choices[0].message.content
    return summary_text.strip()

def chunkify(data_list: List[Dict], chunk_size: int = 5) -> List[List[Dict]]:
    """
    data_list를 chunk_size만큼 나누어 묶음을 반환
    """
    chunks = []
    for i in range(0, len(data_list), chunk_size):
        chunks.append(data_list[i:i+chunk_size])
    return chunks

def main(collected_data: dict, chunk_size: int = 5) -> List[Dict]:
    """
    data_collector.py 에서 수집된 데이터를 입력받아 요약을 수행하고,
    (파일에 저장하지 않고) 메모리 상에서 결과를 반환.
    """
    print("[START] summarize_content.py main()")

    # 1) RSS 데이터, 2) CryptoPanic 데이터, 3) Reddit 데이터를 전부 합쳐서 요약
    combined_data = []
    combined_data.extend(collected_data.get("rss", []))
    combined_data.extend(collected_data.get("cryptopanic", []))
    combined_data.extend(collected_data.get("reddit", []))

    # chunk 단위로 나눈 후 GPT 요약
    all_summaries = []
    chunked_lists = chunkify(combined_data, chunk_size=chunk_size)
    for idx, chunk in enumerate(chunked_lists, start=1):
        summary_result = summarize_chunk(chunk)
        all_summaries.append({
            "chunk_index": idx,
            "summary_text": summary_result
        })
        print(f"[INFO] Summarized chunk {idx} with {len(chunk)} items.")

    print("[END] summarize_content.py main()")
    return all_summaries

if __name__ == "__main__":
    # 단독 실행 시에는 테스트용 데이터를 넣어볼 수 있습니다.
    dummy_data = {
        "rss": [{"title": "Test RSS", "text": "Some RSS news content"}],
        "cryptopanic": [{"title": "Test CryptoPanic", "text": "Some CP news content"}],
        "reddit": [{"title": "Test Reddit", "text": "Some Reddit post content"}]
    }
    summaries = main(dummy_data, chunk_size=2)
    print("[LOG] Summaries:", summaries)
