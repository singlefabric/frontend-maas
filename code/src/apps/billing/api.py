# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends

from src.apps.billing.curd import billing_curd
from src.apps.billing.req_schema import BillingEvent
from src.apps.depends import check_permission
from src.common.const.comm_const import UserPlat
from src.common.loggers import logger
from src.common.utils.data import wrap_rsp

api_router = APIRouter(prefix="/api/billing", tags=["计费相关接口"], dependencies=[Depends(check_permission(UserPlat.QC_CONSOLE))])


@api_router.post("/event")
async def event_handler(event: BillingEvent):
    logger.info(f'[事件] 收到[{event}]')
    if event.type in ['user.balance.recharge', 'user.balance.insufficient'] and event.data:
        if user_id := event.data.get('user_id'):
            billing_curd.evict_balance_cache(user_id)
    return wrap_rsp()
