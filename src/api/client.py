"""X API 客户端 - 使用 twitter-api-client 通过 GraphQL API 获取数据"""

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from pathlib import Path

# 导入 twitter-api-client
try:
    from twitter.scraper import Scraper
    from twitter.account import Account
except ImportError:
    raise ImportError("请安装 twitter-api-client: pip install twitter-api-client")


# X 时间格式: "Wed Jan 07 21:08:30 +0000 2026"
X_TIME_FORMAT = "%a %b %d %H:%M:%S %z %Y"

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))


def parse_x_timestamp(timestamp: str) -> Optional[datetime]:
    """解析 X 的时间戳格式"""
    if not timestamp:
        return None
    try:
        return datetime.strptime(timestamp, X_TIME_FORMAT)
    except ValueError:
        return None


def is_within_24h(timestamp: str) -> bool:
    """判断时间戳是否在过去 24 小时内"""
    dt = parse_x_timestamp(timestamp)
    if not dt:
        return False
    
    # 转换为 UTC 进行比较
    dt_utc = dt.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)
    
    # 差异在 0 到 24 小时之间
    diff = now_utc - dt_utc
    return timedelta(0) <= diff <= timedelta(hours=24)


@dataclass
class TweetData:
    """推文数据结构"""
    tweet_id: str
    user_handle: str
    user_name: str
    content: str
    posted_at: str  # X 格式时间
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0
    media_urls: list[str] = None
    is_retweet: bool = False
    original_author: Optional[str] = None
    
    def __post_init__(self):
        if self.media_urls is None:
            self.media_urls = []
    
    def is_recent(self) -> bool:
        """判断是否是最近发布的（24小时内）"""
        return is_within_24h(self.posted_at)


@dataclass
class UserInfo:
    """用户信息"""
    user_id: str
    handle: str
    name: str
    description: str = ""
    followers_count: int = 0
    following_count: int = 0
    profile_image_url: str = ""


class XApiClient:
    """X API 客户端 - 通过 GraphQL API 获取数据"""
    
    def __init__(self, auth_token: str, ct0: str = None):
        """
        初始化 API 客户端
        
        Args:
            auth_token: X 的 auth_token Cookie
            ct0: X 的 ct0 Cookie (CSRF token)，可选
        """
        self.auth_token = auth_token
        self.ct0 = ct0
        self._scraper: Optional[Scraper] = None
    
    def _get_cookies(self) -> dict:
        """获取 Cookie 字典"""
        cookies = {"auth_token": self.auth_token}
        if self.ct0:
            cookies["ct0"] = self.ct0
        return cookies
    
    def _init_scraper(self):
        """初始化 Scraper"""
        if self._scraper is None:
            self._scraper = Scraper(cookies=self._get_cookies())
    
    def get_user_info(self, handle: str) -> Optional[UserInfo]:
        """
        获取用户信息
        
        Args:
            handle: 用户名 (不含 @)
            
        Returns:
            UserInfo 或 None
        """
        self._init_scraper()
        
        try:
            users = self._scraper.users([handle])
            if users and len(users) > 0:
                raw = users[0]
                # 解析嵌套结构: data.user.result.legacy
                result = raw.get("data", {}).get("user", {}).get("result", {})
                legacy = result.get("legacy", {})
                
                return UserInfo(
                    user_id=result.get("rest_id", ""),
                    handle=legacy.get("screen_name", handle),
                    name=legacy.get("name", ""),
                    description=legacy.get("description", ""),
                    followers_count=legacy.get("followers_count", 0),
                    following_count=legacy.get("friends_count", 0),
                    profile_image_url=legacy.get("profile_image_url_https", "")
                )
        except Exception as e:
            print(f"获取用户信息失败: {e}")
        
        return None
    
    def get_user_tweets(self, handle: str, count: int = 20) -> list[TweetData]:
        """
        获取用户的推文
        
        Args:
            handle: 用户名 (不含 @)
            count: 获取数量
            
        Returns:
            TweetData 列表
        """
        self._init_scraper()
        tweets_data = []
        
        try:
            # 先获取用户信息以获取 user_id
            user_info = self.get_user_info(handle)
            if not user_info or not user_info.user_id:
                print(f"无法获取用户 @{handle} 的 ID")
                return []
            
            try:
                user_id = int(user_info.user_id)
            except ValueError:
                print(f"用户 @{handle} ID 格式错误: '{user_info.user_id}'")
                return []
            
            # 获取用户推文 (返回深度嵌套的数据)
            raw_tweets = self._scraper.tweets([user_id], limit=count)
            
            # 解析嵌套结构
            for raw in raw_tweets:
                tweets_data.extend(self._extract_tweets_from_response(raw))
                    
        except Exception as e:
            import traceback
            print(f"获取推文失败: {e}")
            traceback.print_exc()
        
        return tweets_data[:count]
    
    def _extract_tweets_from_response(self, raw: dict) -> list[TweetData]:
        """从深度嵌套的响应中提取推文"""
        tweets = []
        
        try:
            # 导航到 timeline instructions
            timeline = (raw.get("data", {})
                       .get("user", {})
                       .get("result", {})
                       .get("timeline_v2", {})
                       .get("timeline", {}))
            
            instructions = timeline.get("instructions", [])
            
            for instruction in instructions:
                if instruction.get("type") == "TimelineAddEntries":
                    entries = instruction.get("entries", [])
                    for entry in entries:
                        tweet = self._parse_timeline_entry(entry)
                        if tweet:
                            tweets.append(tweet)
                            
        except Exception as e:
            print(f"提取推文失败: {e}")
        
        return tweets
    
    def _parse_timeline_entry(self, entry: dict) -> Optional[TweetData]:
        """解析时间线条目"""
        try:
            content = entry.get("content", {})
            item_content = content.get("itemContent", {})
            
            if item_content.get("itemType") != "TimelineTweet":
                return None
            
            tweet_result = (item_content.get("tweet_results", {})
                           .get("result", {}))
            
            if tweet_result.get("__typename") != "Tweet":
                return None
            
            # 提取推文信息
            tweet_id = tweet_result.get("rest_id", "")
            legacy = tweet_result.get("legacy", {})
            
            # 用户信息
            core = tweet_result.get("core", {})
            user_results = core.get("user_results", {}).get("result", {})
            user_legacy = user_results.get("legacy", {})
            
            return TweetData(
                tweet_id=tweet_id,
                user_handle=user_legacy.get("screen_name", ""),
                user_name=user_legacy.get("name", ""),
                content=legacy.get("full_text", ""),
                posted_at=legacy.get("created_at", ""),
                likes=legacy.get("favorite_count", 0) or 0,
                retweets=legacy.get("retweet_count", 0) or 0,
                replies=legacy.get("reply_count", 0) or 0,
                views=int(tweet_result.get("views", {}).get("count", 0) or 0),
                media_urls=self._extract_media_urls(legacy),
                is_retweet=legacy.get("full_text", "").startswith("RT @"),
                original_author=None
            )
            
        except Exception as e:
            return None
    
    def _extract_media_urls(self, legacy: dict) -> list[str]:
        """提取媒体 URL"""
        urls = []
        media = legacy.get("extended_entities", {}).get("media", [])
        for m in media:
            if m.get("media_url_https"):
                urls.append(m["media_url_https"])
        return urls
        """
        获取主页时间线（需要登录）
        
        Args:
            count: 获取数量
            
        Returns:
            TweetData 列表
        """
        self._init_scraper()
        tweets_data = []
        
        try:
            # 使用 home_timeline 方法
            tweets = self._scraper.home_timeline(limit=count)
            
            for tweet in tweets:
                tweet_data = self._parse_tweet(tweet)
                if tweet_data:
                    tweets_data.append(tweet_data)
                    
        except Exception as e:
            print(f"获取时间线失败: {e}")
        
        return tweets_data
    
    def _parse_tweet(self, tweet: dict) -> Optional[TweetData]:
        """解析推文数据"""
        try:
            # 提取基本信息
            tweet_id = str(tweet.get("id", ""))
            
            # 用户信息
            user = tweet.get("user", {})
            user_handle = user.get("screen_name", "")
            user_name = user.get("name", "")
            
            # 推文内容
            content = tweet.get("full_text", "") or tweet.get("text", "")
            
            # 时间
            created_at = tweet.get("created_at", "")
            
            # 互动数据
            likes = tweet.get("favorite_count", 0) or 0
            retweets = tweet.get("retweet_count", 0) or 0
            replies = tweet.get("reply_count", 0) or 0
            views = tweet.get("view_count", 0) or 0
            
            # 媒体
            media_urls = []
            media = tweet.get("entities", {}).get("media", [])
            for m in media:
                if m.get("media_url_https"):
                    media_urls.append(m["media_url_https"])
            
            # 转发检测
            is_retweet = content.startswith("RT @")
            original_author = None
            if is_retweet:
                # 提取原作者
                import re
                match = re.match(r"RT @(\w+):", content)
                if match:
                    original_author = match.group(1)
            
            return TweetData(
                tweet_id=tweet_id,
                user_handle=user_handle,
                user_name=user_name,
                content=content,
                posted_at=created_at,
                likes=likes,
                retweets=retweets,
                replies=replies,
                views=views,
                media_urls=media_urls,
                is_retweet=is_retweet,
                original_author=original_author
            )
            
        except Exception as e:
            print(f"解析推文失败: {e}")
            return None


def load_cookies_from_file(filepath: str = "config/cookies.txt") -> dict:
    """从配置文件加载 Cookie"""
    cookies = {}
    
    if not Path(filepath).exists():
        return cookies
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                name, value = line.split('=', 1)
                name = name.strip()
                value = value.strip()
                if name and value and not value.startswith('你的'):
                    cookies[name] = value
    
    return cookies


def create_client_from_config() -> XApiClient:
    """从配置文件创建客户端"""
    cookies = load_cookies_from_file()
    
    auth_token = cookies.get("auth_token", "")
    ct0 = cookies.get("ct0", "")
    
    if not auth_token:
        raise ValueError("未找到 auth_token，请在 config/cookies.txt 中配置")
    
    return XApiClient(auth_token=auth_token, ct0=ct0)
