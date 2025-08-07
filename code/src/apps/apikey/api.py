# -*- coding: utf-8 -*-
from src.apps.depends import check_permission
from src.common.const.comm_const import UserPlat, EventAction
from fastapi import APIRouter, Depends, Request
from src.apps.apikey.rsp_schema import ApiKey, ApiKeyBase
from src.common.event_manage import event_manager, Event
from src.common.rsp_schema import PageResponse, BaseResponse, DataResponse
from src.common.utils.data import wrap_rsp
from src.apps.apikey.curd import apikey_curd
from src.apps.apikey.req_schema import ApikeyCreate, ApikeyUpdate
from src.common.dto import QueryDTO
from src.common.decorate.dynamic_filter import param_to_query
from src.common.const.comm_const import ResourceModule, ApiKeyStatus

api_router = APIRouter(prefix="/api/apikey", tags=["apikey 接口"], dependencies=[Depends(check_permission(UserPlat.QC_CONSOLE))])


@api_router.post("")
async def create_apikey(apikey_param: ApikeyCreate) -> DataResponse[ApiKeyBase]:
    return wrap_rsp(await apikey_curd.save_one(apikey_param, auto_gen_id=ResourceModule.SECRET_KEY, uuid_length=48))


@api_router.put("/{apikey_id}")
async def update_apikey(apikey_id: str, apikey_param: ApikeyUpdate) -> BaseResponse:
    return wrap_rsp(await apikey_curd.base_update(apikey_id, apikey_param, strict=True))


@api_router.delete("/{apikey_id}")
async def delete_apikey(apikey_id: str) -> BaseResponse:
    apikey_param = ApikeyUpdate(
        status=ApiKeyStatus.DELETE.value
    )
    await event_manager.emit(Event(EventAction.EVICT_CACHE, {'module': ResourceModule.SECRET_KEY, 'params': [apikey_id]}))
    return wrap_rsp(await apikey_curd.base_update(apikey_id, apikey_param, strict=True))


@param_to_query(
    keyword_fields=["name", 'id'],
    sort_fields=['create_time', 'update_time'],
    table_type=ApiKey,
    filter_delete=True,
    query_with_user=True,
)
async def list_page(request: Request):
    ...


@api_router.get("")
async def list_apikey(queryDTO: QueryDTO = Depends(list_page)) -> PageResponse[ApiKey]:
    page_data, page_total = await apikey_curd.list_page(queryDTO)
    return wrap_rsp(page_data, total=page_total)
