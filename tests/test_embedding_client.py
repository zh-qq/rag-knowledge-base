from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.embedding_client import EmbeddingError, embed_texts
from app.settings import EmbeddingSettings


class EmbeddingClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = EmbeddingSettings(
            api_key="test-key",
            base_url="https://example.com/v1",
            model="text-embedding-v2",
        )

    def test_returns_vectors_from_cloud_response(self) -> None:
        response = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2]), SimpleNamespace(embedding=[0.3, 0.4])]
        )

        with patch("app.embedding_client.OpenAI") as openai_client:
            openai_client.return_value.embeddings.create.return_value = response

            vectors = embed_texts(["第一段", "第二段"], self.settings)

        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])
        openai_client.return_value.embeddings.create.assert_called_once_with(
            model="text-embedding-v2",
            input=["第一段", "第二段"],
        )

    def test_rejects_empty_texts(self) -> None:
        with self.assertRaisesRegex(EmbeddingError, "不能为空"):
            embed_texts([], self.settings)

    def test_sends_large_inputs_in_ordered_batches(self) -> None:
        responses = [
            SimpleNamespace(data=[SimpleNamespace(embedding=[0.1]), SimpleNamespace(embedding=[0.2])]),
            SimpleNamespace(data=[SimpleNamespace(embedding=[0.3])]),
        ]

        with patch("app.embedding_client.OpenAI") as openai_client:
            openai_client.return_value.embeddings.create.side_effect = responses
            vectors = embed_texts(["第一段", "第二段", "第三段"], self.settings, batch_size=2)

        self.assertEqual(vectors, [[0.1], [0.2], [0.3]])
        self.assertEqual(openai_client.return_value.embeddings.create.call_count, 2)
