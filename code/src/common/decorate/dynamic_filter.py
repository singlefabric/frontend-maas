# -*- coding: utf-8 -*-
import functools
from typing import List, Optional, Any

from fastapi import Request
from src.common.context import Context
from sqlalchemy import or_, and_, desc, BinaryExpression
from sqlmodel import SQLModel

from src.common.dto import QueryDTO
from src.common.utils.data import transform_to_list


def build_query_express(operate: str, model_type: type(SQLModel), column_name: str,
                        value: Any) -> Optional[BinaryExpression]:
    """
    根据查询操作构建查询表达式
    :param operate: 查询操作，如 like、eq等
    :param model_type: SqlModel 类
    :param column_name: 字段名
    :param value: 过滤值
    :return: 查询表达式
    """
    express = None
    column = getattr(model_type, column_name, None)
    if not column or not value:
        return None
    if operate == "like":
        express = column.like(f"%{value}%")
    elif operate == "not_like":
        express = ~column.like(f"%{value}%")
    elif operate == "lt":
        express = column < value
    elif operate == "gt":
        express = column > value
    elif operate == "lte":
        express = column <= value
    elif operate == "gte":
        express = column >= value
    elif operate == "eq":
        express = column == value
    elif operate == "ne":
        express = column != value
    elif operate == "is_in":
        express = column.in_(transform_to_list(value))
    elif operate == "not_in":
        express = ~column.in_(transform_to_list(value))
    elif operate == "not_null":
        express = column.isnot(None)
    elif operate == "is_null":
        express = column.is_(None)

    return express


def param_to_query(like: List[str] = None, lt: List[str] = None, gt: List[str] = None, lte: List[str] = None,
                   gte: List[str] = None, is_in: List[str] = None, not_in: List[str] = None, ne: List[str] = None,
                   eq: List[str] = None, keyword_fields: List[str] = None, sort_fields: List[str] = None,
                   table_type: type(SQLModel) = None, filter_delete: bool = False, query_with_user: bool = False,
                   without_page: bool = False):
    """
    该装饰器用于将参数转换为查询条件。

    :param like: 用于模糊查询的字段列表
    :param lt: 用于小于查询的字段列表
    :param gt: 用于大于查询的字段列表
    :param lte: 用于小于等于查询的字段列表
    :param gte: 用于大于等于查询的字段列表
    :param is_in: 用于in查询的字段列表
    :param not_in: 用于not in查询的字段列表
    :param ne: 用于不等于查询的字段列表
    :param eq: 用于等于查询的字段列表
    :param keyword_fields: 用于关键词查询的字段列表
    :param sort_fields: 允许排序的字段列表
    :param table_type: 表类型，用于指定查询的表
    :param filter_delete: 过滤状态为delete的查询结果
    :param query_with_user: 过滤创建者是请求用户的结果
    :param without_page: 不分页，返回所有的数据

    示例用法:
        @param_to_query(
        eq=['version_id', 'model_id'],
        keyword_fields=["version_name"],
        table_type=ModelVersion,
        is_in=["version_id", "version_name"],
        gt=["create_time", "update_time"],
        lt=["create_time","update_time"])
        async def list_page(request: Request):
            ...

    :param table_type: 表类型，格式如下:
        class ModelVersion(Base):
            __tablename__ = 'model_version'
            version_id = Column(String, primary_key=True)
            version_name = Column(String)
            ...
    """
    def wrap(func):
        @functools.wraps(func)
        async def wrapped_func(request: Request):

            query_params = dict(request.query_params)
            if eq:
                query_params.update({f"{key}_eq": query_params[key] for key in eq if key in query_params})

            config_params = {
                "like": like, "lt": lt, "gt": gt, "lte": lte, "gte": gte, "eq": eq, "ne": ne, "is_in": is_in,
                "not_in": not_in
            }

            # 拼查询对象
            query_filters = []
            for operate, fields in config_params.items():
                if not fields:
                    continue
                for field in fields:
                    query_val = query_params.get(f"{field}_{operate}")  # name_like
                    express = build_query_express(operate, table_type, field, query_val)
                    if express is not None:
                        query_filters.append(express)

            # 添加过滤掉状态为 'delete' 的条件
            filter_delete_param = query_params.get("filter_delete")
            if not filter_delete_param or filter_delete_param != 'false':
                if filter_delete:
                    query_filters.append(getattr(table_type, 'status') != 'delete')

            if query_with_user:
                query_filters.append(getattr(table_type, 'creator') == Context.USER.get().user_id)

            # key_words 单独处理
            key_words = query_params.get("key_words")
            keyword_filters = []
            if key_words and keyword_fields:
                for field in keyword_fields:
                    column = getattr(table_type, field, None)
                    if column:
                        keyword_filters.append(column.like(f"%{key_words}%"))

            # 排序字段
            sort_key = query_params.get("sort_key")
            reverse = int(query_params.get("reverse", 1))
            sort_expr = None
            if sort_fields:
                sort_key = sort_key if sort_key and sort_key in sort_fields else sort_fields[0]
                sort_expr = getattr(table_type, sort_key) if not reverse else desc(getattr(table_type, sort_key))
            if without_page:
                return QueryDTO(and_(*query_filters, or_(*keyword_filters)), query_params.get("page"),
                                query_params.get("offset"), -1, sort_expr)
            else:
                return QueryDTO(and_(*query_filters, or_(*keyword_filters)), query_params.get("page"),
                                query_params.get("offset"), query_params.get("size"), sort_expr)
        return wrapped_func
    return wrap
