"""阿里云 DashScope LLM 实现"""

import json
import re
from typing import Optional
import dashscope
from dashscope import MultiModalConversation, Generation

from .base import BaseLLM, LLMFactory, TweetData, AnalysisResult


@LLMFactory.register("dashscope")
class DashScopeLLM(BaseLLM):
    """阿里云 DashScope 多模态模型实现"""
    
    def __init__(self, api_key: str, vision_model: str = "qwen-vl-max", text_model: str = "qwen-plus"):
        super().__init__(api_key, vision_model, text_model)
        dashscope.api_key = api_key
    
    async def analyze_screenshot(self, image_path: str) -> AnalysisResult:
        """使用通义千问 VL 分析截图"""
        
        # 构建消息
        messages = [
            {
                "role": "user",
                "content": [
                    {"image": f"file://{image_path}"},
                    {"text": self._get_analysis_prompt()}
                ]
            }
        ]
        
        # 调用 API
        response = MultiModalConversation.call(
            model=self.vision_model,
            messages=messages
        )
        
        if response.status_code != 200:
            raise Exception(f"DashScope API error: {response.message}")
        
        raw_response = response.output.choices[0].message.content[0]["text"]
        tweets = self._parse_response(raw_response)
        
        return AnalysisResult(tweets=tweets, raw_response=raw_response)
    
    async def summarize_tweets(self, tweets: list[TweetData]) -> str:
        """使用通义千问生成总结"""
        
        prompt = self._get_summary_prompt(tweets)
        
        response = Generation.call(
            model=self.text_model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response.status_code != 200:
            raise Exception(f"DashScope API error: {response.message}")
        
        # 更健壮的响应解析
        try:
            output = response.output
            if hasattr(output, 'text'):
                return output.text
            elif hasattr(output, 'choices') and output.choices:
                choice = output.choices[0]
                if hasattr(choice, 'message') and choice.message:
                    content = choice.message.content
                    if isinstance(content, str):
                        return content
                    elif isinstance(content, list) and content:
                        return content[0].get("text", str(content))
            # 最后尝试直接转字符串
            return str(output)
        except Exception as e:
            return f"摘要生成失败: {e}"
    
    def _parse_response(self, response: str) -> list[TweetData]:
        """解析 AI 响应为 TweetData 列表"""
        try:
            # 尝试提取 JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析
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
            # 解析失败，返回空列表
            print(f"Failed to parse response: {e}")
            return []
    
    def _parse_number(self, value) -> int:
        """解析数字，支持 1.2K, 3.5M 等格式"""
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
