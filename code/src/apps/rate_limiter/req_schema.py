# -*- coding: utf-8 -*-
import time
from typing import Optional

from fastapi import Query
from pydantic import BaseModel

from src.common.const.comm_const import DEF_METRICS_POINTS, MetricsAggrType
from src.common.const.err_const import Err
from src.common.dto import QueryDTO
from src.common.exceptions import MaaSBaseException
from src.common.utils.data import transform_to_list
from src.setting import settings


class UsersLevelQuery:

    def __init__(
            self,
            user_id: Optional[str] = Query(None, description="用户ID"),
            level: Optional[int] = Query(None, description="用户等级"),
            order_by: Optional[str] = Query(None, description="排序字段"),
            desc: Optional[bool] = Query(False, description="是否倒序"),
    ):
        self.user_id = user_id
        self.level = level
        self.order_by = order_by
        self.desc = desc


class RateLimitsQuery:

    def __init__(
            self,
            model_id: Optional[int] = Query(None, description="模型ID"),
            model_name: Optional[str] = Query(None, description="模型名称"),
            level: Optional[int] = Query(None, description="用户等级"),
            order_by: Optional[str] = Query(None, description="排序字段"),
            desc: Optional[bool] = Query(False, description="是否倒序"),
    ):
        self.model_id = model_id
        self.model_name = model_name
        self.level = level
        self.order_by = order_by
        self.desc = desc

