# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Union

from pydantic import BaseModel
from pydantic.schema import Generic
from sqlalchemy import text, and_, func
from sqlmodel import Session, select, update

from src.common.const.comm_const import ModelT, DataOper, ResourceModule
from src.common.const.err_const import Err
from src.common.context import Context
from src.common.decorate.dynamic_filter import build_query_express
from src.common.dto import QueryDTO
from src.common.exceptions import MaaSBaseException
from src.common.req_schema import BasePageReq
from src.common.utils.data import transform_to_model, get_primary_field
from src.system.db.sync_db import session_manage


class BaseCURD(Generic[ModelT]):

    def __init__(self) -> None:
        self.ModelT = self.target_type[0]

    @property
    def session(self) -> Session:
        return Context.THREAD_SESSION.get()

    @property
    def target_type(self) -> tuple:
        return self.__class__.__orig_bases__[0].__args__

    @session_manage()
    async def get_by_id(self, data_id: Union[int, str]) -> ModelT:
        """
        根据主键 id 查询数据
        :param data_id: 主键id
        :return: 单条数据 / None
        """
        return self.session.get(self.ModelT, data_id)

    @session_manage()
    async def get_all(self):
        """
        查询单表所有数据（数据量大的表慎重调用）
        :return: 多条数据
        """
        return self.session.exec(select(self.ModelT)).all()

    @session_manage()
    async def save_one(self, data: ModelT, auto_gen_id: ResourceModule = None, uuid_length: int = 8) -> ModelT:
        """
        插入单个数据对象
        :param data: 要插入的数据对象
        :param auto_gen_id: 是否自动生成 id，值为模块枚举前缀
        :param uuid_length: 生成id的后缀uuid的长度
        :return: 插入后的数据对象
        """
        obj = transform_to_model(self.ModelT, data, fill_comm_fields=DataOper.CREATE, gen_id_module=auto_gen_id, uuid_length=uuid_length)
        self.session.add(obj)
        return obj

    @session_manage()
    async def get_by_filter(self, filter_conditions: list) -> list:
        """
        根据过滤条件查询数据
        :param filter_conditions: 过滤条件列表，每个元素为字典 {"column_name": column_name, "operator": operator, "value": value}
        :return: 查询到的数据
        """
        query = self.session.query(self.ModelT)
        query_filters = []
        for filter_condition in filter_conditions:
            column_name = filter_condition["column_name"]
            operator = filter_condition["operator"]
            value = filter_condition["value"]
            express = build_query_express(operator, self.ModelT, column_name, value)
            if express is not None:
                query_filters.append(express)

        return query.filter(and_(*query_filters)).all()

    @session_manage()
    async def get_by_query_dto(self, query_dto: QueryDTO, with_count=False) -> (list, int):
        """
        根据 query dto 对象查询数据
        :param query_dto: 查询对象
        :param with_count: 是否查询数量
        :return:
        """
        key_field = get_primary_field(self.ModelT, strict=True)
        total_count = 0
        query = self.session.query(self.ModelT).filter(query_dto.express)
        if with_count:
            total_count = query.with_entities(func.count(getattr(self.ModelT, key_field))).scalar()
        if query_dto.sort_expr is not None:
            query = query.order_by(query_dto.sort_expr)
        if query_dto.page.size > 0:
            ret_list = query.offset(query_dto.page.offset).limit(query_dto.page.size).all()
        else:
            ret_list = query.all()
        return ret_list, total_count

    @session_manage()
    async def base_update(self, data_id: Union[int, str], data: Union[dict, BaseModel], strict: bool = False) -> bool:
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

        if 'update_time' in self.ModelT.__fields__:
            _data["update_time"] = datetime.now()

        update_ret = self.session.exec(update(self.ModelT).where(getattr(self.ModelT, key_field) == data_id)
                                       .values(_data))
        if strict and update_ret.rowcount == 0:
            raise MaaSBaseException(Err.OBJECT_NOT_EXISTS, fields=data_id)

        return update_ret.rowcount > 0

    @session_manage()
    async def query_by_sql(self, sql_str: str, params=None, with_count=False, page: BasePageReq=None):
        """
        执行自定义的 SQL 查询
        :param sql_str: 自定义的 SQL 查询语句
        :param params: 查询参数，例如 {"param_name": value}
        :param with_count: 是否返回查询结果的数量
        :param page: 分页对象
        :return: 查询结果和数量
        """
        if params is None:
            params = {}
        total_count = 0
        if with_count:
            count_query = f"SELECT COUNT(*) as total_count FROM ({sql_str}) as subquery"
            total_count = self.session.execute(text(count_query), params).scalar()
        if page:
            sql_str += f" limit {page.size} offset {page.offset}"
        statement = text(sql_str)
        result = self.session.execute(statement, params)
        columns = result.keys()
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return rows, total_count

    @session_manage()
    async def base_delete(self, data_id: Union[int, str], strict: bool = False) -> bool:
        """
        根据主键 id 删除数据
        :param data_id: 主键 id
        :param strict: 是否校验更新数量，如果数量为 0 抛出异常
        :return: 删除数量是否大于 0
        """

        primary_key = get_primary_field(self.ModelT, strict=True)
        deleted_count = self.session.query(self.ModelT).filter(getattr(self.ModelT, primary_key) == data_id).delete()
        if not deleted_count and strict:
            raise MaaSBaseException(Err.OBJECT_NOT_EXISTS, fields=data_id)
        return deleted_count > 0


base_curd = BaseCURD()
