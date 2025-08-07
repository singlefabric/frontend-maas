# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional

from pydantic import StrictStr
from sqlmodel import SQLModel, Field
from src.common.const.comm_const import ApiKeyStatus


class ApiKeyBase(SQLModel):
    id: Optional[StrictStr]


class ApiKey(SQLModel, table=True):
    __tablename__ = "apikey"
    id: Optional[StrictStr] = Field(default=None, primary_key=True)
    name: str
    creator: Optional[str]
    ip_restriction: str
    update_time: Optional[datetime]
    create_time: Optional[datetime]
    last_time: Optional[datetime]
    status: str = Field(ApiKeyStatus.ACTIVE.value)

