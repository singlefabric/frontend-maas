# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import BooleanClauseList, UnaryExpression

from src.common.const.comm_const import UserPlat, TokenType, MetricUnit
from src.common.req_schema import BasePageReq


class User:

    def __init__(self, user_id: str, user_name: str, role: str, plat: Optional[UserPlat] = None) -> None:
        self.user_id = user_id
        self.user_name = user_name
        self.role = role
        self.plat = plat


EMPTY_USER = User("", "", "")
KS_ADMIN_USER = User("admin", "admin", "", UserPlat.KS_CONSOLE)


class QueryDTO:

    express: BooleanClauseList
    page: BasePageReq
    sort_expr: UnaryExpression

    def __init__(self, express: BooleanClauseList, page, offset, size, sort_expr) -> None:
        self.express = express
        self.page = BasePageReq(page=page, offset=offset, size=size)
        self.sort_expr = sort_expr


@dataclass
class AccessKey:
    access_key_id: str
    secret_access_key: str


class ValidOwner:
    tb_name: str
    tb_id_field: str
    tb_user_field: str

    # 业务id字段，获取顺序 path > params > body
    biz_id_field: str

    def __init__(self, tb_name: str, biz_id_field: str, tb_id_field: str = "id", tb_user_field: str = "creator"):
        self.tb_name = tb_name
        self.tb_id_field = tb_id_field
        self.tb_user_field = tb_user_field
        self.biz_id_field = biz_id_field

@dataclass
class ProductDTO:
    sku_id: str
    sku_code: str
    model: str # Qwen1.5-32B-Chat
    model_category: str # qwen
    token_type: TokenType
    price: float
    unit: MetricUnit
    currency: str = 'cny'
    model_description: str = ''


@dataclass
class ChargeDTO:
    user_id: str
    token_type: TokenType
    model: str
    channel_id: str
    mount: int
    unit: MetricUnit
    date_time: str
    event_id: Optional[str] = None
    charge_success: bool = False
    charge_msg: Optional[str] = None
    trace_id: str = ''


@dataclass
class ModelApi:
    url_path: str
    req_body: dict