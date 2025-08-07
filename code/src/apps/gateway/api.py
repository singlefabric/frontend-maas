# -*- coding: utf-8 -*-
import asyncio
import re
import time
from http import HTTPStatus

import pydash
import tiktoken
from fastapi import APIRouter, Request, Form, UploadFile, File, Response
from httpx import AsyncClient, TimeoutException, HTTPError
from starlette.responses import JSONResponse, StreamingResponse
from starlette.types import Receive

from src.apps.apikey.rsp_schema import ApiKey
from src.apps.channel.curd import channel_curd
from src.apps.gateway.curd import validate_auth
from src.apps.gateway.protocol import ChatCompletionRequest, ChatType, CompletionRequest
from src.apps.gateway.req_schema import TTSReq, EmbeddingsReq, RerankerReq
from src.apps.gateway.rsp_schema import ModelsRsp, ModelInfo
from src.apps.gateway.stream_parser import get_parser
from src.apps.model.curd import model_param_curd
from src.apps.model.rsp_schema import ModelParam
from src.apps.rate_limiter.limiter import limiter
from src.common.const.comm_const import API_KEY_PREFIX, API_INVOKE_EVENT_QUEUE, ModelTag, MetricUnit, LANGUAGE, \
    API_ERROR_EVENT_QUEUE
from src.common.context import Context
from src.common.exceptions import GatewayException
from src.common.loggers import logger
from src.common.utils.data import date_to_utc_fmt, count_characters, replace_model
from src.setting import settings
from src.system.integrations.cache.redis_client import redis_client

api_router = APIRouter(prefix="/v1", tags=["推理服务接口"])
token_encoder = tiktoken.get_encoding("o200k_base")


class ChatStreamingResponse(StreamingResponse):

    def __init__(self, request: Request, url: str, headers: dict, body: dict, channel, api_key_data, proxy_model):
        self.model = body['model']
        self.parser = get_parser(self.model)
        self.api_key_data = api_key_data
        self.channel = channel
        self.start_time = time.time()
        self.body_ = body
        super().__init__(stream_response(request, url, headers, body, channel, api_key_data, proxy_model, self.parser),
                         media_type='text/event-stream')

    async def listen_for_disconnect(self, receive: Receive) -> None:
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                # 计算用量
                prompt_str = ''.join((item.get('content') or '') for item in self.body_.get('messages', []))
                prompt_tokens = len(token_encoder.encode(prompt_str))
                completion_tokens = len(token_encoder.encode(self.parser.reasoning_content + self.parser.content))
                usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                }
                submit_api_invoke(self.model, self.channel, usage, self.api_key_data, ModelTag.CHAT, time.time() - self.start_time)
                logger.warn(f'[{self.api_key_data.creator}]客户端主动断开连接: '
                            f'{len(self.parser.reasoning_content)} / {len(self.parser.content)}')
                break


async def get_proxy_channel(request :Request, model: str, api_key: str=None, req_path=None):
    model_chanel_dict = await channel_curd.query_model_channel_and_cache()
    if model not in model_chanel_dict:
        raise GatewayException(f"未找到模型[{model}]的渠道", HTTPStatus.BAD_REQUEST)

    channels = model_chanel_dict.get(model)
    healthy_channels = pydash.filter_(channels, 'health_status')
    channels = healthy_channels if len(healthy_channels) else channels
    if len(channels) == 1:
        channel = channels[0]
    elif api_key:
        index = abs(hash(api_key)) % len(channels)
        channel = channels[index]
    else:
        channel = pydash.sample(model_chanel_dict.get(model))

    # 代理 model
    proxy_model = channel['model_redirection'].get(model) if channel['model_redirection'] and model in channel['model_redirection'] else model

    # 代理 url，逻辑：1. 以 '/' 结尾忽略 '/v1' 2. 以 '#' 结尾强制使用
    proxy_host = channel.get('inference_service')
    req_path = (req_path or request.url.path.removeprefix(settings.API_PREFIX)).removeprefix('/v1')
    if proxy_host.endswith('#'):
        proxy_url = proxy_host[:-1]
    elif proxy_host.endswith('/'):
        proxy_url = proxy_host[:-1] + req_path
    else:
        proxy_url = proxy_host + '/v1' + req_path
    return channel, proxy_model, proxy_url


def submit_api_invoke(model, channel, usage, api_key_data: ApiKey, model_tag: ModelTag, cost_time: float = 0):
    """
    调用数据上报
    """
    data = {
        'model': model,
        'channel_id': channel['channel_id'],
        'user_id': api_key_data.creator,
        'api_key': api_key_data.id,
        'model_tag': model_tag.value,
        'date_time': date_to_utc_fmt(),
        'cost_time': cost_time,
        'trace_id': Context.TRACE_ID.get() or '',
    }
    data.update({k: v for k, v in usage.items() if k != "prompt_tokens_details" and v is not None})
    if "prompt_tokens_details" in usage and usage["prompt_tokens_details"]:
        prompt_details = usage["prompt_tokens_details"]
        cached_tokens = prompt_details.get("cached_tokens", 0)
        input_tokens = max(data.get("prompt_tokens", 0) - cached_tokens, 0)
        data["cached_tokens"] = cached_tokens
        data["prompt_tokens"] = input_tokens
    logger.info(f'[API INVOKE] {data}')
    asyncio.create_task(redis_client.product_msg(API_INVOKE_EVENT_QUEUE, data))
    asyncio.create_task(limiter.set_token_usage(api_key_data.creator, model, usage.get('total_tokens', 0)))


def submit_http_error(model, channel, api_key_data, cost_time, e, stream=False):
    msg, code = '服务器繁忙', HTTPStatus.SERVICE_UNAVAILABLE
    except_name = type(e).__name__
    except_msg = str(e)

    asyncio.create_task(redis_client.product_msg(API_ERROR_EVENT_QUEUE, {
        'model': model,
        'channel_id': channel['channel_id'],
        'user_id': api_key_data.creator,
        'api_key': api_key_data.id,
        'date_time': date_to_utc_fmt(),
        'cost_time': cost_time,
        'err': except_name,
        'message': except_msg,
        'stream': int(stream),
        'trace_id': Context.TRACE_ID.get() or '',
    }))

    if isinstance(e, GatewayException) and not stream:
        raise e

    log_content = (f"[推理服务] [{channel['channel_id']} {api_key_data.creator} {api_key_data.id} "
                   f"{'stream' if stream else ''}]调用接口异常: [{except_name}][{except_msg}]")
    if isinstance(e, TimeoutException):
        msg, code = '请求超时', HTTPStatus.GATEWAY_TIMEOUT
    elif isinstance(e, HTTPError):
        logger.error(log_content)
    else:
        logger.exception(log_content, exc_info=e)
    if not stream:
        raise GatewayException(msg, code)


async def http_client_send(client: AsyncClient, method, url, model, proxy_model, channel, api_key_data,
                           headers=None, json_=None, data=None, files=None, timeout=10):
    start_time = time.time()
    try:
        response = await client.request(method, url, headers=headers, json=replace_model(json_, proxy_model),
                                        data=replace_model(data, proxy_model), files=files, timeout=timeout)
        code = response.status_code
        if code != 200:
            ret, msg = '', ''
            try:
                ret = response.json()
                msg = pydash.get(ret, 'message', '服务接口异常')
            except Exception:  # noqa
                pass
            logger.warning(f'[推理服务] 调用接口[{url}] 异常: [{code}][{ret}]')
            raise GatewayException(msg, code)
        return response, time.time() - start_time
    except Exception as e:
        submit_http_error(model, channel, api_key_data, time.time() - start_time, e)


async def stream_response(request: Request, url: str, headers: dict, body: dict, channel, api_key_data, proxy_model, parser):
    """
    代理流式请求
    """
    start_time = time.time()
    try:
        json = replace_model(body, proxy_model)
        json['stream_options'] = {"include_usage": True}
        async with AsyncClient() as client:
            async with client.stream(request.method, url, headers=headers, json=json, timeout=300) as stream:
                async for content in parser.parse(stream):  # noqa
                    if content.type_ == ChatType.Usage:
                        # 业务数据（包含 choices）和 usage 在同一条，则正常返回，防止业务数据丢失
                        if (content.data and content.data.get('choices')) or pydash.get(body, 'stream_options.include_usage'):
                            yield content.content
                        submit_api_invoke(body['model'], channel, content.data.get('usage'), api_key_data,
                                          ModelTag.CHAT, time.time() - start_time)
                    else:
                        yield content.content

    except Exception as e:
        submit_http_error(body['model'], channel, api_key_data, time.time() - start_time, e, stream=True)
        yield 'data: {"id":"","object":"chat.completion.chunk","model":"' + body['model'] + '","choices":[{"index":0,"delta":{"role":null,"content":"服务器繁忙，请稍后再试。"},"finish_reason":"stop"}],"usage":null}\n\n'


@api_router.get("/models", description="查询用户可用的模型")
async def models() -> ModelsRsp:
    model_chanel_dict = await asyncio.create_task(channel_curd.query_model_channel_and_cache())
    data = [ModelInfo(id=model) for model in model_chanel_dict.keys()]
    return ModelsRsp(data=data)


async def generate(request: Request):
    body = await request.json()
    model = body['model']
    api_key_data: ApiKey = await validate_auth(model, request, MetricUnit.TOKEN)
    channel, proxy_model, proxy_url = await get_proxy_channel(request, model, api_key=api_key_data.id)

    # 设置默认的 max_tokens
    param_dict = await model_param_curd.get_by_model_name(model)
    param = param_dict.get('max_tokens', ModelParam(key='max_tokens', value='4096', max='8192', tag_id=''))
    if not body.get('max_tokens'):
        body['max_tokens'] = int(param.value)
    body['max_tokens'] = min(body['max_tokens'], int(param.max))

    headers = {'Authorization': API_KEY_PREFIX + channel.get('inference_secret_key')}
    if not body.get('stream'):
        async with AsyncClient() as client:
            response, cost_time = await http_client_send(client, request.method, proxy_url, model, proxy_model, channel,
                                                         api_key_data, headers=headers, json_=body, timeout=300)
            ret_data = response.json()
            for expr in settings.THINK_MODELS.split(','):
                if re.match(rf'^{expr}$', model):
                    reasoning_content = pydash.get(ret_data, 'choices[0].message.reasoning_content') or ''
                    content = pydash.get(ret_data, 'choices[0].message.content') or ''
                    think_index = content.find('</think>')
                    if not reasoning_content and think_index != -1:
                        ret_data['choices'][0]['message']['reasoning_content'] = content[:think_index]
                        ret_data['choices'][0]['message']['content'] = content[think_index + len('</think>'):]
                    break

            submit_api_invoke(body['model'], channel, ret_data.get('usage'), api_key_data, ModelTag.CHAT, cost_time)
            return ret_data

    return ChatStreamingResponse(request, proxy_url, headers, body, channel, api_key_data, proxy_model)

@api_router.post("/chat/completions")
async def chat(_: ChatCompletionRequest, request: Request):
    """
    大模型会话接口，支持流式和非流式
    {
      "id": "chatcmpl-123",
      "object": "chat.completion",
      "created": 1677652288,
      "choices": [{
        "index": 0,
        "message": { "role": "assistant", "content": "\n\nHello there, how may I assist you today?", },
        "finish_reason": "stop"
      }],
      "usage": { "prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21,
                 "prompt_tokens_details": {"cached_tokens": 8}
               }
    }
    """
    return await generate(request)


@api_router.post("/completions")
async def completions(_: CompletionRequest, request: Request):
    return await generate(request)


async def do_speech(request: Request, model: str, input: str, voice: str = '', prompt_text: str = '',
                    prompt_wav: UploadFile = None, speed: float = 1.0):
    """
    文字转语音接口逻辑
    """
    api_key_data: ApiKey = await validate_auth(model, request, MetricUnit.WORDS)
    channel, proxy_model, proxy_url = await get_proxy_channel(request, model, api_key=api_key_data.id, req_path='/v1/audio/speech')
    speed = max(0.5, min(speed, 2))
    headers = {'Authorization': API_KEY_PREFIX + channel.get('inference_secret_key')}
    data = {
        'input': input,
        'voice': voice,
        'prompt_text': prompt_text,
        'speed': speed,
        'trace_id': Context.TRACE_ID.get(),
    }
    files = {}
    if prompt_wav:
        file_content = await prompt_wav.read()
        files['prompt_wav'] = (prompt_wav.filename, file_content)

    # 先不考虑流式场景
    async with AsyncClient() as client:
        response, cost_time = await http_client_send(client, request.method, proxy_url, model, proxy_model, channel,
                                                     api_key_data, headers=headers, data=data, files=files, timeout=300)
        speech_length = int(float(response.headers.get('speech-length', 0)))
        words = count_characters(input)
        logger.info(f'TTS 接口响应，语音时长[{speech_length}], 字符数[{words}]')
        submit_api_invoke(model, channel, {'words': words}, api_key_data, ModelTag.TTS, cost_time)
        return Response(content=response.content, media_type="audio/wav")


@api_router.post("/audio/speech-ext")
async def speech_ext(request: Request, model: str = Form(), input: str = Form(), voice: str = Form(''),
                     prompt_text: str = Form(''), prompt_wav: UploadFile = File(None), speed: float = Form(1.0)):
    return await do_speech(request, model, input, voice, prompt_text, prompt_wav, speed=speed)


@api_router.post("/audio/speech")
async def speech(request: Request, tts_req: TTSReq):
    return await do_speech(request, tts_req.model, tts_req.input, tts_req.voice, speed=tts_req.speed)


@api_router.post("/audio/transcriptions")
async def transcriptions(request: Request, model: str = Form(), file: UploadFile = File(None), lang: LANGUAGE = Form(
    "auto", description="language of audio content")):
    api_key_data: ApiKey = await validate_auth(model, request, MetricUnit.SECONDS)
    channel, proxy_model, proxy_url = await get_proxy_channel(request, model, api_key=api_key_data.id)

    headers = {'Authorization': API_KEY_PREFIX + channel.get('inference_secret_key')}
    file_content = await file.read()
    files = {
        'files': (file.filename, file_content),
        'lang': (None, lang),
    }
    async with AsyncClient() as client:
        response, cost_time = await http_client_send(client, request.method, proxy_url, model, proxy_model, channel,
                                                     api_key_data, headers=headers, files=files, timeout=300)
        ret_data = response.json()
        if 'result' in ret_data and len(ret_data['result']) > 0:
            speech_length = int(pydash.head(ret_data.get('audio_lengths')) or 0)
            submit_api_invoke(model, channel, {'speech_length': speech_length}, api_key_data, ModelTag.ASR, cost_time)
            logger.info(
                f'ASR 接口响应，语音时长[{speech_length}], token 数量[{ret_data.get("result")[0].get("token_size")}]')
            return JSONResponse({'text': ret_data.get('result')[0].get("text")})
        else:
            return JSONResponse(ret_data)


async def common_proxy(model: str, request: Request, metric_unit: MetricUnit, model_tag: ModelTag, usage_field='usage',
                       req_path=None, body=None):
    api_key_data: ApiKey = await validate_auth(model, request, metric_unit)
    channel, proxy_model, proxy_url = await get_proxy_channel(request, model, api_key=api_key_data.id, req_path=req_path)
    headers = {'Authorization': API_KEY_PREFIX + channel.get('inference_secret_key')}
    body = body or (await request.json())
    async with AsyncClient() as client:
        response, cost_time = await http_client_send(client, request.method, proxy_url, model, proxy_model, channel,
                                                     api_key_data, headers=headers, json_=body, timeout=10)
        ret_data = response.json()
        logger.debug(f'[PROXY] 请求 [{proxy_url}][{body}]: {ret_data}')
        submit_api_invoke(body['model'], channel, ret_data.get(usage_field, {}), api_key_data, model_tag, cost_time)
        return ret_data


@api_router.post("/embeddings")
async def embeddings(req: EmbeddingsReq, request: Request):
    body = await request.json()
    if 'dimensions' in body:
        del body['dimensions']
    return await common_proxy(req.model, request, MetricUnit.TOKEN, ModelTag.EMBEDDING, usage_field='usage', body=body)


@api_router.post("/rerank")
async def embeddings(req: RerankerReq, request: Request):
    return await common_proxy(req.model, request, MetricUnit.TOKEN, ModelTag.RERANKER, usage_field='usage')


@api_router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def no_route(request: Request):
    raise GatewayException(f"不存在的接口[{request.url.path.removeprefix(settings.API_PREFIX)}]", HTTPStatus.NOT_FOUND)
