import unittest

from app.text_chunker import TextChunkError, split_document


class TextChunkerTests(unittest.TestCase):
    def test_splits_text_with_overlap(self) -> None:
        chunks = split_document("guide.md", "abcdefghij", chunk_size=4, overlap=1)

        self.assertEqual([chunk.content for chunk in chunks], ["abcd", "defg", "ghij"])
        self.assertEqual([chunk.chunk_index for chunk in chunks], [0, 1, 2])
        self.assertTrue(all(chunk.source_file == "guide.md" for chunk in chunks))

    def test_returns_one_chunk_for_short_text(self) -> None:
        chunks = split_document("notice.txt", "短文本", chunk_size=10, overlap=2)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].content, "短文本")

    def test_rejects_empty_text(self) -> None:
        with self.assertRaisesRegex(TextChunkError, "不能为空"):
            split_document("empty.txt", "   ")

    def test_rejects_invalid_overlap(self) -> None:
        with self.assertRaisesRegex(TextChunkError, "重叠"):
            split_document("guide.md", "content", chunk_size=4, overlap=4)
