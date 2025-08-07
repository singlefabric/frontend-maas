# -*- coding: utf-8 -*-

from typing import Optional

from fastapi import Request

from src.common.const.comm_const import UserPlat
from src.common.const.err_const import Err
from src.common.context import Context
from src.common.dto import ValidOwner, User
from src.common.exceptions import MaaSBaseException
from src.apps.base_curd import base_curd


def check_permission(plat: UserPlat = None, validOwner: Optional[ValidOwner] = None, role: str = None):
    """
    权限拦截器
    :param plat: 平台（云平台或者ks平台）
    :param validOwner: 校验资源所有者
    :param role: 校验调用方角色（预留）
    :return:
    """

    async def validate_permission(request: Request):
        user: User = Context.USER.get()

        # 平台权限不足
        if plat and user.plat not in plat.value.split(","):
            raise MaaSBaseException(Err.AUTH_PLAT_ERR, plat=plat.value)

        # 角色权限不足
        if role and user.role != role:
            raise MaaSBaseException(Err.AUTH_ROLE_ERR)

        # 用户权限不足
        if validOwner:
            id_field = validOwner.biz_id_field
            id_val = request.path_params.get(id_field) or request.query_params.get(id_field)
            if not id_val:
                data = await request.json() or {}
                id_val = data.get(id_field)
            if not id_val or not user.user_id:
                raise MaaSBaseException(Err.REQUIRE_PARAMS, fields=f"{id_field} or user_id")
            sql_str = f"select count(1) from {validOwner.tb_name} where {validOwner.tb_id_field} = :id_val and {validOwner.tb_user_field} = :user_id"
            data_ret = await base_curd.query_by_sql(sql_str, {"id_val": id_val, "user_id": user.user_id})
            if not data_ret or data_ret[0][0].get('count') == 0:
                raise MaaSBaseException(Err.AUTH_OWNER_ERR)
        return True

    return validate_permission
