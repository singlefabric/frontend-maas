import json
import re
import typing

import pydash

from src.apps.gateway.protocol import ChatContentLine, ChatType, empty_chat_response
from src.common.loggers import logger
from src.setting import settings


class BaseChatStreamResponseParser:
    """
    Parse the chat stream response and yield parsed data.
    """

    def __init__(self, chunk_size: int = 1024):
        self.chunk_size = chunk_size
        self._buffer = b''
        self.is_finish = False
        self.has_parsed = False
        self.tool_arg = {}

        self.reasoning_content = ''
        self.content = ''

    async def process_buffer(self) -> typing.AsyncIterator[ChatContentLine]:
        """
        Process the buffer and yield parsed data.
        """
        while True:
            index = self._buffer.find(b'\n\n')
            if index == -1:
                break

            part_b, self._buffer = self._buffer[:index + 2], self._buffer[index + 2:]
            part_s = part_b.decode('utf-8').strip()

            if not part_s.startswith('data:'):
                yield ChatContentLine(content=part_s)
            else:
                # parse every content line starting with 'data:'
                part_data = part_s.lstrip('data:').strip()

                if part_data == '[DONE]':
                    yield ChatContentLine(content=part_data, type_=ChatType.Done)
                else:
                    try:
                        part_json = json.loads(part_data)
                        choices = part_json.get("choices")

                        if choices:
                            for choice in choices:
                                delta = choice.get("delta", {})

                                # 判断是否结束
                                if choice.get("finish_reason", ""):
                                    self.is_finish = True

                                # 调整数据信息（reasoning_content）
                                self.convert_data(delta)

                                # 拼接推理内容（统计需要）
                                self.reasoning_content += (delta.get('reasoning_content') or '')
                                self.content += (delta.get('content') or '')

                                # 处理 tool_calls 里面 arguments 问题
                                tool_calls = delta.get("tool_calls") or []
                                for tool_call in tool_calls:
                                    _function = tool_call.get('function')
                                    if not _function:
                                        continue
                                    if tool_call['index'] not in self.tool_arg:
                                        self.tool_arg[tool_call['index']] = ''
                                    self.tool_arg[tool_call['index']] += _function.get('arguments') or ''

                        for index, argument in self.tool_arg.items():
                            if not argument and self.is_finish:
                                self.tool_arg[index] = ' {}'
                                func_trunk: dict[str, any] = pydash.pick(part_json, ['id', 'object', 'created', 'model'])
                                func_trunk['choices'] = [
                                    {"index": 0,
                                     "delta": {"content": None, "reasoning_content": None,
                                               "tool_calls": [{"id": "", "index": index, "function": {"arguments": " {}"}}]},
                                     "finish_reason": None}]
                                yield ChatContentLine(content=func_trunk, data=func_trunk)

                        type_ = ChatType.Usage if self.is_finish and part_json.get("usage") else ChatType.Text
                        yield ChatContentLine(content=part_json, data=part_json, type_=type_)
                    except Exception as e:
                        logger.exception(f"Error parsing: {part_s}")
                        yield ChatContentLine(content=part_s, type_=ChatType.Error, data={"error": str(e)})

    async def parse(self, stream) -> typing.AsyncIterator[ChatContentLine]:
        """
        Parse the stream and yield parsed data.
        """
        async for chunk in stream.aiter_raw(self.chunk_size):
            self._buffer += chunk
            async for parsed_data in self.process_buffer():
                yield parsed_data
        if self._buffer:
            yield ChatContentLine(content=empty_chat_response(self._buffer.decode('utf-8')), type_=ChatType.Error)


    def convert_data(self, choices):
        pass


class ThinkChatStreamResponseParser(BaseChatStreamResponseParser):
    """
    Parse the chat stream response and yield parsed data.
    """

    def __init__(self, chunk_size: int = 1024):
        super().__init__(chunk_size)
        self.thinking = True

    def convert_data(self, delta):
        content = delta.get("content")
        reasoning_content = delta.get("reasoning_content")

        if not self.has_parsed and reasoning_content is not None:
            self.has_parsed = True

        # 检测是否 think 结束
        if self.thinking and content is not None:
            if not self.has_parsed and "</think>" in content:
                content = content.replace("</think>", "")
                self.thinking = False
            if self.has_parsed:
                self.thinking = False

        if self.thinking:
            delta["reasoning_content"] = reasoning_content if reasoning_content is not None else content
            delta["content"] = None
        else:
            delta["reasoning_content"] = None
            delta["content"] = content


def get_parser(model_name: str, chunk_size: int = 1024) -> BaseChatStreamResponseParser:
    """
    Get the parser instance by name.
    """
    for expr in settings.THINK_MODELS.split(','):
        if re.match(rf'^{expr}$', model_name):
            return ThinkChatStreamResponseParser(chunk_size=chunk_size)
    return BaseChatStreamResponseParser(chunk_size=chunk_size)