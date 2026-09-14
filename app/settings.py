import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv


class SettingsError(ValueError):
    """运行所需配置缺失时抛出。"""


@dataclass(frozen=True)
class EmbeddingSettings:
    api_key: str
    base_url: str
    model: str


@dataclass(frozen=True)
class ChatSettings:
    api_key: str
    base_url: str
    model: str


def load_embedding_settings() -> EmbeddingSettings:
    """从本地 .env 和环境变量读取向量服务配置。"""
    load_dotenv()
    return embedding_settings_from_values(os.environ)


def embedding_settings_from_values(values: Mapping[str, str]) -> EmbeddingSettings:
    required_keys = {
        "DASHSCOPE_API_KEY": "api_key",
        "DASHSCOPE_BASE_URL": "base_url",
        "EMBEDDING_MODEL": "model",
    }
    missing_keys = [key for key in required_keys if not values.get(key, "").strip()]
    if missing_keys:
        raise SettingsError(f"缺少配置：{', '.join(missing_keys)}")

    return EmbeddingSettings(
        api_key=values["DASHSCOPE_API_KEY"].strip(),
        base_url=values["DASHSCOPE_BASE_URL"].strip(),
        model=values["EMBEDDING_MODEL"].strip(),
    )


def load_chat_settings() -> ChatSettings:
    """从本地 .env 和环境变量读取对话模型配置。"""
    load_dotenv()
    return chat_settings_from_values(os.environ)


def chat_settings_from_values(values: Mapping[str, str]) -> ChatSettings:
    required_keys = {
        "DASHSCOPE_API_KEY": "api_key",
        "DASHSCOPE_BASE_URL": "base_url",
        "CHAT_MODEL": "model",
    }
    missing_keys = [key for key in required_keys if not values.get(key, "").strip()]
    if missing_keys:
        raise SettingsError(f"缺少配置：{', '.join(missing_keys)}")

    return ChatSettings(
        api_key=values["DASHSCOPE_API_KEY"].strip(),
        base_url=values["DASHSCOPE_BASE_URL"].strip(),
        model=values["CHAT_MODEL"].strip(),
    )
