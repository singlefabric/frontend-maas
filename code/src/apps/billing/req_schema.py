# -*- coding: utf-8 -*-
from typing import Optional

from pydantic import BaseModel

from src.common.req_schema import BasePageReq


class GetChargeReq(BasePageReq):
    resource_id: str
    user_id: Optional[str] = None


class BillingEvent(BaseModel):
    id: str  # e8a14589-e43b-4ca4-8bfa-18d8d82e6b28
    source: str  # billing
    specversion: str  # 1.0
    type: str  # user.balance.recharge / user.balance.insufficient
    datacontenttype: Optional[str]  # application/json
    time: Optional[str]  # 2024-08-21T09:16:38.955624Z
    data: Optional[dict]  # {"user_id": "usr-123"}
