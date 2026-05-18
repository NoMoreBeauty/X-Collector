"""LLM 抽象基类和工厂"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import base64
from pathlib import Path


@dataclass
class TweetData:
    """推文数据结构"""
    user_handle: str
    user_name: str
    content: str
    posted_at: Optional[str] = None  # 现在是标准 X 时间格式
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


@dataclass
class AnalysisResult:
    """图像分析结果 (API模式下不再使用)"""
    tweets: list[TweetData]
    raw_response: str


class BaseLLM(ABC):
    """LLM 抽象基类，所有供应商实现需继承此类"""
    
    def __init__(self, api_key: str, vision_model: str, text_model: str):
        self.api_key = api_key
        self.vision_model = vision_model
        self.text_model = text_model
    
    @abstractmethod
    async def analyze_screenshot(self, image_path: str) -> AnalysisResult:
        """分析截图 (废弃)"""
        pass
    
    @abstractmethod
    async def summarize_tweets(self, tweets: list[TweetData]) -> str:
        """
        总结推文内容，生成摘要
        
        Args:
            tweets: 推文列表
            
        Returns:
            str: 总结文本
        """
        pass
    
    def _encode_image(self, image_path: str) -> str:
        """将图片编码为 base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def _get_image_mime_type(self, image_path: str) -> str:
        """获取图片 MIME 类型"""
        suffix = Path(image_path).suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_map.get(suffix, "image/png")
    
    def _get_analysis_prompt(self) -> str:
        """获取图像分析提示词 (废弃)"""
        return ""

    def _get_summary_prompt(self, tweets: list[TweetData]) -> str:
        """获取总结提示词"""
        tweets_text = ""
        for t in tweets:
            media_info = f"[含 {len(t.media_urls)} 个媒体]" if t.media_urls else ""
            stats = f"❤️{t.likes} 🔄{t.retweets} 👁️{t.views}"
            tweets_text += f"@{t.user_handle} ({t.user_name}) [{t.posted_at}]:\n{t.content}\n{media_info} {stats}\n---\n"
        
        return f"""你是一位 AI 行业情报分析师，专注于追踪 AI 领域的实质性进展。

以下是过去 24 小时内从 X (Twitter) 采集的 AI 圈推文，请严格按照下方标准进行筛选和总结。

## 重要性判断标准

**必须收录（重大事件）**：
- 新模型 / 新产品正式发布或重大更新
- 重要研究论文 / 技术突破公开
- 公司战略层面的重大决策（融资、并购、裁员、战略转型）
- AI 相关法规、政策、监管动向
- 行业内引发广泛讨论的深度观点（需有实质论据）

**选择性收录（有价值信息）**：
- 技术细节分析、工程实践经验分享
- 有数据支撑的行业趋势洞察
- 值得关注但非头条的产品功能更新

**直接忽略（噪声）**：
- 日常闲聊、个人生活动态
- 无实质内容的会议 / 活动预告
- 纯转发（无评论的 RT）
- 宣传推广、招聘广告
- 重复报道同一事件的多条推文（只取最具信息量的一条）

## 输出格式

### 🔴 今日重大事件
（仅列出真正重要的事件，每条附上关键信息摘要。**如果今天没有重大事件，请直接写"今日无重大进展"，不要用普通内容填充此区域。**）

### 🟡 值得关注
（有价值但非头条的内容，可按以下方向归类：大模型进展 / AI 工具与产品 / AI 研究 / AI 政策与行业动态。此栏可以为空。）

### 📊 今日信号强度
用一句话评价今天整体信息量：【高/中/低】+ 简要说明原因。

---

## 推文原文

{tweets_text}

请用中文回复，使用 Markdown 格式。信息量少的日子请如实说明，不要强行填充内容。"""


class LLMFactory:
    """LLM 工厂类，根据配置创建对应的 LLM 实例"""
    
    _providers: dict[str, type[BaseLLM]] = {}
    
    @classmethod
    def register(cls, name: str):
        """注册 LLM 供应商的装饰器"""
        def decorator(llm_class: type[BaseLLM]):
            cls._providers[name] = llm_class
            return llm_class
        return decorator
    
    @classmethod
    def create(cls, provider: str, api_key: str, vision_model: str, text_model: str) -> BaseLLM:
        """
        创建 LLM 实例
        
        Args:
            provider: 供应商名称 (dashscope, openai, anthropic, google)
            api_key: API 密钥
            vision_model: 视觉模型名称
            text_model: 文本模型名称
            
        Returns:
            BaseLLM: LLM 实例
        """
        if provider not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown provider: {provider}. Available: {available}")
        
        return cls._providers[provider](api_key, vision_model, text_model)
    
    @classmethod
    def available_providers(cls) -> list[str]:
        """获取可用的供应商列表"""
        return list(cls._providers.keys())
