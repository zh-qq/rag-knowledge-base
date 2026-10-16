"""知识库 Agent 的工具调用循环。"""

import ast
import json
from dataclasses import dataclass
from typing import Callable

from openai import APIError, OpenAI

from app.settings import ChatSettings

MAX_TOOL_ROUNDS = 3


class AgentError(RuntimeError):
    """模型工具调用或最终回答不可用时抛出。"""


@dataclass(frozen=True)
class AgentResponse:
    answer: str
    tool_calls: list[str]


SearchKnowledge = Callable[[str, int], dict]
ReadSource = Callable[[int], dict]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "检索知识库。回答任何与资料有关的问题前必须先调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "用于检索的简短问题"},
                    "limit": {
                        "type": "integer",
                        "description": "返回资料数量，范围为 1 到 3，默认 3",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_source",
            "description": "读取上一轮检索结果中某个引用编号的完整原文。只能读取已经检索到的来源。",
            "parameters": {
                "type": "object",
                "properties": {
                    "citation_index": {"type": "integer", "description": "引用编号，从 1 开始"},
                },
                "required": ["citation_index"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算简单四则运算表达式。不得自行心算，必须调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "只包含数字、括号和 + - * / 的表达式"},
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
]


def run_agent(
    question: str,
    settings: ChatSettings,
    search_knowledge: SearchKnowledge,
    read_source: ReadSource,
    history: list[dict[str, str]] | None = None,
) -> AgentResponse:
    """让模型在受控工具之间循环，直到生成最终中文回答。"""
    if not question.strip():
        raise AgentError("问题不能为空")

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "你是知识库 Agent。与知识库有关的问题必须先调用 search_knowledge；"
                "若需查看命中资料完整内容，再调用 read_source。数学表达式必须调用 calculate。"
                "只能使用工具返回的资料回答，资料不足时明确说明。请用简洁中文回答；"
                "引用知识库事实时标注对应编号，例如 [1]。"
            ),
        },
    ]
    messages.extend(history or [])
    messages.append({"role": "user", "content": question})
    tool_calls: list[str] = []

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.chat.completions.create(
                model=settings.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
            message = response.choices[0].message
            requested_tools = message.tool_calls or []
            if not requested_tools:
                if not tool_calls:
                    raise AgentError("模型未调用工具，无法生成可核对的回答")
                if not message.content:
                    raise AgentError("云端对话模型未返回回答")
                return AgentResponse(answer=message.content, tool_calls=tool_calls)

            messages.append(_assistant_tool_message(message))
            for tool_call in requested_tools:
                tool_name = tool_call.function.name
                tool_calls.append(tool_name)
                result = _execute_tool(tool_name, tool_call.function.arguments, search_knowledge, read_source)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
    except APIError as error:
        raise AgentError("云端对话模型调用失败") from error

    raise AgentError("工具调用次数超过上限，请换一种更具体的问法")


def _assistant_tool_message(message: object) -> dict:
    """将 SDK 返回对象转换成 OpenAI 兼容的下一轮消息。"""
    tool_calls = getattr(message, "tool_calls", None) or []
    return {
        "role": "assistant",
        "content": getattr(message, "content", None) or "",
        "tool_calls": [
            {
                "id": item.id,
                "type": "function",
                "function": {
                    "name": item.function.name,
                    "arguments": item.function.arguments,
                },
            }
            for item in tool_calls
        ],
    }


def _execute_tool(
    tool_name: str,
    raw_arguments: str,
    search_knowledge: SearchKnowledge,
    read_source: ReadSource,
) -> dict:
    try:
        arguments = json.loads(raw_arguments)
    except (TypeError, json.JSONDecodeError) as error:
        raise AgentError("模型返回的工具参数不是合法 JSON") from error
    if not isinstance(arguments, dict):
        raise AgentError("模型返回的工具参数格式不正确")

    if tool_name == "search_knowledge":
        query = arguments.get("query")
        limit = arguments.get("limit", 3)
        if not isinstance(query, str) or not query.strip():
            raise AgentError("知识库检索缺少问题")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 3:
            raise AgentError("知识库检索数量必须在 1 到 3 之间")
        return search_knowledge(query, limit)

    if tool_name == "read_source":
        citation_index = arguments.get("citation_index")
        if isinstance(citation_index, bool) or not isinstance(citation_index, int) or citation_index < 1:
            raise AgentError("来源编号必须是从 1 开始的整数")
        return read_source(citation_index)

    if tool_name == "calculate":
        expression = arguments.get("expression")
        if not isinstance(expression, str):
            raise AgentError("计算工具缺少表达式")
        return {"expression": expression, "result": calculate_expression(expression)}

    raise AgentError("模型请求了不支持的工具")


def calculate_expression(expression: str) -> int | float:
    """只解析数字和四则运算，禁止执行任意 Python 代码。"""
    if not expression.strip() or len(expression) > 100:
        raise AgentError("计算表达式不能为空且不能超过 100 个字符")
    try:
        tree = ast.parse(expression, mode="eval")
        return _calculate_node(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError) as error:
        raise AgentError("仅支持数字、括号和四则运算") from error


def _calculate_node(node: ast.expr) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _calculate_node(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _calculate_node(node.left)
        right = _calculate_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right
    raise ValueError("不支持的表达式")
