"""数据模型定义"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class User:
    """订阅用户"""
    handle: str
    name: str
    category: str = ""
    priority: str = "medium"
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "handle": self.handle,
            "name": self.name,
            "category": self.category,
            "priority": self.priority,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Tweet:
    """推文数据"""
    id: str  # tweet_id
    user_handle: str
    user_name: str
    content: str
    posted_at: Optional[str] = None
    collected_at: datetime = field(default_factory=datetime.now)
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0  # 浏览数
    media_urls: str = ""  # 媒体URL，逗号分隔
    is_retweet: bool = False
    original_author: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_handle": self.user_handle,
            "user_name": self.user_name,
            "content": self.content,
            "posted_at": self.posted_at,
            "collected_at": self.collected_at.isoformat(),
            "likes": self.likes,
            "retweets": self.retweets,
            "replies": self.replies,
            "views": self.views,
            "media_urls": self.media_urls,
            "is_retweet": self.is_retweet,
            "original_author": self.original_author
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Tweet":
        collected_at = data.get("collected_at")
        if isinstance(collected_at, str):
            collected_at = datetime.fromisoformat(collected_at)
        elif collected_at is None:
            collected_at = datetime.now()
            
        return cls(
            id=data.get("id", ""),
            user_handle=data.get("user_handle", ""),
            user_name=data.get("user_name", ""),
            content=data.get("content", ""),
            posted_at=data.get("posted_at"),
            collected_at=collected_at,
            likes=data.get("likes", 0),
            retweets=data.get("retweets", 0),
            replies=data.get("replies", 0),
            views=data.get("views", 0),
            media_urls=data.get("media_urls", ""),
            is_retweet=data.get("is_retweet", False),
            original_author=data.get("original_author")
        )


@dataclass
class CollectionRun:
    """采集运行记录"""
    id: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    users_count: int = 0
    tweets_count: int = 0
    success_count: int = 0
    error_count: int = 0
    status: str = "running"  # running, completed, failed
    errors: str = ""  # JSON 字符串存储错误列表
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "users_count": self.users_count,
            "tweets_count": self.tweets_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "status": self.status,
            "errors": self.errors
        }
    
    def add_error(self, error: str):
        """添加错误信息"""
        errors_list = json.loads(self.errors) if self.errors else []
        errors_list.append(error)
        self.errors = json.dumps(errors_list, ensure_ascii=False)
