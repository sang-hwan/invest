# data_collector.py
import os
import sys
import asyncio
import feedparser
import requests
import re

print("[LOG] data_collector.py module is being imported...")

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()

import asyncpraw

def clean_text(raw_text: str, max_length: int = 500) -> str:
    text = re.sub(r'<.*?>', ' ', raw_text)
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[\r\n]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) > max_length:
        text = text[:max_length] + " ...(truncated)"
    return text

async def collect_reddit_data() -> list:
    print("[LOG] collect_reddit_data() start...")
    reddit_data = []

    async with asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_SECRET_ID"),
        user_agent=os.getenv("REDDIT_USER_AGENT")
    ) as reddit_client:
        
        reddit_subs = [
            "CryptoCurrency",
            "Bitcoin",
            "Ethereum",
            "CryptoMarkets",
            "CryptoMoonShots",
            "Altcoin",
            "CoinBase",
            "Binance",
            "KrakenSupport",
            "BitcoinBeginners"
        ]

        for sub_name in reddit_subs:
            try:
                subreddit = await reddit_client.subreddit(sub_name)
                async for submission in subreddit.hot(limit=5):
                    post_info = {
                        "subreddit": sub_name,
                        "title": clean_text(submission.title, max_length=300),
                        "url": submission.url,
                        "score": submission.score
                    }
                    reddit_data.append(post_info)
            except Exception as e:
                print(f"[ERROR] 서브레딧({sub_name}) 수집 중 오류: {e}")

    print("[LOG] collect_reddit_data() end. total collected:", len(reddit_data))
    return reddit_data

def get_rss_feed(url: str) -> list:
    print("[LOG] get_rss_feed() start...")
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries:
        summary_clean = clean_text(getattr(entry, 'summary', ''), max_length=1000)
        text_clean = clean_text(entry.title + " " + getattr(entry, 'summary', ''), max_length=1500)

        articles.append({
            'source': 'RSS',
            'title': clean_text(entry.title, max_length=300),
            'link': entry.link,
            'summary': summary_clean,
            'timestamp': getattr(entry, 'published', ''),
            'text': text_clean
        })
    print("[LOG] get_rss_feed() end. total articles:", len(articles))
    return articles

def get_cryptopanic_news(api_key: str, kind='news', currencies='BTC,ETH') -> list:
    print("[LOG] get_cryptopanic_news() start...")
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        'auth_token': api_key,
        'kind': kind,
        'currencies': currencies
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        results = data.get('results', [])
        parsed = []
        for item in results:
            body_text = item.get('body', '')
            text_clean = clean_text(item['title'] + " " + body_text, max_length=1500)
            parsed.append({
                'source': 'CryptoPanic',
                'title': clean_text(item['title'], max_length=300),
                'timestamp': item['published_at'],
                'text': text_clean,
                'domain': item['source']['domain']
            })
        print("[LOG] get_cryptopanic_news() end. total news:", len(parsed))
        return parsed
    else:
        print("[ERROR] CryptoPanic Error:", response.text)
        return []

def main() -> dict:
    print("[START] data_collector.py main()")
    
    # 1) RSS
    print("[INFO] Fetching RSS feed...")
    rss_url = "https://news.google.com/rss/search?q=bitcoin"
    rss_articles = get_rss_feed(rss_url)

    # 2) CryptoPanic
    print("[INFO] Fetching CryptoPanic news...")
    api_key = os.getenv("CRYPTOPANIC_API_KEY", "")
    cp_news = []
    if api_key:
        cp_news = get_cryptopanic_news(api_key, 'news', 'BTC,ETH')
    else:
        print("[INFO] CryptoPanic API Key가 설정되지 않았습니다. (데이터 수집 스킵)")

    # 3) Reddit
    print("[INFO] Fetching Reddit data...")
    reddit_data = asyncio.run(collect_reddit_data())

    print("[END] data_collector.py main()")
    return {
        "rss": rss_articles,
        "cryptopanic": cp_news,
        "reddit": reddit_data
    }

if __name__ == "__main__":
    # 단독 실행 시 테스트
    data = main()
    print("[LOG] data_collector.py executed directly, data length:",
          {k: len(v) for k, v in data.items()})
