# -*- coding: utf-8 -*-

from fastapi import APIRouter, Depends

from src.apps.depends import check_permission
from src.common.const.comm_const import UserPlat
from src.common.event_manage import event_manager, Event
from src.common.utils.data import wrap_rsp

admin_router = APIRouter(prefix="/admin/system", tags=["服务相关接口"], dependencies=[Depends(check_permission(UserPlat.KS_CONSOLE))])


@admin_router.post("/emit-event")
async def emit_event(event: Event):
    await event_manager.emit(event)
    return wrap_rsp()