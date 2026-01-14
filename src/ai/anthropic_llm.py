"""Anthropic Claude LLM 实现"""

import json
import re
from anthropic import AsyncAnthropic

from .base import BaseLLM, LLMFactory, TweetData, AnalysisResult


@LLMFactory.register("anthropic")
class AnthropicLLM(BaseLLM):
    """Anthropic Claude 3 Vision 实现"""
    
    def __init__(self, api_key: str, vision_model: str = "claude-3-sonnet-20240229", text_model: str = "claude-3-sonnet-20240229"):
        super().__init__(api_key, vision_model, text_model)
        self.client = AsyncAnthropic(api_key=api_key)
    
    async def analyze_screenshot(self, image_path: str) -> AnalysisResult:
        """使用 Claude 3 Vision 分析截图"""
        
        base64_image = self._encode_image(image_path)
        mime_type = self._get_image_mime_type(image_path)
        
        response = await self.client.messages.create(
            model=self.vision_model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": base64_image
                            }
                        },
                        {
                            "type": "text",
                            "text": self._get_analysis_prompt()
                        }
                    ]
                }
            ]
        )
        
        raw_response = response.content[0].text
        tweets = self._parse_response(raw_response)
        
        return AnalysisResult(tweets=tweets, raw_response=raw_response)
    
    async def summarize_tweets(self, tweets: list[TweetData]) -> str:
        """使用 Claude 生成总结"""
        
        prompt = self._get_summary_prompt(tweets)
        
        response = await self.client.messages.create(
            model=self.text_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    def _parse_response(self, response: str) -> list[TweetData]:
        """解析 AI 响应为 TweetData 列表"""
        try:
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response
            
            data = json.loads(json_str)
            tweets_data = data.get("tweets", [])
            
            return [
                TweetData(
                    user_handle=t.get("user_handle", ""),
                    user_name=t.get("user_name", ""),
                    content=t.get("content", ""),
                    posted_at=t.get("posted_at"),
                    likes=self._parse_number(t.get("likes", 0)),
                    retweets=self._parse_number(t.get("retweets", 0)),
                    replies=self._parse_number(t.get("replies", 0)),
                    media_description=t.get("media_description"),
                    is_retweet=t.get("is_retweet", False),
                    original_author=t.get("original_author")
                )
                for t in tweets_data
            ]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to parse response: {e}")
            return []
    
    def _parse_number(self, value) -> int:
        """解析数字"""
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            value = value.strip().upper()
            multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}
            for suffix, mult in multipliers.items():
                if value.endswith(suffix):
                    try:
                        return int(float(value[:-1]) * mult)
                    except ValueError:
                        return 0
            try:
                return int(value.replace(",", ""))
            except ValueError:
                return 0
        return 0
