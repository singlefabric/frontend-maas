# -*- coding: utf-8 -*-
import json
import time
from typing import Union
import pydash
from cachetools import TTLCache
from httpx import AsyncClient, TimeoutException, RemoteProtocolError, ConnectError, RequestError

from src.apps.base_curd import BaseCURD
from src.apps.channel.req_schema import ChannelReq
from src.apps.channel.rsp_schema import *
from src.apps.metrics.curd import metrics_curd
from src.common.asyncache import cached
from src.common.const.comm_const import TTLTime, ResourceModule, API_KEY_PREFIX, EventAction
from src.common.dto import QueryDTO, ModelApi
from src.common.event_manage import EvictEventSubscriber, EventManager, Event
from src.common.loggers import logger
from src.common.utils.data import uuid
from src.setting import settings
from src.system.db.sync_db import session_manage
from src.common.decorate.dynamic_filter import build_query_express
from src.common.exceptions import MaaSBaseException
from sqlalchemy import and_, or_, text
from src.common.const.err_const import Err

# 健康检查变更连续次数[渠道, 连续次数]
HEALTH_TIMES: dict[str, int] = {}

MODEL_API = {
    "txt2txt": ModelApi("/chat/completions", {
        "stream": True,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "你好"}
        ]
    }),
    "rerank": ModelApi("/rerank", {
        "query": "What is the capital of France?",
        "documents": [
            "Paris is the capital of France.",
            "London is the capital of England."],
      "top_n": "2"
    }),
    "embedding": ModelApi("/embeddings", {
        "input": ["你好"]
    }),
}


class ChannelCURD(BaseCURD[Channel]):

    @session_manage()
    async def list_page(self, query_dto: QueryDTO) -> (list, int):
        ret_list, total_count = await self.get_by_query_dto(query_dto, with_count=True)
        return ret_list, total_count

    @session_manage()
    async def update(self, data_id: Union[int, str], data: Union[dict, BaseModel], strict: bool = False) -> bool:
        rowcount = await self.base_update(data_id, data, strict)
        await EventManager.emit(Event(EventAction.EVICT_CACHE, {'module': ResourceModule.CHANNEL, 'params': []}))
        return rowcount

    @cached(cache=TTLCache(maxsize=1024, ttl=TTLTime.MODEL_CHANNEL.value), evict=EvictEventSubscriber(module=ResourceModule.CHANNEL))
    async def query_model_channel_and_cache(self):
        """
        查询模型及渠道数据并缓存
        """
        logger.info('加载模型渠道数据')
        sql = ("select t3.name, t1.id channel_id, t1.inference_secret_key, t1.inference_service, t1.health_status, "
               "t1.model_redirection from channel t1 left join channel_to_model t2 on t1.id = t2.channel_id left join "
               "model t3 on t2.model_id = t3.id where t1.status = 'active' and t3.status = 'active'")
        ret = await self.query_by_sql(sql)
        for channel in ret[0]:
            if channel['model_redirection']:
                try:
                    channel['model_redirection'] = json.loads(channel['model_redirection'])
                except Exception:  # noqa
                    channel['model_redirection'] = None
                    logger.warning(f'解析渠道{channel["channel_id"]}的 model_redirection 失败: {channel["model_redirection"]}')
        return pydash.group_by(ret[0], 'name')

    async def health_check(self):
        logger.info('渠道健康检查')
        sql = ("select t3.name, t1.id channel_id, t1.inference_secret_key, t1.inference_service, t1.health_status "
               "from channel t1 left join channel_to_model t2 on t1.id = t2.channel_id left join model t3 on "
               "t2.model_id = t3.id where t1.status = 'active' and t3.status = 'active'")
        ret = await self.query_by_sql(sql)
        for channel in ret[0]:
            model = channel['name']
            response = None
            start_time = time.time()
            cid = channel['channel_id']
            base_url = channel['inference_service'] + '/' if not channel['inference_service'].endswith('/') else channel['inference_service']
            async with AsyncClient() as client:
                try:
                    response = await client.request('GET', base_url + 'v1/models', headers={'Authorization': f'{API_KEY_PREFIX}{channel["inference_secret_key"]}'}, timeout=5)
                    if response.status_code not in [200, 404] or not len(response.content):
                        health = 0
                    else:
                        health = 1
                except Exception as e:
                    if isinstance(e, TimeoutException):
                        logger.warning(f'[健康检查] 渠道[{cid}][{base_url}]请求超时: {e}')
                    elif isinstance(e, RemoteProtocolError) or isinstance(e, ConnectError):
                        logger.warning(f'[健康检查] 渠道[{cid}][{base_url}]无法连接: {e}')
                    else:
                        logger.exception(f'[健康检查] 渠道[{cid}][{base_url}][start: {start_time}]')
                    health = 0

            metrics_curd.submit_channel_health(cid, model, health)
            if channel['health_status'] != health:

                # 达到阈值之后触发状态变更
                continue_times = pydash.get(HEALTH_TIMES, cid, default=0)
                HEALTH_TIMES[cid] = continue_times + 1

                if HEALTH_TIMES[cid] >= settings.HEALTH_CHANGE_THRESHOLD:
                    logger.error(f'[健康检查] 模型[{model}]渠道[{cid}]变更健康状态[{health}]，健康检查状态码[{response.status_code if response else ""}][start: {start_time:.2f}s]')
                    await self.base_update(cid, {'health_status': health})
                    await EventManager.emit(Event(EventAction.EVICT_CACHE, {'module': ResourceModule.CHANNEL, 'params': []}))
                    HEALTH_TIMES[cid] = 0
            else:
                HEALTH_TIMES[cid] = 0

    @session_manage()
    async def save_model_channels(self, model_id: str, model_name: str, channels: list[ChannelReq]):
        del_ch_sql = "delete from channel where id in (select channel_id from channel_to_model where model_id = :model_id)"
        self.session.execute(text(del_ch_sql), {"model_id": model_id})

        del_ch_model_sql = "delete from channel_to_model where model_id = :model_id"
        self.session.execute(text(del_ch_model_sql), {"model_id": model_id})

        for ch in channels:
            if not ch.id:
                ch.id = uuid(ResourceModule.CHANNEL)
            channel = pydash.pick(ch.dict(), ["id", "name", "inference_secret_key", "inference_service"])
            channel.update({
                "channel_type_id": "",
                "model_redirection": json.dumps({model_name: ch.model_name}) if ch.model_name else '{}',
                "status": "active"
            })
            await self.save_one(Channel(**channel))  # noqa
            await channel_to_model_curd.save_one(ChannelToModel(**{"channel_id": ch.id, "model_id": model_id}))  # noqa

    @session_manage()
    async def get_model_channels(self, model_id: str) -> dict:
        sql = "select * from channel where id in (select channel_id from channel_to_model where model_id = :model_id)"
        ret = await self.query_by_sql(sql, {"model_id": model_id})
        return ret[0]

    @session_manage()
    async def test_connect(self, tag_ids: list[str], model_name: str, inference_service: str, inference_secret_key: str):
        model_api = None
        for tag_id in tag_ids:
            if tag_id in MODEL_API:
                model_api = MODEL_API[tag_id]
                break
        if not model_api:
            raise MaaSBaseException(Err.CHANNEL_CONNECT_FAILED, message="模型类型暂不支持")
        if inference_service.endswith('#'):
            url = inference_service[:-1]
        elif inference_service.endswith('/'):
            url = inference_service[:-1] + model_api.url_path
        else:
            url = inference_service + '/v1' + model_api.url_path
        body_data = model_api.req_body
        body_data['model'] = model_name
        logger.debug(f'request [{url}][{body_data}]')
        headers = {'Authorization': API_KEY_PREFIX + inference_secret_key}
        try:
            async with AsyncClient() as client:
                response = await client.post(url, headers=headers, json=body_data)
                if response.status_code != 200:
                    raise MaaSBaseException(Err.CHANNEL_CONNECT_FAILED, message="response是%s" % (response.status_code))
                else:
                    is_streaming = (
                            response.headers.get('Content-Type', '').startswith('text/event-stream') or
                            response.headers.get('Transfer-Encoding', '').lower() == 'chunked')
                    if not is_streaming:
                        response_data = response.json()
                        if 'code' in response_data and response_data['code'] != 200:
                            raise MaaSBaseException(Err.CHANNEL_CONNECT_FAILED, message="暂不支持该模型")
        except RequestError as e:
            raise MaaSBaseException(Err.CHANNEL_CONNECT_FAILED, message=e)


class ChannelToModelCURD(BaseCURD[ChannelToModel]):

    @session_manage()
    async def get_id_by_filter(self, filter_conditions: list[dict[str, any]]) -> list[int]:
        """
        根据过滤条件查询数据并返回 ID 列表
        :param filter_conditions: 过滤条件列表，每个元素为字典 {"column_name": column_name, "operator": operator, "value": value}
        :return: 查询到的 ID 列表
        """
        query = self.session.query(self.ModelT)

        # 使用列表推导式构建过滤条件
        query_filters = [
            build_query_express(condition["operator"], self.ModelT, condition["column_name"], condition["value"])
            for condition in filter_conditions
        ]

        # 执行查询并提取 ID
        ids = query.filter(and_(*query_filters)).with_entities(self.ModelT.model_id).all()

        # 返回 ID 列表
        return [id_ for (id_,) in ids]  # 解构元组，提取 ID

    @session_manage()
    async def delete_data(self, conditions: list[tuple[str, str]], strict: bool = False) -> bool:
        """
        根据 channel_id 和 model_id 的组合条件删除多个数据
        :param conditions: (channel_id, model_id) 的元组列表
        :param strict: 是否校验更新数量，如果数量为 0 抛出异常
        :return: 删除数量是否大于 0
        """

        # 构造 OR 条件
        filter_conditions = or_(
            *(and_(
                getattr(self.ModelT, 'channel_id') == channel_id,
                getattr(self.ModelT, 'model_id') == model_id
            ) for channel_id, model_id in conditions)
        )
        # 执行删除操作
        deleted_count = self.session.query(self.ModelT).filter(filter_conditions).delete()
        # 检查删除数量
        if deleted_count == 0 and strict:
            raise MaaSBaseException(Err.OBJECT_NOT_EXISTS, fields={'conditions': conditions})
        return deleted_count > 0

    @session_manage()
    async def get_by_channel_id(self, channel_id: str) -> list[ChannelToModel]:
        """
        根据 name 查询所有数据
        :param channel_id: 要查询的channel id
        :return: 匹配名称的所有数据的列表
        """
        # 使用 SQLAlchemy 的 filter 方法根据 channel id 查询所有匹配的数据
        results = self.session.query(self.ModelT).filter(self.ModelT.channel_id == channel_id).all()
        return results


class ChannelTypeCURD(BaseCURD[ChannelType]):
    @session_manage()
    async def list_page(self, query_dto: QueryDTO) -> (list, int):
        ret_list, total_count = await self.get_by_query_dto(query_dto, with_count=True)
        return ret_list, total_count


channel_curd = ChannelCURD()
channel_to_model_curd = ChannelToModelCURD()
channel_type_curd = ChannelTypeCURD()

