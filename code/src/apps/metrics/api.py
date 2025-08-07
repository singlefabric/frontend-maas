# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends

from src.apps.depends import check_permission
from src.common.rsp_schema import PageResponse
from src.apps.metrics.curd import metrics_curd
from src.apps.metrics.req_schema import ApiMetricsQuery, ApiModelTokenMetricsQuery, ApiUserTokenMetricsQuery
from src.common.const.comm_const import UserPlat
from src.common.utils.data import wrap_rsp

api_router = APIRouter(prefix="/api/metrics", tags=["metrics 统计相关接口"], dependencies=[Depends(check_permission(UserPlat.ALL))])
admin_router = APIRouter(prefix="/admin/metrics", tags=["metrics 统计相关接口"], dependencies=[Depends(check_permission(UserPlat.KS_CONSOLE))])

@api_router.get("/tokens")
async def tokens(query_params: ApiMetricsQuery = Depends()):
    return wrap_rsp(await metrics_curd.query_api_metrics(query_params))


@admin_router.get("/model")
async def models(query_params: ApiModelTokenMetricsQuery = Depends()) -> PageResponse[dict]:
    resutl, data_len = await metrics_curd.query_model_token_metrics(query_params)
    return wrap_rsp(resutl, data_len)

@admin_router.get("/user")
async def users(query_params: ApiUserTokenMetricsQuery = Depends()) -> PageResponse[dict]:
    resutl, data_len = await metrics_curd.query_user_token_metrics(query_params)
    return wrap_rsp(resutl, data_len)