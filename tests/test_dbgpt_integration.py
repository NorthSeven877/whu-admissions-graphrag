"""Run with the DB-GPT virtual environment to verify the retrieval adapter."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from dbgpt.core.interface.llm import ModelOutput
from dbgpt_app.scene import BaseChat
from dbgpt_app.scene.chat_knowledge.v1.chat import ChatKnowledge


class GraphIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def make_chat(self):
        chat = ChatKnowledge.__new__(ChatKnowledge)
        chat.space_context = None
        chat.current_user_input = SimpleNamespace(last_text="强基计划综合成绩怎么算？")
        chat.knowledge_space = "whu_admission"
        chat._graph_documents = [{
            "title": "2026年强基计划招生简章",
            "date": "2026-04-09",
            "url": "https://aoff.whu.edu.cn/info/1114/26942.htm",
            "text": "综合成绩=高考成绩×85%＋综合能力测试折算成绩×15%",
        }]
        return chat

    async def test_policy_context_uses_graph_documents(self):
        chat = self.make_chat()
        client = AsyncMock()
        client.post.return_value = httpx.Response(
            200, json={"documents": chat._graph_documents},
            request=httpx.Request("POST", "http://localhost/retrieve"),
        )
        manager = AsyncMock()
        manager.__aenter__.return_value = client
        with patch.dict("os.environ", {"WHU_GRAPH_RETRIEVE_URL": "http://localhost/retrieve"}):
            with patch("httpx.AsyncClient", return_value=manager):
                values = await chat.generate_input_values()
        self.assertIn("85%", values["context"])
        self.assertIn("[1]", values["context"])
        self.assertEqual(values["question"], chat.current_user_input.last_text)
        self.assertEqual(chat.chunks_with_score, [])

    async def test_incremental_answer_appends_sources_once(self):
        async def stream(*args, **kwargs):
            yield ModelOutput.build("高考成绩占85%。", "")
            yield ModelOutput.build("", "")

        with patch.object(BaseChat, "stream_call", stream):
            outputs = [value async for value in self.make_chat().stream_call(False, True)]
        answer = "".join(value.text for value in outputs)
        self.assertEqual(answer.count("依据资料"), 1)
        self.assertIn("https://aoff.whu.edu.cn/info/1114/26942.htm", answer)

    async def test_snapshot_keeps_answer_with_sources(self):
        async def stream(*args, **kwargs):
            yield ModelOutput.build("高考成绩占85%。", "")

        with patch.object(BaseChat, "stream_call", stream):
            outputs = [value async for value in self.make_chat().stream_call(False, False)]
        self.assertIn("高考成绩占85%", outputs[-1].text)
        self.assertIn("依据资料", outputs[-1].text)

    async def test_failed_model_output_has_no_sources(self):
        async def stream(*args, **kwargs):
            yield ModelOutput.build("模型连接失败", "", error_code=1)

        with patch.object(BaseChat, "stream_call", stream):
            outputs = [value async for value in self.make_chat().stream_call(False, True)]
        self.assertEqual(len(outputs), 1)
        self.assertFalse(outputs[0].success)


if __name__ == "__main__":
    unittest.main()
