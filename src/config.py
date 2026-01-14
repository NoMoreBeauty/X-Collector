"""配置加载器"""

import os
from pathlib import Path
from typing import Optional
import yaml
from dotenv import load_dotenv


class Config:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self._config: dict = {}
        self._load()
    
    def _load(self):
        """加载配置"""
        # 加载环境变量
        load_dotenv()
        
        # 加载配置文件
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            # 使用示例配置
            example_path = self.config_path.parent / "config.example.yaml"
            if example_path.exists():
                with open(example_path, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}
        
        # 替换环境变量
        self._resolve_env_vars(self._config)
    
    def _resolve_env_vars(self, obj):
        """递归替换配置中的环境变量引用"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    obj[key] = os.environ.get(env_var, "")
                elif isinstance(value, (dict, list)):
                    self._resolve_env_vars(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str) and item.startswith("${") and item.endswith("}"):
                    env_var = item[2:-1]
                    obj[i] = os.environ.get(env_var, "")
                elif isinstance(item, (dict, list)):
                    self._resolve_env_vars(item)
    
    def get(self, key: str, default=None):
        """获取配置值，支持点号分隔的路径"""
        parts = key.split(".")
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value
    
    @property
    def ai_provider(self) -> str:
        return self.get("ai.provider", "dashscope")
    
    @property
    def ai_api_key(self) -> str:
        """从环境变量获取 API Key"""
        provider = self.ai_provider
        env_map = {
            "dashscope": "DASHSCOPE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY"
        }
        env_var = env_map.get(provider, f"{provider.upper()}_API_KEY")
        return os.environ.get(env_var, "")
    
    @property
    def ai_vision_model(self) -> str:
        provider = self.ai_provider
        return self.get(f"ai.{provider}.vision_model", "")
    
    @property
    def ai_text_model(self) -> str:
        provider = self.ai_provider
        return self.get(f"ai.{provider}.text_model", "")
    
    @property
    def collector_headless(self) -> bool:
        return self.get("collector.headless", True)
    
    @property
    def collector_scroll_times(self) -> int:
        return self.get("collector.scroll_times", 3)
    
    @property
    def collector_scroll_delay(self) -> float:
        return self.get("collector.scroll_delay", 2.0)
    
    @property
    def collector_max_tweets(self) -> int:
        return self.get("collector.max_tweets_per_user", 20)
    
    @property
    def collector_use_system_chrome(self) -> bool:
        return self.get("collector.use_system_chrome", False)
    
    @property
    def screenshots_path(self) -> str:
        return self.get("storage.screenshots_path", "data/screenshots")
    
    @property
    def database_path(self) -> str:
        return self.get("storage.database_path", "data/tweets.db")
    
    @property
    def reports_path(self) -> str:
        return self.get("storage.reports_path", "reports")
    
    @property
    def scheduler_time(self) -> str:
        return self.get("scheduler.daily_collect_time", "08:00")
    
    @property
    def scheduler_timezone(self) -> str:
        return self.get("scheduler.timezone", "Asia/Shanghai")
    
    @property
    def email_enabled(self) -> bool:
        return self.get("email.enabled", False)
    
    @property
    def email_config(self) -> dict:
        """从环境变量和配置文件合并邮件配置"""
        config = self.get("email", {})
        # 从环境变量读取敏感信息
        return {
            "smtp_host": os.environ.get("EMAIL_SMTP_HOST", config.get("smtp_host", "")),
            "smtp_port": int(os.environ.get("EMAIL_SMTP_PORT", config.get("smtp_port", 587))),
            "use_tls": os.environ.get("EMAIL_USE_TLS", "true").lower() == "true",
            "username": os.environ.get("EMAIL_USERNAME", config.get("username", "")),
            "password": os.environ.get("EMAIL_PASSWORD", config.get("password", "")),
            "from_address": os.environ.get("EMAIL_FROM", config.get("from_address", "")),
            "from_address": os.environ.get("EMAIL_FROM", config.get("from_address", "")),
            "to_addresses": [x.strip() for x in os.environ.get("EMAIL_TO_ADDRESSES", "").split(",") if x.strip()] if os.environ.get("EMAIL_TO_ADDRESSES") else config.get("to_addresses", [])
        }


def load_subscriptions(path: str = "config/subscriptions.yaml") -> list[dict]:
    """加载订阅用户列表"""
    filepath = Path(path)
    if not filepath.exists():
        return []
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    return data.get("users", [])
