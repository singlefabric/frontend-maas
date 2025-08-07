# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional

from pydantic import StrictStr, BaseModel
from sqlmodel import SQLModel, Field
from src.common.const.comm_const import ChannelStatus


class ChannelBase(SQLModel):
    id: Optional[str]
    name: Optional[str]


class Channel(SQLModel, table=True):
    __tablename__ = "channel"
    id: Optional[StrictStr] = Field(default=None, primary_key=True)
    name: str
    channel_type_id: str
    model_redirection: Optional[str]
    inference_secret_key: str
    inference_service: str
    update_time: datetime
    create_time: datetime
    status: str = Field(default=ChannelStatus.ACTIVE.value)
    health_status: Optional[int] = 1


class ChannelType(SQLModel, table=True):
    __tablename__ = "channel_type"
    id: Optional[StrictStr] = Field(default=None, primary_key=True)
    name: Optional[str]


class ChannelToModel(SQLModel, table=True):
    __tablename__ = "channel_to_model"
    channel_id: Optional[str] = Field(default=None, primary_key=True)
    model_id: Optional[str] = Field(default=None, primary_key=True)


class TypeInfo(BaseModel):
    id: Optional[str]
    name: Optional[str]


class ChannelInfo(BaseModel):
    id: str
    name: str
    channel_type: TypeInfo
    model_redirection: Optional[str]
    inference_secret_key: str
    inference_service: str
    model: list[TypeInfo]
    update_time: datetime
    create_time: datetime
    status: ChannelStatus



