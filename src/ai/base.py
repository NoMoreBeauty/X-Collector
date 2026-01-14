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
            media_info = f"[包含 {len(t.media_urls)} 个媒体文件]" if t.media_urls else ""
            stats = f"❤️{t.likes} 🔄{t.retweets} 👁️{t.views}"
            tweets_text += f"@{t.user_handle} ({t.user_name}) [{t.posted_at}]:\n{t.content}\n{media_info} {stats}\n---\n"
        
        return f"""请对以下收集到的 X (Twitter) 推文进行总结和提炼。
这些推文都是在过去24小时内发布的，请基于此进行总结。

推文列表：
{tweets_text}

请提供：
1. **今日核心动态**：最重要的话题摘要 (3-5条)
2. **按主题归类**：将相关推文合并归类 (如"AI进展", "技术讨论", "生活动态"等)
3. **高热度推文**：点赞/转发/浏览量较高且有价值的内容
4. **媒体内容**：如有可识别的图片/视频内容，简要提及

请用中文回复，使用 Markdown 格式，保持专业、简洁。"""


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
