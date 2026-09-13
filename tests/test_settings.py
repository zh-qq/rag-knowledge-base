import unittest

from app.settings import SettingsError, embedding_settings_from_values


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
