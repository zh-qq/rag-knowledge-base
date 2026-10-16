import unittest

from app.settings import (
    SettingsError,
    app_settings_from_values,
    chat_settings_from_values,
    embedding_settings_from_values,
    rerank_settings_from_values,
    weather_settings_from_values,
)


class EmbeddingSettingsTests(unittest.TestCase):
    def test_creates_settings_from_complete_values(self) -> None:
        settings = embedding_settings_from_values(
            {
                "DASHSCOPE_API_KEY": "test-key",
                "DASHSCOPE_BASE_URL": "https://example.com/v1",
                "EMBEDDING_MODEL": "text-embedding-v2",
            }
        )

        self.assertEqual(settings.model, "text-embedding-v2")
        self.assertEqual(settings.base_url, "https://example.com/v1")

    def test_reports_missing_settings_without_exposing_values(self) -> None:
        with self.assertRaisesRegex(SettingsError, "DASHSCOPE_API_KEY"):
            embedding_settings_from_values({})

    def test_creates_chat_settings_from_complete_values(self) -> None:
        settings = chat_settings_from_values(
            {
                "CHAT_API_KEY": "test-key",
                "CHAT_BASE_URL": "https://example.com/v1",
                "CHAT_MODEL": "qwen-plus",
            }
        )

        self.assertEqual(settings.model, "qwen-plus")

    def test_supports_deepseek_chat_configuration(self) -> None:
        settings = chat_settings_from_values(
            {
                "CHAT_API_KEY": "deepseek-test-key",
                "CHAT_BASE_URL": "https://api.deepseek.com",
                "CHAT_MODEL": "deepseek-flash",
            }
        )

        self.assertEqual(settings.api_key, "deepseek-test-key")
        self.assertEqual(settings.base_url, "https://api.deepseek.com")
        self.assertEqual(settings.model, "deepseek-flash")

    def test_prefers_generic_chat_configuration_over_legacy_dashscope_values(self) -> None:
        settings = chat_settings_from_values(
            {
                "CHAT_API_KEY": "generic-key",
                "CHAT_BASE_URL": "https://api.example.com",
                "CHAT_MODEL": "generic-model",
                "DASHSCOPE_API_KEY": "legacy-key",
                "DASHSCOPE_BASE_URL": "https://legacy.example.com",
            }
        )

        self.assertEqual(settings.api_key, "generic-key")
        self.assertEqual(settings.base_url, "https://api.example.com")

    def test_uses_legacy_dashscope_values_when_generic_chat_values_are_absent(self) -> None:
        settings = chat_settings_from_values(
            {
                "DASHSCOPE_API_KEY": "legacy-key",
                "DASHSCOPE_BASE_URL": "https://legacy.example.com",
                "CHAT_MODEL": "qwen-plus",
            }
        )

        self.assertEqual(settings.api_key, "legacy-key")
        self.assertEqual(settings.base_url, "https://legacy.example.com")

    def test_rejects_partially_configured_generic_chat_settings(self) -> None:
        with self.assertRaisesRegex(SettingsError, "CHAT_API_KEY 与 CHAT_BASE_URL"):
            chat_settings_from_values(
                {
                    "CHAT_API_KEY": "test-key",
                    "CHAT_MODEL": "qwen-plus",
                }
            )

    def test_uses_safe_public_demo_defaults(self) -> None:
        settings = app_settings_from_values({})

        self.assertFalse(settings.public_demo_mode)
        self.assertEqual(settings.max_upload_bytes, 2 * 1024 * 1024)
        self.assertEqual(settings.max_chunk_count, 200)
        self.assertEqual(settings.max_question_length, 1000)

    def test_rejects_invalid_public_demo_flag(self) -> None:
        with self.assertRaisesRegex(SettingsError, "PUBLIC_DEMO_MODE"):
            app_settings_from_values({"PUBLIC_DEMO_MODE": "enabled"})

    def test_creates_rerank_settings_from_environment_values(self) -> None:
        settings = rerank_settings_from_values(
            {
                "DASHSCOPE_API_KEY": "test-key",
                "DASHSCOPE_RERANK_BASE_URL": "https://example.com/compatible-api/v1/",
                "RERANK_MODEL": "qwen3-rerank",
            }
        )

        self.assertEqual(settings.base_url, "https://example.com/compatible-api/v1")
        self.assertEqual(settings.model, "qwen3-rerank")

    def test_creates_weather_settings_from_environment_values(self) -> None:
        settings = weather_settings_from_values(
            {
                "QWEATHER_API_KEY": "test-key",
                "QWEATHER_API_HOST": "https://example.com/",
            }
        )

        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(settings.api_host, "https://example.com")

    def test_rejects_non_https_weather_host(self) -> None:
        with self.assertRaisesRegex(SettingsError, "https"):
            weather_settings_from_values(
                {
                    "QWEATHER_API_KEY": "test-key",
                    "QWEATHER_API_HOST": "http://example.com",
                }
            )
