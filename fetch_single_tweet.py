import re
import json
import asyncio
from pathlib import Path

from src.api import create_client_from_config
from src.browser.scraper import XScraper, ScraperConfig


URL = "https://x.com/thedankoe/status/2010751592346030461"


def parse_tweet_url(url: str) -> tuple[str, str]:
    m = re.search(r"x\.com/([^/]+)/status/(\d+)", url)
    if not m:
        raise ValueError("无法从 URL 解析出 handle 和 tweet_id")
    handle = m.group(1)
    tweet_id = m.group(2)
    return handle, tweet_id


def fetch_tweet(url: str):
    handle, target_id = parse_tweet_url(url)
    client = create_client_from_config()
    tweets = client.get_user_tweets(handle, count=200)
    for t in tweets:
        if t.tweet_id == target_id:
            return t
    return None


def save_tweet(tweet, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{tweet.user_handle}_{tweet.tweet_id}"
    json_path = out_dir / f"{base_name}.json"
    txt_path = out_dir / f"{base_name}.txt"
    data = {
        "tweet_id": tweet.tweet_id,
        "user_handle": tweet.user_handle,
        "user_name": tweet.user_name,
        "content": tweet.content,
        "posted_at": tweet.posted_at,
        "likes": tweet.likes,
        "retweets": tweet.retweets,
        "replies": tweet.replies,
        "views": tweet.views,
        "media_urls": tweet.media_urls,
        "is_retweet": tweet.is_retweet,
        "original_author": tweet.original_author,
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text(tweet.content, encoding="utf-8")
    return {"json": json_path, "text": txt_path}


def extract_tco_urls(text: str) -> list[str]:
    return re.findall(r"https://t\.co/\w+", text or "")


def download_article(short_url: str, base_path: Path) -> dict:
    async def _inner():
        config = ScraperConfig(
            headless=True,
            screenshots_path="data/blog_screenshots",
        )
        scraper = XScraper(config)
        await scraper.start()
        try:
            page = await scraper.context.new_page()
            await page.goto(short_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            text = await page.evaluate("document.body.innerText")
            final_url = page.url
            txt_path = base_path.with_suffix(".txt")
            txt_path.write_text(text, encoding="utf-8", errors="ignore")
            return {"final_url": final_url, "text": txt_path}
        finally:
            await scraper.stop()

    return asyncio.run(_inner())


async def capture_screenshot(url: str, tag: str) -> str:
    config = ScraperConfig(
        headless=True,
        screenshots_path="data/blog_screenshots",
    )
    scraper = XScraper(config)
    await scraper.start()
    try:
        page = await scraper.context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        path = await scraper._take_screenshot(page, tag)
        await page.close()
        return path
    finally:
        await scraper.stop()


def main():
    tweet = fetch_tweet(URL)
    if tweet is None:
        print("未在最近推文中找到目标推文，请尝试增大 count 或手动调整逻辑")
        return
    out_dir = Path("data/single_tweet")
    paths = save_tweet(tweet, out_dir)
    print("已保存 JSON 文件:", paths["json"])
    print("已保存文本文件:", paths["text"])
    urls = extract_tco_urls(tweet.content)
    if urls:
        article_base = out_dir / f"{tweet.user_handle}_{tweet.tweet_id}_article"
        article = download_article(urls[0], article_base)
        print("展开后的真实链接:", article["final_url"])
        print("已保存博客 HTML 文件:", article["html"])
        print("已保存博客纯文本文件:", article["text"])
    else:
        print("推文内容中未检测到 t.co 博客链接")
    screenshot_tag = f"{tweet.user_handle}_{tweet.tweet_id}"
    screenshot_path = asyncio.run(capture_screenshot(URL, screenshot_tag))
    print("已保存截图文件:", screenshot_path)


if __name__ == "__main__":
    main()
