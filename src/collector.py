"""核心采集器 - 使用 API 模式采集推文"""

import asyncio
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import Config, load_subscriptions
from .api import create_client_from_config, XApiClient
from .api.client import TweetData as ApiTweetData
from .ai import LLMFactory
from .ai.base import TweetData as AiTweetData
from .storage import Database, Tweet, CollectionRun
from .notification import ReportGenerator, EmailNotifier
from .notification.email import EmailConfig

# 导入所有 LLM 实现以注册到工厂（用于摘要）
from .ai import dashscope_llm, openai_llm, anthropic_llm, google_llm

console = Console()


class Collector:
    """X 信息采集器 - API 模式"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._db: Optional[Database] = None
        self._llm = None
        self._api_client: Optional[XApiClient] = None
    
    async def _init_components(self):
        """初始化组件"""
        # 数据库
        self._db = Database(self.config.database_path)
        await self._db.connect()
        
        # LLM（仅用于摘要）
        if self.config.ai_api_key:
            self._llm = LLMFactory.create(
                provider=self.config.ai_provider,
                api_key=self.config.ai_api_key,
                vision_model=self.config.ai_vision_model,
                text_model=self.config.ai_text_model
            )
        
        # API 客户端
        try:
            self._api_client = create_client_from_config()
        except ValueError as e:
            console.print(f"[yellow]⚠️ API 客户端初始化失败: {e}[/yellow]")
            console.print("[yellow]   请在 config/cookies.txt 中配置 auth_token[/yellow]")
    
    async def _cleanup(self):
        """清理资源"""
        if self._db:
            await self._db.close()
    
    async def collect(self, user_handles: Optional[list[str]] = None) -> CollectionRun:
        """
        执行采集任务（API 模式）
        
        Args:
            user_handles: 指定用户列表 (可选，默认采集所有订阅用户)
            
        Returns:
            CollectionRun: 采集运行记录
        """
        await self._init_components()
        
        if not self._api_client:
            console.print("[red]❌ API 客户端未初始化，无法采集[/red]")
            return CollectionRun(status="no_api_client")
        
        try:
            # 加载用户列表
            all_users = load_subscriptions()
            if user_handles:
                users = [u for u in all_users if u.get("handle") in user_handles]
            else:
                users = all_users
            
            if not users:
                console.print("[yellow]⚠️ 没有找到要采集的用户[/yellow]")
                return CollectionRun(status="no_users")
            
            console.print(f"[cyan]📋 准备采集 {len(users)} 个用户 (API 模式)...[/cyan]")
            
            # 开始采集记录
            run = await self._db.start_collection_run(len(users))
            
            all_tweets = []
            tweets_per_user = self.config.collector_max_tweets
            
            # 使用线程池执行同步 API 调用（避免 asyncio 冲突）
            import concurrent.futures
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                
                for user in users:
                    handle = user.get("handle", "")
                    name = user.get("name", "")
                    
                    task = progress.add_task(f"采集 @{handle}...", total=None)
                    
                    try:
                        # 在线程池中执行同步 API 调用
                        loop = asyncio.get_event_loop()
                        api_tweets = await loop.run_in_executor(
                            executor,
                            lambda: self._api_client.get_user_tweets(handle, count=tweets_per_user)
                        )
                        
                        if api_tweets:
                            # 过滤非最近24小时推文
                            recent_tweets = [t for t in api_tweets if t.is_recent()]
                            skipped_count = len(api_tweets) - len(recent_tweets)
                            
                            # 转换为 Tweet 对象
                            for t in recent_tweets:
                                tweet = Tweet(
                                    id=t.tweet_id,
                                    user_handle=t.user_handle or handle,
                                    user_name=t.user_name or name,
                                    content=t.content,
                                    posted_at=t.posted_at,
                                    likes=t.likes,
                                    retweets=t.retweets,
                                    replies=t.replies,
                                    views=t.views,
                                    is_retweet=t.is_retweet,
                                    original_author=t.original_author,
                                    media_urls=",".join(t.media_urls) if t.media_urls else ""
                                )
                                all_tweets.append(tweet)
                            
                            run.success_count += 1
                            msg = f"✅ @{handle}: {len(recent_tweets)} 条24小时内推文"
                            if skipped_count > 0:
                                msg += f" (跳过 {skipped_count} 条旧推文)"
                            progress.update(task, description=msg)
                        else:
                            run.success_count += 1
                            progress.update(task, description=f"⚠️ @{handle}: 暂无推文")
                            
                    except Exception as e:
                        run.error_count += 1
                        run.add_error(f"@{handle}: {str(e)}")
                        console.print(f"[red]❌ @{handle}: {e}[/red]")
                    
                    progress.remove_task(task)
                    
                    # 添加延迟避免请求过快
                    await asyncio.sleep(1)
            
            executor.shutdown(wait=False)
            
            # 保存推文
            if all_tweets:
                new_count = await self._db.save_tweets(all_tweets)
                run.tweets_count = new_count
                console.print(f"[green]✅ 保存了 {new_count} 条新推文[/green]")
            
            # 完成采集记录
            await self._db.complete_collection_run(run)
            
            return run
            
        finally:
            await self._cleanup()
    
    async def generate_report(self, with_summary: bool = True) -> str:
        """
        生成今日报告
        
        Args:
            with_summary: 是否包含 AI 摘要
            
        Returns:
            str: 报告文件路径
        """
        await self._init_components()
        
        try:
            # 获取今日推文
            tweets = await self._db.get_today_tweets()
            
            if not tweets:
                console.print("[yellow]⚠️ 今日没有采集到推文[/yellow]")
                return ""
            
            console.print(f"[cyan]📝 生成报告，包含 {len(tweets)} 条推文...[/cyan]")
            
            # 生成摘要
            summary = ""
            if with_summary and self._llm and tweets:
                console.print("[cyan]🤖 AI 正在生成摘要...[/cyan]")
                # 限制数量避免超出 token 限制 (用户要求最多50条)
                # 简单按采集时间排序 (数据库默认 DESC)
                limited_tweets = tweets[:50]
                
                tweet_data_list = [
                    AiTweetData(
                        user_handle=t.user_handle,
                        user_name=t.user_name,
                        content=t.content,
                        posted_at=t.posted_at,
                        likes=t.likes,
                        retweets=t.retweets,
                        replies=t.replies,
                        views=t.views,
                        media_urls=t.media_urls.split(",") if t.media_urls else []
                    )
                    for t in limited_tweets
                ]
                summary = await self._llm.summarize_tweets(tweet_data_list)
            
            # 生成报告
            generator = ReportGenerator(self.config.reports_path)
            report_path = generator.save(tweets, summary)
            
            console.print(f"[green]✅ 报告已保存: {report_path}[/green]")
            
            return report_path
            
        finally:
            await self._cleanup()
    
    async def send_notification(self, report_path: str) -> bool:
        """发送邮件通知"""
        if not self.config.email_enabled:
            console.print("[yellow]⚠️ 邮件通知未启用[/yellow]")
            return False
        
        await self._init_components()
        
        try:
            tweets = await self._db.get_today_tweets()
            users = load_subscriptions()
            
            # 生成摘要
            summary = "暂无摘要"
            if self._llm and tweets:
                # 限制数量避免超出 token 限制，优先取最新的
                tweet_data_list = [
                    AiTweetData(
                        user_handle=t.user_handle,
                        user_name=t.user_name,
                        content=t.content,
                        posted_at=t.posted_at,
                        likes=t.likes,
                        retweets=t.retweets,
                        replies=t.replies,
                        views=t.views,
                        media_urls=t.media_urls.split(",") if t.media_urls else []
                    )
                    for t in tweets[:50]  # 增加限制到50
                ]
                summary = await self._llm.summarize_tweets(tweet_data_list)
            
            # 发送邮件
            email_cfg = self.config.email_config
            notifier = EmailNotifier(EmailConfig(
                smtp_host=email_cfg.get("smtp_host", ""),
                smtp_port=email_cfg.get("smtp_port", 587),
                use_tls=email_cfg.get("use_tls", True),
                username=email_cfg.get("username", ""),
                password=email_cfg.get("password", ""),
                from_address=email_cfg.get("from_address", ""),
                to_addresses=email_cfg.get("to_addresses", [])
            ))
            
            success = await notifier.send_daily_report(
                tweets_count=len(tweets),
                users_count=len(users),
                summary=summary,
                report_path=report_path
            )
            
            if success:
                console.print("[green]✅ 邮件发送成功[/green]")
            else:
                console.print("[red]❌ 邮件发送失败[/red]")
            
            return success
            
        finally:
            await self._cleanup()


async def run_collection(user_handles: Optional[list[str]] = None):
    """便捷函数：执行采集"""
    collector = Collector()
    return await collector.collect(user_handles)


async def run_full_pipeline(user_handles: Optional[list[str]] = None):
    """便捷函数：完整流程（采集 + 报告 + 通知）"""
    collector = Collector()
    
    # 采集
    await collector.collect(user_handles)
    
    # 生成报告
    report_path = await collector.generate_report()
    
    # 发送通知
    if report_path:
        await collector.send_notification(report_path)
