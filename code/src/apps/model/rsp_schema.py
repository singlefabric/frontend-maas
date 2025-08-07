# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional

from pydantic import StrictStr, BaseModel
from sqlalchemy import JSON
from sqlmodel import SQLModel, Field


class ModelTag(SQLModel):
    id: str
    name: str
    type: str


class ModelBase(SQLModel):
    id: Optional[StrictStr] = Field(default=None, primary_key=True)
    name: str
    icon: Optional[str] = ''
    brief: Optional[str] = ''
    developer: Optional[str] = ''
    maas_id_map: Optional[dict] = Field(default=None, sa_type=JSON)
    is_experience: Optional[int] = 0
    create_time: Optional[datetime]
    update_time: Optional[datetime]


class Model(ModelBase, table=True):
    __tablename__ = "model"
    creator: str
    status: Optional[str]


class ModelParam(SQLModel, table=True):
    __tablename__ = "model_param"
    id: Optional[int] = Field(primary_key=True)
    key: str
    value: str
    min: Optional[StrictStr]
    max: Optional[StrictStr]
    tag_id: str
    model_id: Optional[StrictStr]


class ModelParamInfo(BaseModel):
    key: str
    value: str
    min: str
    max: str

