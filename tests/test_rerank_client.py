from io import BytesIO
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from app.rerank_client import RerankError, rerank_results
from app.settings import RerankSettings
from app.vector_store import SearchResult


class RerankClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = RerankSettings(
            api_key="test-key",
            base_url="https://example.com/compatible-api/v1",
            model="qwen3-rerank",
        )
        self.candidates = [
            SearchResult("guide.md", 0, "图书馆晚上十点关闭。", 0.4),
            SearchResult("network.md", 1, "网络问题请联系信息中心。", 0.9),
        ]

    def test_reranks_candidates_and_preserves_original_sources(self) -> None:
        response = MagicMock()
        response.read.return_value = json.dumps(
            {
                "results": [
                    {"index": 1, "relevance_score": 0.95},
                    {"index": 0, "relevance_score": 0.72},
                ]
            }
        ).encode("utf-8")

        with patch("app.rerank_client.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = response
            results = rerank_results("网络怎么报修？", self.candidates, self.settings, limit=2)

        self.assertEqual([item.source_file for item in results], ["network.md", "guide.md"])
        self.assertEqual(results[0].score, 0.95)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.com/compatible-api/v1/reranks")
        self.assertEqual(json.loads(request.data)["model"], "qwen3-rerank")

    def test_rejects_empty_candidates(self) -> None:
        with self.assertRaisesRegex(RerankError, "没有可重排序"):
            rerank_results("问题", [], self.settings)

    def test_returns_chinese_error_when_remote_request_fails(self) -> None:
        error = HTTPError("https://example.com", 500, "error", {}, BytesIO(b"{}"))

        with patch("app.rerank_client.urlopen", side_effect=error), self.assertRaisesRegex(
            RerankError, "请求失败"
        ):
            rerank_results("问题", self.candidates, self.settings, limit=1)
