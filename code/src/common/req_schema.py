# -*- coding: utf-8 -*-
from typing import Optional, Any
from pydantic import BaseModel

from src.common.const.comm_const import DEF_PAGE_SIZE, MAX_PAGE_SIZE


class BaseReq(BaseModel):
    """基础请求 model"""
    ...


class BaseIdReq(BaseReq):
    id: int


class BaseStrIdReq(BaseReq):
    id: str


class BasePageReq(BaseReq):
    page: Optional[int]
    offset: Optional[int]
    size: Optional[int]

    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)
        _self = __pydantic_self__

        if _self.size is None:
            _self.size = DEF_PAGE_SIZE
        _self.size = min(_self.size, MAX_PAGE_SIZE)

        if _self.offset is None:
            _self.offset = 0 if _self.page is None else (_self.page - 1) * _self.size
