# -*- coding: utf-8 -*-
from cachetools import TTLCache
from typing import Union
from pydantic import BaseModel

from src.apps.base_curd import BaseCURD
from src.common.const.err_const import Err
from src.common.asyncache import cached
from src.common.const.comm_const import TTLTime, LAST_TIME_DIC, ResourceModule
from src.common.dto import QueryDTO
from sqlmodel import update, case, null

from src.common.event_manage import EvictEventSubscriber
from src.system.db.sync_db import session_manage
from src.apps.apikey.rsp_schema import ApiKey
from src.common.utils.data import get_primary_field
from src.common.exceptions import MaaSBaseException
from src.apps.apikey.req_schema import ApikeyLastTimeUpdate


class ApiKeyCURD(BaseCURD[ApiKey]):

    @session_manage()
    async def list_page(self, query_dto: QueryDTO) -> (list, int):
        ret_list, total_count = await self.get_by_query_dto(query_dto, with_count=True)
        return ret_list, total_count

    @session_manage()
    async def save_last_time(self):
        """
        保存apikey的last time
        """
        for apikey_item in LAST_TIME_DIC:
            apikey_last_time_update = ApikeyLastTimeUpdate(
                last_time=LAST_TIME_DIC[apikey_item]
            )
            await apikey_curd.update_last_time(apikey_item, apikey_last_time_update)

    @session_manage()
    async def update_last_time(self, data_id: Union[int, str], data: Union[dict, BaseModel], strict: bool = False) -> bool:
        """
        根据主键 id 更新数据
        :param data_id: 主键
        :param data: 要更新的数据，字典或 pydantic 对象，例如 {"column_name": value}
        :param strict: 是否校验更新数量，如果数量为 0 抛出异常
        :return: 更新数量是否大于 0
        """
        key_field = get_primary_field(self.ModelT, strict=True)
        _data = data.dict(exclude_none=True) if isinstance(data, BaseModel) else data

        if not _data:
            raise MaaSBaseException(Err.VALIDATE_PARAMS, message="缺少update参数")
        new_last_time = _data['last_time']

        # 创建更新语句
        stmt = (
            update(self.ModelT).where(
                getattr(self.ModelT, key_field) == data_id
            ).values(
                last_time=case(
                    (self.ModelT.last_time == null(), new_last_time),
                    (new_last_time > self.ModelT.last_time, new_last_time),
                    else_=self.ModelT.last_time
                )
            )
        )
        update_ret = self.session.execute(stmt)
        if strict and update_ret.rowcount == 0:
            raise MaaSBaseException(Err.OBJECT_NOT_EXISTS, fields=data_id)
        return update_ret.rowcount > 0

    @cached(cache=TTLCache(maxsize=1024, ttl=TTLTime.APIKEY.value), evict=EvictEventSubscriber(module=ResourceModule.SECRET_KEY))
    async def query_by_id_and_cache(self, apikey_id) -> ApiKey:
        """
        根据 id 查询令牌并缓存
        """
        return await self.get_by_id(apikey_id)


apikey_curd = ApiKeyCURD()
