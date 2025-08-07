# -*- coding: utf-8 -*-
from typing import Optional

from fastapi import APIRouter, Depends

from src.apps.depends import check_permission
from src.apps.product.curd import product_curd
from src.common.const.comm_const import UserPlat
from src.common.utils.data import wrap_rsp

api_router = APIRouter(prefix="/api/product", tags=["产品相关接口"], dependencies=[Depends(check_permission(UserPlat.QC_CONSOLE))])


@api_router.get("/fee-rate")
async def tokens(keyword: Optional[str]=None):
    return wrap_rsp(product_curd.get_model_fee_rate(keyword))