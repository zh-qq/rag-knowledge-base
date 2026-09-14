import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from app.text_chunker import DocumentChunk
from app.vector_store import VectorStore, VectorStoreError


class VectorStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = VectorStore(dimension=2)
        self.chunks = [
            DocumentChunk("network.md", 0, "校园网络报修流程"),
            DocumentChunk("library.md", 0, "图书馆开放时间"),
        ]

    def test_returns_most_similar_chunk(self) -> None:
        self.store.add(self.chunks, [[1.0, 0.0], [0.0, 1.0]])

        results = self.store.search([0.9, 0.1], limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_file, "network.md")
        self.assertEqual(results[0].chunk_index, 0)
        self.assertGreater(results[0].score, 0.9)

    def test_returns_empty_results_before_indexing(self) -> None:
        self.assertEqual(self.store.search([1.0, 0.0]), [])

    def test_rejects_mismatched_chunk_and_vector_counts(self) -> None:
        with self.assertRaisesRegex(VectorStoreError, "数量必须一致"):
            self.store.add(self.chunks, [[1.0, 0.0]])

    def test_rejects_wrong_vector_dimension(self) -> None:
        with self.assertRaisesRegex(VectorStoreError, "维度必须为 2"):
            self.store.add([self.chunks[0]], [[1.0, 0.0, 0.0]])

    def test_saves_and_restores_index(self) -> None:
        self.store.add(self.chunks, [[1.0, 0.0], [0.0, 1.0]])

        with TemporaryDirectory() as directory:
            index_path = Path(directory) / "knowledge_base.faiss"
            metadata_path = Path(directory) / "chunks.json"
            self.store.save(index_path, metadata_path)
            restored_store = VectorStore.load(index_path, metadata_path)

        self.assertIsNotNone(restored_store)
        results = restored_store.search([0.9, 0.1], limit=1)
        self.assertEqual(restored_store.count, 2)
        self.assertEqual(results[0].source_file, "network.md")
