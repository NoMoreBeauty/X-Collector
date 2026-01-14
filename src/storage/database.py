"""SQLite 数据库操作"""

import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import hashlib

from .models import Tweet, CollectionRun


class Database:
    """SQLite 数据库管理"""
    
    def __init__(self, db_path: str = "data/tweets.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """连接数据库"""
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()
    
    async def close(self):
        """关闭数据库连接"""
        if self._conn:
            await self._conn.close()
    
    async def _create_tables(self):
        """创建数据表"""
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS tweets (
                id TEXT PRIMARY KEY,
                user_handle TEXT NOT NULL,
                user_name TEXT,
                content TEXT NOT NULL,
                posted_at TEXT,
                collected_at TEXT NOT NULL,
                likes INTEGER DEFAULT 0,
                retweets INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                media_urls TEXT DEFAULT '',
                is_retweet INTEGER DEFAULT 0,
                original_author TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_tweets_user ON tweets(user_handle);
            CREATE INDEX IF NOT EXISTS idx_tweets_collected ON tweets(collected_at);
            
            CREATE TABLE IF NOT EXISTS collection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                users_count INTEGER DEFAULT 0,
                tweets_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                errors TEXT DEFAULT '[]'
            );
        """)
        await self._conn.commit()
    
    @staticmethod
    def generate_tweet_id(user_handle: str, content: str) -> str:
        """生成推文唯一ID"""
        text = f"{user_handle}:{content[:100]}"
        return hashlib.md5(text.encode()).hexdigest()
    
    async def save_tweet(self, tweet: Tweet) -> bool:
        """
        保存推文 (如果已存在则跳过)
        
        Returns:
            bool: True 如果是新推文，False 如果已存在
        """
        # 生成 ID
        if not tweet.id:
            tweet.id = self.generate_tweet_id(tweet.user_handle, tweet.content)
        
        # 检查是否已存在
        cursor = await self._conn.execute(
            "SELECT id FROM tweets WHERE id = ?", (tweet.id,)
        )
        if await cursor.fetchone():
            return False
        
        # 插入新推文
        await self._conn.execute("""
            INSERT INTO tweets (
                id, user_handle, user_name, content, posted_at, collected_at,
                likes, retweets, replies, views, media_urls, is_retweet,
                original_author
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tweet.id, tweet.user_handle, tweet.user_name, tweet.content,
            tweet.posted_at, tweet.collected_at.isoformat(),
            tweet.likes, tweet.retweets, tweet.replies, tweet.views,
            tweet.media_urls, 1 if tweet.is_retweet else 0, tweet.original_author
        ))
        await self._conn.commit()
        return True
    
    async def save_tweets(self, tweets: list[Tweet]) -> int:
        """
        批量保存推文
        
        Returns:
            int: 新保存的推文数量
        """
        new_count = 0
        for tweet in tweets:
            if await self.save_tweet(tweet):
                new_count += 1
        return new_count
    
    async def get_tweets_by_user(self, handle: str, limit: int = 50) -> list[Tweet]:
        """获取用户的推文"""
        cursor = await self._conn.execute("""
            SELECT * FROM tweets WHERE user_handle = ?
            ORDER BY collected_at DESC LIMIT ?
        """, (handle, limit))
        
        rows = await cursor.fetchall()
        return [Tweet.from_dict(dict(row)) for row in rows]
    
    async def get_tweets_since(self, since: datetime, limit: int = 500) -> list[Tweet]:
        """获取指定时间后的推文"""
        cursor = await self._conn.execute("""
            SELECT * FROM tweets WHERE collected_at >= ?
            ORDER BY collected_at DESC LIMIT ?
        """, (since.isoformat(), limit))
        
        rows = await cursor.fetchall()
        return [Tweet.from_dict(dict(row)) for row in rows]
    
    async def get_today_tweets(self) -> list[Tweet]:
        """获取今日推文"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.get_tweets_since(today)
    
    async def start_collection_run(self, users_count: int) -> CollectionRun:
        """开始新的采集运行"""
        run = CollectionRun(users_count=users_count)
        
        cursor = await self._conn.execute("""
            INSERT INTO collection_runs (started_at, users_count, status)
            VALUES (?, ?, ?)
        """, (run.started_at.isoformat(), users_count, "running"))
        
        await self._conn.commit()
        run.id = cursor.lastrowid
        return run
    
    async def complete_collection_run(self, run: CollectionRun):
        """完成采集运行"""
        run.completed_at = datetime.now()
        run.status = "completed" if run.error_count == 0 else "completed_with_errors"
        
        await self._conn.execute("""
            UPDATE collection_runs SET
                completed_at = ?,
                tweets_count = ?,
                success_count = ?,
                error_count = ?,
                status = ?,
                errors = ?
            WHERE id = ?
        """, (
            run.completed_at.isoformat(), run.tweets_count, run.success_count,
            run.error_count, run.status, run.errors, run.id
        ))
        await self._conn.commit()
    
    async def get_latest_run(self) -> Optional[CollectionRun]:
        """获取最近一次采集运行"""
        cursor = await self._conn.execute("""
            SELECT * FROM collection_runs ORDER BY started_at DESC LIMIT 1
        """)
        row = await cursor.fetchone()
        if row:
            data = dict(row)
            return CollectionRun(
                id=data["id"],
                started_at=datetime.fromisoformat(data["started_at"]),
                completed_at=datetime.fromisoformat(data["completed_at"]) if data["completed_at"] else None,
                users_count=data["users_count"],
                tweets_count=data["tweets_count"],
                success_count=data["success_count"],
                error_count=data["error_count"],
                status=data["status"],
                errors=data["errors"]
            )
        return None
    
    async def cleanup_old_data(self, retention_days: int = 30):
        """清理旧数据"""
        cutoff = datetime.now() - timedelta(days=retention_days)
        await self._conn.execute(
            "DELETE FROM tweets WHERE collected_at < ?",
            (cutoff.isoformat(),)
        )
        await self._conn.commit()
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
