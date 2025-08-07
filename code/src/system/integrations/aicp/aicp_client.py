# -*- coding: utf-8 -*-
from enum import Enum

import requests

from src.common.const.err_const import Err
from src.common.context import Context
from src.common.dto import AccessKey, KS_ADMIN_USER
from src.common.exceptions import MaaSBaseException
from src.common.loggers import logger
from src.common.utils import data as util
from src.setting import settings
from src.system.interface import qingcloud_user


# 鉴权方式：集群内服务，使用header aicp-userid；集群外服务，使用签名
class AuthType(str, Enum):
    HEADER = 'header'
    SIGNATURE = 'signature'
    NONE = 'none'


def send_request(host, path, params=None, data=None, user_id=None, auth_type: AuthType = AuthType.HEADER, method: str = 'GET', timeout: int = 5, json=None):
    params = {} if params is None else params
    user_id = user_id or Context.USER.get().user_id
    headers = {'Content-Type': 'application/json', 'aicp-userid': user_id}
    if auth_type == AuthType.SIGNATURE:
        if Context.USER.get() == KS_ADMIN_USER:
            key: AccessKey = AccessKey(settings.QINGCLOUD_ACCESS_KEY_ID, settings.QINGCLOUD_SECRET_ACCESS_KEY)
        else:
            key: AccessKey = qingcloud_user.get_access_key(user_id)
        path = path + '?' + util.get_signature(method, path, key.access_key_id, key.secret_access_key, params)

    url = f'{host}{path}'
    logger.debug(f'[AICP-REQ] {url}')
    if method == 'GET':
        rep = requests.get(url, headers=headers, params=params if auth_type != AuthType.SIGNATURE else {}, timeout=timeout)
    elif method == 'POST':
        rep = requests.post(url, headers=headers, data=data, json=json, timeout=timeout)
    else:
        raise MaaSBaseException(Err.NOT_IMPLEMENT)
    if rep.status_code != 200:
        logger.error(f"[AICP-ERR] 请求 [{url}] 失败: [{rep.status_code}][{rep.text}]")
        raise MaaSBaseException(Err.INTERFACE_FAILED, action="send_aicp_request",
                                message="Request failed with status code: " + str(rep.status_code))
    try:
        _data = rep.json()
        if _data.get('ret_code') != 0:
            logger.error(f"[AICP-ERR] 请求 [{url}] 失败: [{_data.get('ret_code')}][{_data.get('message')}]")
            raise MaaSBaseException(Err.INTERFACE_FAILED, action="send_aicp_request", message=_data.get('message'))
        logger.debug(f'[AICP-RSP] {_data}')
        return _data
    except ValueError:
        raise MaaSBaseException(Err.INTERFACE_FAILED, action="send_aicp_request", message="Response content is not valid JSON")
