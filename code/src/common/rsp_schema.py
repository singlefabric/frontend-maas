# -*- coding: utf-8 -*-
from typing import Any, Generic, List, Optional, Type, Union

from fastapi.exceptions import RequestValidationError
from pydantic.generics import GenericModel
from starlette.responses import StreamingResponse
from starlette.types import Receive

from src.common.const.comm_const import ModelT
from src.common.const.err_const import Err
from src.common.context import Context
from src.common.exceptions import MaaSBaseException
from src.common.loggers import logger
from src.setting import settings


class BaseResponse(GenericModel, Generic[ModelT]):
    ret_code: int = 0
    message: str = "success"
    trace_id: str = ""

    def __init__(__pydantic_self__, **data: Any) -> None:
        super().__init__(**data)
        __pydantic_self__.trace_id = Context.TRACE_ID.get() or ""


class DataResponse(BaseResponse, Generic[ModelT]):
    data: Optional[Union[dict, ModelT]] = None


class ListResponse(BaseResponse, Generic[ModelT]):
    list: List[Union[dict, ModelT]]


class PageResponse(ListResponse, Generic[ModelT]):
    total: int = 0


class IDResponse(BaseResponse, Generic[ModelT]):
    id: str


class R(Generic[ModelT]):

    @classmethod
    def suc(cls) -> BaseResponse:
        return BaseResponse[str]()

    @classmethod
    def data(cls, data: Type[ModelT]) -> DataResponse[ModelT]:
        return DataResponse[ModelT](data=data)

    @classmethod
    def list(cls, _list: Type[List[ModelT]]) -> ListResponse[List[ModelT]]:
        return ListResponse[ModelT](list=_list)

    @classmethod
    def page(cls, _list: Type[List[ModelT]], total: int) -> PageResponse[List[ModelT]]:
        return PageResponse[ModelT](list=_list, total=total)

    @classmethod
    def id(cls, id: str) -> IDResponse[str]:
        return IDResponse(id=id)

    @classmethod
    def err(cls, exc: Exception) -> BaseResponse:
        err: Err
        params = {}
        if isinstance(exc, MaaSBaseException):
            err = exc.err
            params = exc.prams
        elif isinstance(exc, RequestValidationError):
            err = Err.VALIDATE_PARAMS
            params = {"message": str(exc)}
        else:
            err = Err.SERVER_ERR
        message = err.msg_en if settings.ERR_LANG == 'en' else err.msg_zh
        message = message.format(**params)
        return BaseResponse(ret_code=err.code, message=message)
