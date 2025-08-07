# -*- coding: utf-8 -*-
import pydash
from cachetools import TTLCache

from src.apps.channel.curd import channel_curd
from src.apps.model.req_schema import ModelQueryReq, ModelSaveReq
from src.apps.product.curd import product_curd
from src.apps.rate_limiter.curd import RateCURD, RateLimitCURD
from src.common.const.err_const import Err
from src.common.context import Context
from src.common.dto import User
from src.common.event_manage import EvictEventSubscriber, EventManager, Event
from src.common.asyncache import cached
from src.common.const.comm_const import TTLTime, ResourceModule, EventAction, ModelStatus
from src.apps.base_curd import BaseCURD
from src.apps.model.rsp_schema import *
from src.common.exceptions import MaaSBaseException
from src.common.utils.data import uuid
from src.setting import settings
from src.system.db.sync_db import session_manage
from src.system.integrations.aicp import aicp_client

TAG_MODULE = "imaas"


class ModelCURD(BaseCURD[Model]):

    @session_manage()
    async def get_by_model_name(self, model_name: str) -> list[Model]:
        """
        根据 name 查询所有数据
        :param model_name: 要查询的model_name
        :return: 匹配名称的所有数据的列表
        """
        # 使用 SQLAlchemy 的 filter 方法根据 model id 查询所有匹配的数据
        results = self.session.query(self.ModelT).filter(self.ModelT.name == model_name).all()
        return results

    @session_manage()
    async def list_for_square(self, req: ModelQueryReq):
        # 根据标签过滤的模型 ID
        tag_model_ids = []
        if req.model_tag:
            tag_ids = req.model_tag.split(',')
            res_list = model_tag_curd.get_resource_by_tag(tag_ids)
            tag_model_ids = pydash.pluck(res_list, 'resource_id')
            if not tag_model_ids:
                return [], 0

        # 根据渠道过滤的模型 ID
        channel_sql = "select model_id from channel_to_model where channel_id in (select id from channel where status = 'active')"
        channel_sql_ret = await self.query_by_sql(channel_sql)
        model_ids = pydash.pluck(channel_sql_ret[0], 'model_id')

        # 查询
        if tag_model_ids:
            model_ids = list(set(tag_model_ids) & set(model_ids))
        if not model_ids:
            return [], 0
        model_sql = f"select * from model where status = 'active' and id in :model_ids"
        params = {'model_ids': tuple(model_ids)}
        if req.key_words:
            model_sql += " and name like :key_words"
            params['key_words'] = f"%{req.key_words}%"
        model_sql += f" order by create_time desc"
        rows, total_count = await self.query_by_sql(model_sql, params, with_count=True, page=req)

        # 设置标签信息
        ids = pydash.pluck(rows, 'id')
        model_tags = model_tag_curd.get_tag_by_resource(ids)
        list_ = []
        for row in rows:
            model = ModelBase(**row).model_dump()
            model['model_tag'] = model_tags.get(row['id'], [])
            list_.append(model)
        return list_, total_count

    @session_manage()
    async def detail_for_square(self, model_id: str):
        user: User = Context.USER.get()
        data = await model_curd.get_by_id(model_id)
        if not data:
            raise MaaSBaseException(Err.OBJECT_NOT_EXISTS, fields=model_id)
        model = ModelBase(**data.model_dump()).model_dump()

        # 设置标签
        model_tags = model_tag_curd.get_tag_by_resource([model_id])
        model['model_tag'] = model_tags.get(model['id'], [])

        # 计费详情
        product_list = product_curd.get_prd(model['name'])
        model['model_price'] = pydash.map_(product_list, lambda x: pydash.pick(x.__dict__, ['token_type', 'price', 'unit']))

        # 限流信息
        model['user_level'] = await RateCURD().get_user_level(user.user_id)
        rate_limit = await RateLimitCURD().get_model_limit(model['id'])
        model['rate_limit'] = pydash.map_(rate_limit, lambda x: pydash.pick(x.model_dump(), ['level', 'rpm', 'tpm']))
        return model

    @session_manage()
    async def create(self, req: ModelSaveReq):
        models = await self.get_by_model_name(req.name)
        if models:
            raise MaaSBaseException(Err.VALIDATE_PARAMS, message="模型名称已存在")
        id_ = uuid(ResourceModule.MODEL)
        req.id = id_
        model_tag_curd.save_resource_tag(id_, req.tag_ids)
        await channel_curd.save_model_channels(id_, req.name, req.channels)
        model = Model(**req.dict(exclude={'channels', 'tag_ids'}))
        model.status = ModelStatus.INACTIVE.value
        await self.save_one(model)  # noqa
        await EventManager.emit(Event(EventAction.EVICT_CACHE, {'module': ResourceModule.CHANNEL, 'params': []}))

    @session_manage()
    async def update(self, model_id: str, req: ModelSaveReq):
        model = await self.get_by_id(model_id)
        if not model:
            raise MaaSBaseException(Err.VALIDATE_PARAMS, message="模型不存在")
        model_tag_curd.save_resource_tag(model_id, req.tag_ids)
        await channel_curd.save_model_channels(model_id, model.name, req.channels)
        model = Model(**req.dict(exclude={'channels', 'tag_ids', 'name', 'id'}))
        await self.base_update(model_id, model)
        await EventManager.emit(Event(EventAction.EVICT_CACHE, {'module': ResourceModule.CHANNEL, 'params': []}))

    @session_manage()
    async def change_status(self, model_id: str, status: ModelStatus):
        model = await self.get_by_id(model_id)
        if not model:
            raise MaaSBaseException(Err.VALIDATE_PARAMS, message="模型不存在")
        if (status == ModelStatus.ACTIVE and model.status != ModelStatus.INACTIVE.value) or \
                (status == ModelStatus.INACTIVE and model.status != ModelStatus.ACTIVE.value):
            raise MaaSBaseException(Err.VALIDATE_PARAMS, message="模型状态不正确")
        await self.base_update(model_id, {'status': status.value})
        await EventManager.emit(Event(EventAction.EVICT_CACHE, {'module': ResourceModule.CHANNEL, 'params': []}))

    @session_manage()
    async def get_model(self, model_id: str):
        data = await model_curd.get_by_id(model_id)
        if not data:
            raise MaaSBaseException(Err.OBJECT_NOT_EXISTS, fields=model_id)
        model = data.model_dump()

        # 设置标签
        model_tags = model_tag_curd.get_tag_by_resource([model_id])
        model['model_tag'] = model_tags.get(model['id'], [])

        # 设置渠道
        model['channels'] = await channel_curd.get_model_channels(model_id)
        return model

    @session_manage()
    async def delete(self, model_id: str):
        model = await self.get_by_id(model_id)
        if not model:
            raise MaaSBaseException(Err.VALIDATE_PARAMS, message="模型不存在")
        model_tag_curd.save_resource_tag(model_id, [])
        await channel_curd.save_model_channels(model_id, None, [])
        await self.base_delete(model_id)


class ModelTagCURD:

    @staticmethod
    def save_resource_tag(model_id: str, tag_ids: list[str]):
        data = {"module": TAG_MODULE, "resource_id": model_id, "tag_ids": tag_ids, "region": settings.QINGCLOUD_REGION}
        aicp_client.send_request(settings.PROXY_SERVER_HOST, '/global/product/api/tag/resource-tag',
                                 auth_type=aicp_client.AuthType.SIGNATURE, method="POST", json=data)

    @staticmethod
    def get_tag_by_resource(model_ids: list[str]) -> dict[str, list[dict]]:
        if not model_ids:
            return {}
        params = {"module": TAG_MODULE, "resource_ids": model_ids, "region": settings.QINGCLOUD_REGION}
        data = aicp_client.send_request(settings.PROXY_SERVER_HOST, '/global/product/api/tag/resource-tag',
                                        auth_type=aicp_client.AuthType.SIGNATURE, method="GET", params=params)
        return data['data']


    @staticmethod
    def get_resource_by_tag(tag_ids: list[str]) -> list[dict]:
        params = {"module": TAG_MODULE, "tag_ids": tag_ids, "region": settings.QINGCLOUD_REGION}
        data = aicp_client.send_request(settings.PROXY_SERVER_HOST, '/global/product/api/tag/tag-resource',
                                        auth_type=aicp_client.AuthType.SIGNATURE, method="GET", params=params)
        return data['list']


model_curd = ModelCURD()
model_tag_curd = ModelTagCURD()


class ModelParamCURD(BaseCURD[ModelParam]):

    @session_manage()
    async def get_by_model_tag(self, model_tag_id: str) -> list[ModelParam]:
        """
        根据 name 查询所有数据
        :param model_tag_id: 要查询的model_tag_id
        :return: 匹配名称的所有数据的列表
        """
        # 使用 SQLAlchemy 的 filter 方法根据 model id 查询所有匹配的数据
        results = (self.session.query(self.ModelT).filter(self.ModelT.tag_id == model_tag_id).
                   filter(self.ModelT.model_id.is_(None)).all())
        return results

    @session_manage()
    async def get_by_model_id_and_tag_id(self, model_id: str, model_tag_id: str) -> list[ModelParam]:
        """
        根据 name 查询所有数据
        :param model_id: 要查询的model_id
        :param model_tag_id: 要查询的model_tag_id
        :return: 匹配名称的所有数据的列表
        """
        # 使用 SQLAlchemy 的 filter 方法根据 model id 查询所有匹配的数据
        results = (self.session.query(self.ModelT).filter(self.ModelT.model_id == model_id).
                   filter(self.ModelT.tag_id == model_tag_id).all())
        return results

    @cached(cache=TTLCache(maxsize=1024, ttl=TTLTime.MODEL_PARAM.value),
            evict=EvictEventSubscriber(module=ResourceModule.PARAM))
    async def get_by_model_name(self, model_name: str, tag_id: str="txt2txt") -> dict[str, ModelParam]:
        """
        根据 name 查询所有数据
        :param model_name: 要查询的model_name
        :param tag_id: 要查询的tag_id
        :return: 匹配名称的所有数据的列表
        """
        # 使用 SQLAlchemy 的 filter 方法根据 model id 查询所有匹配的数据
        model_param = []
        model_list = await model_curd.get_by_model_name(model_name)
        if model_list is None or len(model_list) < 1:
            return {}
        for model in model_list:
            model_param_list = await model_param_curd.get_by_model_id_and_tag_id(model.id, tag_id)
            if model_param_list is not None and len(model_param_list) > 0:
                model_param.extend(model_param_list)
            else:
                model_param_list = await model_param_curd.get_by_model_tag(tag_id)
                if model_param_list is not None and len(model_param_list) > 0:
                    model_param.extend(model_param_list)
        return {item.key: item  for item in model_param}

model_param_curd = ModelParamCURD()
