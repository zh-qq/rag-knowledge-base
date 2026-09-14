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


@dataclass(frozen=True)
class RerankSettings:
    api_key: str
    base_url: str
    model: str


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    secret_key: str


@dataclass(frozen=True)
class AppSettings:
    """公开演示和资源限额配置。"""

    public_demo_mode: bool
    public_demo_knowledge_base_name: str
    max_upload_bytes: int
    max_chunk_count: int
    max_question_length: int
    embedding_batch_size: int


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


def load_rerank_settings() -> RerankSettings:
    """从本地 .env 和环境变量读取重排序模型配置。"""
    load_dotenv()
    return rerank_settings_from_values(os.environ)


def load_supabase_settings() -> SupabaseSettings:
    """从本地 .env 和环境变量读取云端知识库配置。"""
    load_dotenv()
    return supabase_settings_from_values(os.environ)


def load_app_settings() -> AppSettings:
    """从本地 .env 和环境变量读取运行时限额配置。"""
    load_dotenv()
    return app_settings_from_values(os.environ)


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


def rerank_settings_from_values(values: Mapping[str, str]) -> RerankSettings:
    required_keys = {
        "DASHSCOPE_API_KEY": "api_key",
        "DASHSCOPE_RERANK_BASE_URL": "base_url",
        "RERANK_MODEL": "model",
    }
    missing_keys = [key for key in required_keys if not values.get(key, "").strip()]
    if missing_keys:
        raise SettingsError(f"缺少配置：{', '.join(missing_keys)}")

    return RerankSettings(
        api_key=values["DASHSCOPE_API_KEY"].strip(),
        base_url=values["DASHSCOPE_RERANK_BASE_URL"].rstrip("/"),
        model=values["RERANK_MODEL"].strip(),
    )


def supabase_settings_from_values(values: Mapping[str, str]) -> SupabaseSettings:
    required_keys = {
        "SUPABASE_URL": "url",
        "SUPABASE_SECRET_KEY": "secret_key",
    }
    missing_keys = [key for key in required_keys if not values.get(key, "").strip()]
    if missing_keys:
        raise SettingsError(f"缺少配置：{', '.join(missing_keys)}")

    return SupabaseSettings(
        url=values["SUPABASE_URL"].strip(),
        secret_key=values["SUPABASE_SECRET_KEY"].strip(),
    )


def app_settings_from_values(values: Mapping[str, str]) -> AppSettings:
    """解析非敏感运行时配置，并在无配置时使用安全默认值。"""
    public_demo_mode = _read_bool(values, "PUBLIC_DEMO_MODE", False)
    public_demo_knowledge_base_name = values.get(
        "PUBLIC_DEMO_KNOWLEDGE_BASE_NAME", "公开演示知识库"
    ).strip()
    if public_demo_mode and not public_demo_knowledge_base_name:
        raise SettingsError("公开演示模式缺少配置：PUBLIC_DEMO_KNOWLEDGE_BASE_NAME")

    return AppSettings(
        public_demo_mode=public_demo_mode,
        public_demo_knowledge_base_name=public_demo_knowledge_base_name,
        max_upload_bytes=_read_positive_int(values, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024),
        max_chunk_count=_read_positive_int(values, "MAX_CHUNK_COUNT", 200),
        max_question_length=_read_positive_int(values, "MAX_QUESTION_LENGTH", 1000),
        embedding_batch_size=_read_positive_int(values, "EMBEDDING_BATCH_SIZE", 32),
    )


def _read_bool(values: Mapping[str, str], key: str, default: bool) -> bool:
    raw_value = values.get(key, str(default)).strip().lower()
    if raw_value in {"true", "1", "yes"}:
        return True
    if raw_value in {"false", "0", "no"}:
        return False
    raise SettingsError(f"配置 {key} 必须为 true 或 false")


def _read_positive_int(values: Mapping[str, str], key: str, default: int) -> int:
    raw_value = values.get(key, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as error:
        raise SettingsError(f"配置 {key} 必须为正整数") from error
    if value <= 0:
        raise SettingsError(f"配置 {key} 必须为正整数")
    return value
