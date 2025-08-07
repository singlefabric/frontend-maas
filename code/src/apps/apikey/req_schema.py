# -*- coding: utf-8 -*-
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ApikeyCreate(BaseModel):
    name: Optional[str]


class ApikeyUpdate(ApikeyCreate):
    status: Optional[str]


class ApikeyLastTimeUpdate(ApikeyCreate):
    last_time: Optional[datetime]