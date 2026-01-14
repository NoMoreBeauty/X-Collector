"""Google Gemini LLM 实现"""

import json
import re
from pathlib import Path
import google.generativeai as genai
from PIL import Image

from .base import BaseLLM, LLMFactory, TweetData, AnalysisResult


@LLMFactory.register("google")
class GoogleLLM(BaseLLM):
    """Google Gemini Vision 实现"""
    
    def __init__(self, api_key: str, vision_model: str = "gemini-1.5-pro", text_model: str = "gemini-1.5-pro"):
        super().__init__(api_key, vision_model, text_model)
        genai.configure(api_key=api_key)
        self.vision_client = genai.GenerativeModel(vision_model)
        self.text_client = genai.GenerativeModel(text_model)
    
    async def analyze_screenshot(self, image_path: str) -> AnalysisResult:
        """使用 Gemini Vision 分析截图"""
        
        image = Image.open(image_path)
        
        response = await self.vision_client.generate_content_async(
            [self._get_analysis_prompt(), image]
        )
        
        raw_response = response.text
        tweets = self._parse_response(raw_response)
        
        return AnalysisResult(tweets=tweets, raw_response=raw_response)
    
    async def summarize_tweets(self, tweets: list[TweetData]) -> str:
        """使用 Gemini 生成总结"""
        
        prompt = self._get_summary_prompt(tweets)
        
        response = await self.text_client.generate_content_async(prompt)
        
        return response.text
    
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
