# -*- coding: utf-8 -*-

from cachetools import cached, TTLCache

from src.common.const.comm_const import UserPlat, TTLTime
from src.common.const.err_const import Err
from src.common.dto import User, EMPTY_USER, AccessKey
from src.common.exceptions import MaaSBaseException
from src.common.utils.data import map_user
from src.system.interface.abs_user_interface import AbsUserInterface
from src.system.interface.qingcloud.iaas_client import iaas_client


class QingCloudUser(AbsUserInterface):

    @cached(cache=TTLCache(maxsize=1024, ttl=TTLTime.USER.value))
    def get_access_key(self, user_id: str) -> AccessKey:
        user_id = map_user(user_id)
        if not user_id:
            raise MaaSBaseException(Err.REQUIRE_PARAMS, fields="user_id")
        rsp = iaas_client.send_request("DescribeAccessKeys", {"owner": [user_id], "controller": "pitrix"})
        if not rsp.get("access_key_set"):
            raise MaaSBaseException(Err.NOT_FOUND)
        item = rsp.get("access_key_set")[0]
        return AccessKey(access_key_id=item["access_key_id"], secret_access_key=item["secret_access_key"])

    @cached(cache=TTLCache(maxsize=1024, ttl=TTLTime.USER.value))
    def get_user_by_id(self, user_id: str) -> User:
        user_id = map_user(user_id)
        if not user_id:
            return EMPTY_USER
        rsp = iaas_client.send_request("DescribeUsers", {"users": [user_id]})
        if not rsp.get("user_set"):
            return EMPTY_USER
        q_user = rsp.get("user_set")[0]
        return User(user_id, q_user["user_name"], q_user["role"], UserPlat.QC_CONSOLE)


qingcloud_user = QingCloudUser()
