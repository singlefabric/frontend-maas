# -*- coding: utf-8 -*-
from typing import List

from fastapi import APIRouter, Depends, Query
from starlette.requests import Request

from src.apps.depends import check_permission
from src.apps.rate_limiter.curd import LevelCURD, RateCURD, RateLimitCURD, UserLevelCURD
from src.apps.rate_limiter.schema import LevelBase, RateLimit, RateLimitBase, RateLimitDeleteParam, UserLevel, UserLevelBase, \
    UserModelRateLimit
from src.common.const.comm_const import UserPlat
from src.common.context import Context
from src.common.decorate.dynamic_filter import param_to_query
from src.common.dto import QueryDTO, User
from src.common.rsp_schema import PageResponse
from src.common.utils.data import wrap_rsp
from src.system.interface import qingcloud_user

api_router = APIRouter(prefix="/api/rate", tags=["速率限制相关接口"], dependencies=[Depends(check_permission(UserPlat.ALL))])

admin_router = APIRouter(prefix="/admin/api/rate", tags=["管理端速率限制相关接口"],
                         dependencies=[Depends(check_permission(UserPlat.KS_CONSOLE))])
"""
用户的
1. 根据模型名称查询限制

管理端
1. 查询用户level列表
2. 查看用户 rate 限制信息
3. 查询 level rate 限制(level/model name)
4. 新增 level + model name 速率配置


"""

"""
init sql : 


"""


@api_router.get(
    "/models/limit",
    description="获取当前用户的model的限流信息, console端调用",
)
async def get_user_limits(
        model_name: str
):
    """
    获取用户限流信息
    :return:
    """
    user: User = Context.USER.get()
    user_level = await RateCURD().get_user_level(user.user_id)
    limit: UserModelRateLimit = await RateCURD().get_level_model_limit(user_level, model_name)
    return wrap_rsp(limit)


@param_to_query(
    is_in=["level"],
    eq=["model_id"],
    keyword_fields=["model_name"],
    sort_fields=['rpm', 'tpm', 'level', 'model_name', 'created_at', 'updated_at'],
    table_type=RateLimit
)
async def list_rate_limit_page(request: Request):
    ...


@admin_router.get(
    "/models",
    description="kse页面查询所有模型的限流信息"
)
async def get_models_limits(
        query_dto: QueryDTO = Depends(list_rate_limit_page)
) -> PageResponse[RateLimit]:
    """
    查询所有模型的限流信息
    """
    page_data, page_total = await RateLimitCURD().get_by_query_dto(query_dto, with_count=True)
    return wrap_rsp(page_data, total=page_total)


@admin_router.put(
    "/models",
    description="设置模型的限流信息, 根据 model_id + level 进行更新. 如果不存在则新增"
)
async def put_model_limit(
        rate_limit: RateLimitBase
):
    """
    设置模型的限流信息
    """
    item = await RateLimitCURD().put_item(rate_limit)
    return wrap_rsp(item)

@admin_router.delete(
    "/models",
    description="删除模型的限流信息, 根据 model_id + level 进行删除"
)
async def delete_model_limit(
        rate_limit: RateLimitDeleteParam
):
    """
    设置模型的限流信息
    """
    item = await RateLimitCURD().delete_item(rate_limit)
    return wrap_rsp(item)


@param_to_query(
    is_in=["level", "upgrade_policy"],
    keyword_fields=["user_id"],
    sort_fields=['level', 'created_at', 'updated_at', 'upgrade_policy'],
    table_type=UserLevel
)
async def list_user_level_page(request: Request):
    ...


@admin_router.get(
    "/users",
    description="查询所有用户的level"
)
async def get_users(
        query: QueryDTO = Depends(list_user_level_page)
) -> PageResponse[UserLevel]:
    user_levels, count = await UserLevelCURD().get_by_query_dto(query, with_count=True)
    results = []
    for item in user_levels:
        result = item.dict()
        result['user_name'] = qingcloud_user.get_user_by_id(item.user_id).user_name
        results.append(result)
    return wrap_rsp(results, total=count)


@admin_router.get(
    "/levels",
    description="查询所有的level"
)
async def get_levels(
        level: List[int] = Query([], description="levels you search")
) -> PageResponse[UserLevel]:
    result = await LevelCURD().get_by_filter([{"column_name": "level", "operator": "is_in", "value": level}])
    return wrap_rsp(result)

@admin_router.put(
    "/levels",
    description="修改level"
)
async def get_levels(
        level: LevelBase
):
    result = await LevelCURD().put_item(level)
    return wrap_rsp(result)

@admin_router.delete(
    "/levels",
    description="删除level"
)
async def delete_levels(
    level: int
):
    result = await LevelCURD().delete_item(level)
    return wrap_rsp(result)

@admin_router.put(
    "/users",
    description="设置用户等级,以及升级策略"
)
async def set_user_level(
        user_level: UserLevelBase
):
    result = await UserLevelCURD().put_item(user_level)
    return wrap_rsp(result)
