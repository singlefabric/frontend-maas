# -*- coding: utf-8 -*-
import json

import pydash
from fastapi import APIRouter, Depends, Request, Query

from src.apps.channel.curd import channel_curd, channel_to_model_curd, channel_type_curd
from src.apps.channel.req_schema import ChannelCreate, ChannelUpdate, ChannelUpdateBase
from src.apps.channel.rsp_schema import Channel, ChannelBase, ChannelToModel, ChannelType, ChannelInfo, TypeInfo
from src.apps.depends import check_permission
from src.apps.model.curd import model_curd, model_tag_curd
from src.apps.model.rsp_schema import Model
from src.common.const.comm_const import ChannelStatus, ModelStatus
from src.common.const.comm_const import ResourceModule, EventAction
from src.common.const.comm_const import UserPlat
from src.common.const.err_const import Err
from src.common.decorate.dynamic_filter import param_to_query
from src.common.dto import QueryDTO
from src.common.event_manage import EventManager, Event
from src.common.exceptions import MaaSBaseException
from src.common.loggers import logger
from src.common.rsp_schema import PageResponse, BaseResponse, DataResponse
from src.common.utils.data import wrap_rsp

admin_router = APIRouter(prefix="/admin/channel", tags=["channel 接口"], dependencies=[Depends(check_permission(UserPlat.KS_CONSOLE))])
api_channel_type_api_router = APIRouter(prefix="/api/channel_type", tags=["channel type 接口"], dependencies=[Depends(check_permission(UserPlat.QC_CONSOLE))])
admin_channel_type_api_router = APIRouter(prefix="/admin/channel_type", tags=["channel type 接口"], dependencies=[Depends(check_permission(UserPlat.KS_CONSOLE))])


@admin_router.post("")
async def create_channel(channel_param: ChannelCreate) -> DataResponse[ChannelBase]:
    # 更新channel表
    channel_info: Channel = await channel_curd.save_one(channel_param, auto_gen_id=ResourceModule.CHANNEL)
    if channel_param.model_id is None or len(channel_param.model_id) == 0:
        logger.debug("model is null when create channel")
    else:
        # 更新channel_to_model表
        for modelId in channel_param.model_id:
            channel_to_model = ChannelToModel(
                channel_id=channel_info.id,
                model_id=modelId
            )
            await channel_to_model_curd.save_one(channel_to_model)
    await EventManager.emit(Event(EventAction.EVICT_CACHE, {'module': ResourceModule.CHANNEL, 'params': []}))
    return wrap_rsp(channel_info)


@admin_router.put("/{channel_id}")
async def update_channel(channel_id: str, channel_param: ChannelUpdate) -> BaseResponse:
    filter_conditions = [
        {"column_name": "channel_id", "operator": "eq", "value": channel_id},
    ]
    # 根据channel id查询关联的model id
    model_ids = await channel_to_model_curd.get_id_by_filter(filter_conditions)
    # 如果之前存在，但是更新之后的model里面没有则从表中删除，如果之前不存在，更新之后有则新增
    if channel_param.model_id is not None:
        insert_model_ids, delete_model_ids = find_unique_elements(channel_param.model_id, model_ids)
        # 删除更新之后不存在的model和channel的对应关系
        for i in delete_model_ids:
            delete_num = await channel_to_model_curd.delete_data([(channel_id, i)], strict=True)
            if delete_num == 0:
                logger.debug("Delete num is 0 when delete model id(%s) in channel_to_model" % (i))
        for i in insert_model_ids:
            channel_to_model = ChannelToModel(
                channel_id=channel_id,
                model_id=i
            )
            await channel_to_model_curd.save_one(channel_to_model)
    # 修改channel表
    channel_update_base = ChannelUpdateBase(
        channel_type_id=channel_param.channel_type_id,
        name=channel_param.name,
        model_redirection=channel_param.model_redirection,
        inference_secret_key=channel_param.inference_secret_key,
        inference_service=channel_param.inference_service,
        status=channel_param.status
    )
    if channel_param.model_redirection is None:
        channel_update_base.model_redirection = '{}'
    return wrap_rsp(await channel_curd.update(channel_id, channel_update_base, strict=True))


@admin_router.delete("/{channel_id}")
async def delete_channel(channel_id: str) -> BaseResponse:
    channel_update = ChannelUpdate(
        status=ChannelStatus.DELETE.value
    )
    return wrap_rsp(await channel_curd.update(channel_id, channel_update, strict=True))


@param_to_query(
    keyword_fields=["name", 'id'],
    sort_fields=['create_time', 'update_time'],
    table_type=Channel,
    filter_delete=True,
    without_page=True
)
async def list_page(request: Request):
    ...


@admin_router.get("")
async def list_channel(request: Request, queryDTO: QueryDTO = Depends(list_page)) -> PageResponse[ChannelType]:
    page_data, page_total = await channel_curd.list_page(queryDTO)
    query_params = dict(request.query_params)
    query_status = query_params.get("status", None)
    query_channel_type = query_params.get("channel_type", None)
    page = int(query_params.get("page", 1)) - 1
    page_size = int(query_params.get("size", 20))
    start_page = int(page * page_size)

    channel_info_list = []
    for channelInfoItem in page_data:
        if not (query_status is None or channelInfoItem.status == query_status):
            continue
        # 查询channel type信息
        channel_type: ChannelType = await channel_type_curd.get_by_id(channelInfoItem.channel_type_id)
        channel_type_info = TypeInfo(
            id=channel_type.id,
            name=channel_type.name
        )
        if not(query_channel_type is None or channel_type.id == query_channel_type):
            continue
        channel_to_model_list = await channel_to_model_curd.get_by_channel_id(channelInfoItem.id)
        model_info_list = []
        if channel_to_model_list is not None:
            for channelToModelItem in channel_to_model_list:
                # 查询model信息
                model: Model = await model_curd.get_by_id(channelToModelItem.model_id)
                model_info = TypeInfo(
                    id=model.id,
                    name=model.name
                )
                if model.status == ModelStatus.DELETE.value:
                    continue
                model_info_list.append(model_info)
        channel_info = ChannelInfo(
            id=channelInfoItem.id,
            name=channelInfoItem.name,
            model_redirection=channelInfoItem.model_redirection,
            inference_secret_key=channelInfoItem.inference_secret_key,
            inference_service=channelInfoItem.inference_service,
            create_time=channelInfoItem.create_time,
            update_time=channelInfoItem.update_time,
            status=channelInfoItem.status,
            channel_type=channel_type_info,
            model=model_info_list
        )
        channel_info_list.append(channel_info)
    return wrap_rsp(channel_info_list[start_page:start_page + page_size], total=len(channel_info_list))


@admin_router.get("/test-connect")
async def test_connect(tag_ids: list[str]=Query(), model_name: str=Query(), inference_service: str=Query(),
                       inference_secret_key: str=Query()) -> BaseResponse:
    await channel_curd.test_connect(tag_ids, model_name, inference_service, inference_secret_key)
    return wrap_rsp(True)


@admin_router.get("/test/{channel_id}")
async def channel_connect(channel_id: str, model_id: str) -> BaseResponse:
    channel_info: Channel = await channel_curd.get_by_id(channel_id)
    model_info: Model = await model_curd.get_by_id(model_id)
    model_to_tag = model_tag_curd.get_tag_by_resource([model_info.id]).get(model_info.id, [])
    if not model_to_tag:
        raise MaaSBaseException(Err.CHANNEL_CONNECT_FAILED, message="资源未关联标签")
    tag_ids = pydash.pluck(model_to_tag, 'id')
    if channel_info.model_redirection:
        model_redirection_json = json.loads(channel_info.model_redirection)
    else:
        model_redirection_json = {}
    model_name = model_redirection_json.get(model_info.name) if model_redirection_json.get(model_info.name) else model_info.name
    await channel_curd.test_connect(tag_ids, model_name, channel_info.inference_service, channel_info.inference_secret_key)
    return wrap_rsp(True)


@param_to_query(
    keyword_fields=["name", 'id'],
    table_type=ChannelType
)
async def list_channel_page(request: Request):
    ...


@admin_channel_type_api_router.get("")
async def list_channel_type(queryDTO: QueryDTO = Depends(list_channel_page)) -> PageResponse[ChannelInfo]:
    page_data, page_total = await channel_type_curd.list_page(queryDTO)
    return wrap_rsp(page_data, total=page_total)

@api_channel_type_api_router.get("")
async def list_channel_type(queryDTO: QueryDTO = Depends(list_channel_page)) -> PageResponse[ChannelInfo]:
    page_data, page_total = await channel_type_curd.list_page(queryDTO)
    return wrap_rsp(page_data, total=page_total)


def find_unique_elements(list1, list2):
    if not list1 and not list2:
        return [], []  # 两个都为空
    elif not list1:
        return [], list(set(list2))  # list1 为空，返回 list2 的唯一元素
    elif not list2:
        return list(set(list1)), []  # list2 为空，返回 list1 的唯一元素

    # 将两个列表转换为集合
    set1 = set(list1)
    set2 = set(list2)

    # 找到两个集合的差集
    unique_to_list1 = set1 - set2  # 仅在 list1 中
    unique_to_list2 = set2 - set1  # 仅在 list2 中

    # 返回结果
    return list(unique_to_list1), list(unique_to_list2)
