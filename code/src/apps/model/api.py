# -*- coding: utf-8 -*-
import pydash
from fastapi import APIRouter, Depends, Request, Body

from src.apps.depends import check_permission
from src.apps.model.rsp_schema import Model, ModelParamInfo, ModelBase
from src.common.const.comm_const import UserPlat, ModelStatus
from src.common.rsp_schema import PageResponse, DataResponse, BaseResponse
from src.common.utils.data import wrap_rsp
from .curd import model_curd, model_param_curd, model_tag_curd
from .req_schema import ModelQueryReq, ModelSaveReq
from ...common.decorate.dynamic_filter import param_to_query
from ...common.dto import QueryDTO

api_router = APIRouter(prefix="/api/model", tags=["model 接口"], dependencies=[Depends(check_permission(UserPlat.ALL))])
admin_router = APIRouter(prefix="/admin/model", tags=["model 接口"], dependencies=[Depends(check_permission(UserPlat.KS_CONSOLE))])


@api_router.get("")
async def list_model(req: ModelQueryReq=Depends()) -> PageResponse[ModelBase]:
    """
    用户端广场
    """
    row, total_count = await model_curd.list_for_square(req)
    return wrap_rsp(row, total=total_count)


@param_to_query(
    keyword_fields=["name", 'id'],
    sort_fields=['create_time', 'update_time'],
    table_type=Model,
    filter_delete=True
)
async def list_page(request: Request):
    ...


@admin_router.get("")
async def list_model(query_dto: QueryDTO = Depends(list_page)) -> PageResponse[dict]:
    page_data, page_total = await model_curd.get_by_query_dto(query_dto, with_count=True)
    # 设置标签信息
    ids = pydash.pluck(page_data, 'id')
    model_tags = model_tag_curd.get_tag_by_resource(ids)
    list_ = pydash.map_(page_data, lambda x: x.dict())
    for model in list_:
        model['model_tag'] = model_tags.get(model['id'], [])
    return wrap_rsp(list_, total=page_total)


@admin_router.get("/{model_id}")
async def get_model(model_id: str) -> DataResponse[dict]:
    model = await model_curd.get_model(model_id)
    return wrap_rsp(model)


@admin_router.post("")
async def create(req: ModelSaveReq) -> BaseResponse:
    await model_curd.create(req)
    return wrap_rsp()


@admin_router.put("/change-status")
async def change_status(model_id: str=Body(), status: ModelStatus=Body()) -> BaseResponse:
    await model_curd.change_status(model_id, status)
    return wrap_rsp()


@admin_router.put("/{model_id}")
async def update(model_id: str, req: ModelSaveReq) -> BaseResponse:
    await model_curd.update(model_id, req)
    return wrap_rsp()


@admin_router.delete("/{model_id}")
async def delete(model_id: str) -> BaseResponse:
    await model_curd.delete(model_id)
    return wrap_rsp()


@api_router.get("/param")
async def list_model_param(request: Request) -> PageResponse[ModelParamInfo]:
    query_params = dict(request.query_params)
    model_tag_id = query_params.get("model_tag")
    mode_id = query_params.get("model_id")
    model_param_list = await model_param_curd.get_by_model_id_and_tag_id(mode_id, model_tag_id)
    if model_param_list is not None and len(model_param_list) > 0:
        return wrap_rsp(model_param_list, total=len(model_param_list))
    model_param_list = await model_param_curd.get_by_model_tag(model_tag_id)
    return wrap_rsp(model_param_list, total=len(model_param_list))


@api_router.get("/{model_id}")
async def get_model(model_id: str) -> DataResponse[dict]:
    model = await model_curd.detail_for_square(model_id)
    return wrap_rsp(model)
