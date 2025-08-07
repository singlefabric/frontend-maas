# -*- coding: utf-8 -*-

import base64
import copy
import hashlib
import hmac
import random
import string
from collections import OrderedDict
from datetime import datetime
from hashlib import sha256
from typing import Any, Optional
from urllib import parse

from pydantic import BaseModel
from sqlalchemy.inspection import inspect
from sqlmodel import SQLModel

from src.common.const.comm_const import ModelT, DataOper, ResourceModule
from src.common.const.err_const import Err
from src.common.context import Context
from src.common.exceptions import MaaSBaseException, GatewayException
from src.common.rsp_schema import R, BaseResponse
from src.setting import settings


def wrap_rsp(response=None, total=-1, data_model: ModelT = None):
    """
    返回值包装为标准格式
    :param response: 原返回值
    :param data_model: 泛型
    :param total: 分页返回的数据总量
    :return: 包装后返回值
    """
    if response is None:
        return R.suc()
    if not isinstance(response, BaseResponse):
        if isinstance(response, (int, str)):
            return R[data_model].id(id=response)
        if isinstance(response, list):
            if total > -1:
                return R[data_model].page(_list=response, total=total)
            return R[data_model].list(_list=response)
        elif isinstance(response, object):
            return R[data_model].data(data=response)
    return response


def get_primary_field(model_class: SQLModel, strict: bool = False) -> str:
    """
    从 SQLModel 类中获取主键字段
    :param model_class: SQLModel 类
    :param strict: 是否严格校验，不存在字段时抛出异常
    :return: 主键字段名称
    """
    primary_keys = inspect(model_class).primary_key
    if not primary_keys and strict:
        raise MaaSBaseException(Err.SERVER_ERR)
    return primary_keys[0].name if primary_keys else None


def transform_to_model(target_model_cls, obj, fill_comm_fields: DataOper = None,
                       gen_id_module: ResourceModule = None, uuid_length: int = 8) -> ModelT:
    """
    其他对象转 SQLModel 对象，用来存储数据库
    :param target_model_cls: 目标 SQLModel class
    :param obj: 源对象（普通对象或者 Pydantic 对象）
    :param fill_comm_fields: 是否填充公共字段数据，可选 create 或 update
    :param gen_id_module: 生成主键 id 的模块（前缀），不传不会生成 id
    :param uuid_length: 生成主键 id 后缀的的长度
    :return: 转换后的 SQLModel 对象
    """

    if isinstance(obj, dict):
        obj_dict = obj
    elif isinstance(obj, BaseModel):
        obj_dict = obj.dict()
    else:
        raise MaaSBaseException(Err.SERVER_ERR)

    model_obj = target_model_cls(**obj_dict)
    if gen_id_module:
        key_field = get_primary_field(target_model_cls, strict=True)
        model_obj.__dict__[key_field] = uuid(gen_id_module, length=uuid_length)

    now = datetime.now()
    if fill_comm_fields == DataOper.CREATE:
        if hasattr(model_obj, "create_time"):
            model_obj.create_time = now
        if hasattr(model_obj, "update_time"):
            model_obj.update_time = now
        if hasattr(model_obj, "creator"):
            model_obj.creator = Context.USER.get().user_id
    elif fill_comm_fields == DataOper.UPDATE:
        if hasattr(model_obj, "update_time"):
            model_obj.update_time = now
    return model_obj


def transform_to_list(data: Any, sep: str = ","):
    """
    数据转 list
    :param data: 数据，目前支持字符串
    :param sep: 分隔符
    :return: list
    """
    if not isinstance(data, str):
        return data
    return data.split(sep)


def date_to_utc_fmt(dt: datetime=None) -> str:
    """
    转换为utc时间字符串
    """
    return (dt or datetime.utcnow()).isoformat(timespec='milliseconds') + 'Z'


def hex_encode_md5_hash(data):
    if not data:
        data = "".encode("utf-8")
    else:
        data = data.encode("utf-8")
    md5 = hashlib.md5()
    md5.update(data)
    return md5.hexdigest()


def get_signature(method: str, url: str, ak: str, sk: str, params: dict):
    """
    计算签名
    :param url: 签名url地址，如 /api/test
    :param ak: access_key_id
    :param sk:  secure_key
    :param params: url 中参数
    :param method: method GET POST PUT DELETE
    :return: 添加签名后的 url
    """

    url += "/" if not url.endswith("/") else ""
    params["access_key_id"] = ak
    sorted_param = OrderedDict()
    keys = sorted(params.keys())
    for key in keys:
        if isinstance(params[key], list):
            sorted_param[key] = sorted(params[key])
        else:
            sorted_param[key] = params[key]

    url_param = parse.urlencode(sorted_param, safe='/', quote_via=parse.quote, doseq=True)
    string_to_sign = method + "\n" + url + "\n" + url_param + "\n" + hex_encode_md5_hash("")

    h = hmac.new(sk.encode(encoding="utf-8"), digestmod=sha256)
    h.update(string_to_sign.encode(encoding="utf-8"))
    sign = base64.b64encode(h.digest()).strip()
    signature = parse.quote_plus(sign.decode())
    signature = parse.quote_plus(signature)
    url_param += "&signature=%s" % signature
    return url_param


# 生成随机字符串
def uuid(prefix: Optional[ResourceModule], length=8) -> str:
    ascii_letters = string.ascii_letters + string.digits
    uuid_str = ''.join(random.choice(ascii_letters) for _ in range(length))
    return f"{prefix.value}-{uuid_str}" if prefix else uuid_str


# 如果配置了账号映射关系，返回映射的账号
def map_user(user_id: str):
    return settings.ACCOUNT_MAPPING.get(user_id, user_id)


def count_characters(s):
    """
    统计字符串中字符数量
    其中1个汉字算2个字符，英文、标点符号、空格均按照1个字符
    """
    total_chars = 0
    for char in s:
        # 判断字符是否为汉字
        if '\u4e00' <= char <= '\u9fff':
            total_chars += 2
        else:
            total_chars += 1
    return total_chars


def replace_model(body: dict, proxy_model) -> dict:
    if not body or 'model' not in body:
        return body
    new_body = copy.deepcopy(body)
    new_body['model'] = proxy_model
    return new_body
