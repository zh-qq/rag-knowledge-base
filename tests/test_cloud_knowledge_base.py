import unittest
from unittest.mock import patch

from app.knowledge_base_repository import SupabaseKnowledgeBaseRepository
from app.settings import SettingsError, supabase_settings_from_values
from app.text_chunker import DocumentChunk


class CloudKnowledgeBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = supabase_settings_from_values(
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            }
        )
        self.repository = SupabaseKnowledgeBaseRepository(self.settings)

    def test_requires_complete_supabase_settings(self) -> None:
        with self.assertRaisesRegex(SettingsError, "SUPABASE_SERVICE_ROLE_KEY"):
            supabase_settings_from_values({"SUPABASE_URL": "https://example.supabase.co"})

    def test_rebuilds_vector_store_for_one_knowledge_base(self) -> None:
        cloud_rows = [
            {
                "source_file": "network.txt",
                "document_chunks": [
                    {"chunk_index": 0, "content": "校园网络报修请联系信息中心。", "embedding": [1.0, 0.0]},
                    {"chunk_index": 1, "content": "图书馆每天开放至晚上十点。", "embedding": [0.0, 1.0]},
                ],
            }
        ]

        with patch.object(self.repository, "_request", return_value=cloud_rows):
            store = self.repository.load_vector_store(12)

        self.assertIsNotNone(store)
        self.assertEqual(store.count, 2)
        self.assertEqual(store.search([1.0, 0.0], limit=1)[0].source_file, "network.txt")

    def test_saves_one_document_and_its_chunk_batch(self) -> None:
        calls = []

        def fake_request(method, table, query=None, body=None, prefer=None):
            calls.append((method, table, body, prefer))
            return [{"id": 8, "source_file": "guide.md"}] if table == "documents" else []

        with patch.object(self.repository, "_request", side_effect=fake_request):
            self.repository.save_document(
                3,
                "guide.md",
                [DocumentChunk("guide.md", 0, "资料内容")],
                [[0.1, 0.2]],
            )

        self.assertEqual(calls[0][0:2], ("POST", "documents"))
        self.assertEqual(calls[1][0:2], ("POST", "document_chunks"))
        self.assertEqual(calls[1][2][0]["document_id"], 8)
