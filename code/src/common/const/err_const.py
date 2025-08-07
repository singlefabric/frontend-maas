# -*- coding: utf-8 -*-
from enum import Enum


class Err(Enum):
    """
    异常常量
    """
    NOT_FOUND = (404, '您查询的资源不存在', 'resource not found')
    AUTH_INSUFFICIENT = (403, '权限不足', 'Insufficient authority')
    SERVER_ERR = (500, '内部错误', 'system error')

    # 用户、权限、资金相关
    NOT_LOGIN = (401, '用户未登录', 'user is not login')
    AUTH_PLAT_ERR = (401, '权限错误，接口需要平台[{plat}]权限', 'auth error, api need plat [{plat}] auth')
    AUTH_ROLE_ERR = (401, '权限错误，接口无权调用', 'auth error, api has no auth')
    AUTH_OWNER_ERR = (401, '权限错误，非本人资源，无法操作', 'auth error, is not resource owner')
    NOT_ENOUGH_MONEY = (401, '余额不足，需要支付[{need_cash}]元，请充值后再使用', 'not enough money, need pay ￥[{need_cash}]')

    # 参数校验相关
    REQUIRE_PARAMS = (422, '缺少参数[{fields}]', 'require params [{fields}]')
    OBJECT_EXISTS = (422, '[{fields}]已存在', '[{fields}] already exists')
    OBJECT_NOT_EXISTS = (422, '[{fields}]不存在', '[{fields}] not exists')
    OUT_OF_RANGE = (422, '超过[{fields}]范围[{range}]', '[{fields}] out of range[{range}]')
    VALIDATE_PARAMS = (422, '参数校验失败[{message}]', 'validate param error [{message}]')

    # 1201 - 1300 业务相关
    NOT_IMPLEMENT = (501, '功能未实现', 'function is not implemented')
    INTERFACE_FAILED = (500, '接口[{action}]请求失败: {message}', 'interface [{action}] request failed: {message}')
    NOT_SUPPORT = (501, '不支持的业务[{message}]', 'not support {message}')
    CHANNEL_CONNECT_FAILED = (500, 'channel连接失败[{message}]', 'channel connecting failed {message}')

    # 1301 - 1400 系统相关
    DATABASE_ERR = (500, '数据库操作错误', 'database operation error')

    def __new__(cls, code, msg_zh, msg_en):
        obj = object.__new__(cls)
        obj._value_ = str(code) + msg_zh
        obj.code = code
        obj.msg_zh = msg_zh
        obj.msg_en = msg_en
        return obj
