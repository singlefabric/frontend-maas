# -*- coding: utf-8 -*-
from typing import Optional

from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    channel_type_id: str
    name: str
    model_id: list[str]
    model_redirection: Optional[str]
    inference_secret_key: str
    inference_service: str


class ChannelUpdateBase(BaseModel):
    channel_type_id:  Optional[str]
    name:  Optional[str]
    model_redirection: Optional[str]
    inference_secret_key: Optional[str]
    inference_service: Optional[str]
    status: Optional[str]


class ChannelUpdate(ChannelUpdateBase):
    model_id: Optional[list[str]]


class ChannelReq(BaseModel):
    id: Optional[str] = Field('', max_length=32)
    name: str = Field(..., min_length=2, max_length=32)
    inference_secret_key: Optional[str] = Field('', max_length=128)
    inference_service: str = Field(..., max_length=256)
    model_name: Optional[str] = Field('', max_length=64)