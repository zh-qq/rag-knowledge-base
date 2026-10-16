from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.agent_service import AgentError, calculate_expression, run_agent
from app.settings import ChatSettings


def tool_call(name: str, arguments: str, call_id: str = "tool-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def response(content: str | None, tool_calls: list[SimpleNamespace] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


class AgentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = ChatSettings("test-key", "https://example.com/v1", "deepseek-flash")

    def test_calls_knowledge_tool_then_returns_answer(self) -> None:
        search_knowledge = Mock(
            return_value={
                "sources": [
                    {"citation_index": 1, "source_file": "guide.md", "content": "图书馆十点关闭。"}
                ]
            }
        )
        first_response = response(None, [tool_call("search_knowledge", '{"query": "图书馆几点关门？"}')])
        final_response = response("图书馆晚上十点关闭。[1]")

        with patch("app.agent_service.OpenAI") as openai_client:
            openai_client.return_value.chat.completions.create.side_effect = [
                first_response,
                final_response,
            ]
            result = run_agent("图书馆几点关门？", self.settings, search_knowledge, Mock())

        self.assertEqual(result.answer, "图书馆晚上十点关闭。[1]")
        self.assertEqual(result.tool_calls, ["search_knowledge"])
        search_knowledge.assert_called_once_with("图书馆几点关门？", 3)
        second_request = openai_client.return_value.chat.completions.create.call_args_list[1].kwargs
        self.assertEqual(second_request["messages"][-1]["role"], "tool")
        self.assertIn("guide.md", second_request["messages"][-1]["content"])

    def test_calculates_expression_without_executing_code(self) -> None:
        self.assertEqual(calculate_expression("(8 + 2) * 3 / 5"), 6)
        with self.assertRaisesRegex(AgentError, "仅支持数字"):
            calculate_expression("__import__('os').system('dir')")

    def test_rejects_invalid_tool_arguments(self) -> None:
        invalid_response = response(None, [tool_call("search_knowledge", "not-json")])

        with patch("app.agent_service.OpenAI") as openai_client:
            openai_client.return_value.chat.completions.create.return_value = invalid_response
            with self.assertRaisesRegex(AgentError, "不是合法 JSON"):
                run_agent("图书馆几点关门？", self.settings, Mock(), Mock())

    def test_rejects_answer_without_any_tool_call(self) -> None:
        direct_response = response("图书馆晚上十点关闭。")

        with patch("app.agent_service.OpenAI") as openai_client:
            openai_client.return_value.chat.completions.create.return_value = direct_response
            with self.assertRaisesRegex(AgentError, "未调用工具"):
                run_agent("图书馆几点关门？", self.settings, Mock(), Mock())
