"""报告生成器 - 生成 Markdown 格式的每日报告"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from jinja2 import Template

from ..storage.models import Tweet


# 报告模板
REPORT_TEMPLATE = """# X 动态采集报告

**生成时间**: {{ generated_at }}
**采集时间范围**: {{ date_range }}
**采集用户数**: {{ users_count }}
**推文总数**: {{ tweets_count }}

---

## 📊 热点摘要

{{ summary }}

---

## 📝 推文详情

{% for user_handle, user_tweets in tweets_by_user.items() %}
### @{{ user_handle }} ({{ user_tweets|length }} 条)

{% for tweet in user_tweets %}
> **{{ tweet.user_name }}** @{{ tweet.user_handle }} · {{ tweet.posted_at or '未知时间' }}
> 
> {{ tweet.content }}
> 
> ❤️ {{ tweet.likes }} | 🔄 {{ tweet.retweets }} | 💬 {{ tweet.replies }}{% if tweet.media_urls %}
> 🖼️ *[媒体内容]* {{ tweet.media_urls }}{% endif %}

{% endfor %}
---

{% endfor %}

## 📈 统计信息

| 指标 | 数值 |
|------|------|
| 采集用户数 | {{ users_count }} |
| 推文总数 | {{ tweets_count }} |
| 总点赞数 | {{ total_likes }} |
| 总转发数 | {{ total_retweets }} |

---

*本报告由 X Information Collector 自动生成*
"""


class ReportGenerator:
    """Markdown 报告生成器"""
    
    def __init__(self, reports_path: str = "reports"):
        self.reports_path = Path(reports_path)
        self.template = Template(REPORT_TEMPLATE)
    
    def generate(
        self,
        tweets: list[Tweet],
        summary: str = "",
        date_range: str = ""
    ) -> str:
        """
        生成报告内容
        
        Args:
            tweets: 推文列表
            summary: AI 生成的摘要
            date_range: 日期范围描述
            
        Returns:
            str: Markdown 格式的报告内容
        """
        # 按用户分组
        tweets_by_user = {}
        for tweet in tweets:
            if tweet.user_handle not in tweets_by_user:
                tweets_by_user[tweet.user_handle] = []
            tweets_by_user[tweet.user_handle].append(tweet)
        
        # 统计数据
        total_likes = sum(t.likes for t in tweets)
        total_retweets = sum(t.retweets for t in tweets)
        
        # 渲染模板
        return self.template.render(
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            date_range=date_range or datetime.now().strftime("%Y-%m-%d"),
            users_count=len(tweets_by_user),
            tweets_count=len(tweets),
            summary=summary or "暂无摘要",
            tweets_by_user=tweets_by_user,
            total_likes=total_likes,
            total_retweets=total_retweets
        )
    
    def save(
        self,
        tweets: list[Tweet],
        summary: str = "",
        filename: Optional[str] = None
    ) -> str:
        """
        生成并保存报告
        
        Args:
            tweets: 推文列表
            summary: AI 摘要
            filename: 文件名 (可选，默认按日期)
            
        Returns:
            str: 保存的文件路径
        """
        # 确保目录存在
        self.reports_path.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        if not filename:
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        filepath = self.reports_path / filename
        
        # 生成并保存
        content = self.generate(tweets, summary)
        filepath.write_text(content, encoding="utf-8")
        
        return str(filepath)
    
    def get_latest_report(self) -> Optional[str]:
        """获取最新的报告文件路径"""
        if not self.reports_path.exists():
            return None
        
        reports = sorted(self.reports_path.glob("report_*.md"), reverse=True)
        return str(reports[0]) if reports else None
