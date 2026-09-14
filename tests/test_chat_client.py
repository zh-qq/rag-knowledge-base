from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.chat_client import ChatError, answer_from_context
from app.settings import ChatSettings
from app.vector_store import SearchResult


class ChatClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = ChatSettings(
            api_key="test-key",
            base_url="https://example.com/v1",
            model="qwen-plus",
        )
        self.results = [SearchResult("guide.md", 0, "图书馆晚上十点关闭。", 0.9)]

    def test_generates_answer_from_context(self) -> None:
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="图书馆晚上十点关闭。"))]
        )

        with patch("app.chat_client.OpenAI") as openai_client:
            openai_client.return_value.chat.completions.create.return_value = response
            answer = answer_from_context("图书馆几点关闭？", self.results, self.settings)

        self.assertEqual(answer, "图书馆晚上十点关闭。")
        call_arguments = openai_client.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(call_arguments["model"], "qwen-plus")
        self.assertIn("guide.md", call_arguments["messages"][1]["content"])

    def test_rejects_empty_context(self) -> None:
        with self.assertRaisesRegex(ChatError, "没有可用于回答的资料"):
            answer_from_context("图书馆几点关闭？", [], self.settings)
