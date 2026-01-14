"""定时任务调度器"""

import asyncio
from datetime import datetime
from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz


class Scheduler:
    """定时任务调度器"""
    
    def __init__(self, timezone: str = "Asia/Shanghai"):
        self.timezone = pytz.timezone(timezone)
        self._scheduler = AsyncIOScheduler(timezone=self.timezone)
        self._collect_job = None
    
    def schedule_daily_collection(
        self,
        collect_func: Callable,
        hour: int = 8,
        minute: int = 0
    ):
        """
        设置每日采集任务
        
        Args:
            collect_func: 采集函数 (async)
            hour: 执行小时 (24小时制)
            minute: 执行分钟
        """
        trigger = CronTrigger(hour=hour, minute=minute, timezone=self.timezone)
        
        self._collect_job = self._scheduler.add_job(
            collect_func,
            trigger=trigger,
            id="daily_collection",
            name="Daily Tweet Collection",
            replace_existing=True
        )
        
        print(f"📅 已设置每日采集任务: {hour:02d}:{minute:02d} ({self.timezone})")
    
    def start(self):
        """启动调度器"""
        if not self._scheduler.running:
            self._scheduler.start()
            print("🚀 调度器已启动")
    
    def stop(self):
        """停止调度器"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            print("⏹️ 调度器已停止")
    
    def get_next_run_time(self) -> Optional[datetime]:
        """获取下次执行时间"""
        if self._collect_job:
            return self._collect_job.next_run_time
        return None
    
    def run_now(self, collect_func: Callable):
        """立即执行采集任务"""
        self._scheduler.add_job(
            collect_func,
            id="manual_collection",
            name="Manual Tweet Collection",
            replace_existing=True
        )
    
    async def wait_forever(self):
        """持续运行直到被中断"""
        try:
            while True:
                await asyncio.sleep(3600)  # 每小时检查一次
        except asyncio.CancelledError:
            pass


def parse_time(time_str: str) -> tuple[int, int]:
    """解析时间字符串 (HH:MM) 为 (hour, minute)"""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])
