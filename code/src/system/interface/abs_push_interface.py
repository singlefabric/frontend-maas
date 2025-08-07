# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod

from src.common.const.err_const import Err
from src.common.exceptions import MaaSBaseException


class AbsPushInterface(ABC):
    """
    推送相关接口
    """
    @abstractmethod
    def push_socket(self, action: str, resource: str, status: str, user_id: str, resource_type: str = None,
                    reason: str = None, op_id: str = None):
        """
        调用push服务推送数据到前端
        :param action: 资源 action
        :param resource: 资源 id
        :param status: 推送状态
        :param user_id: 用户 id
        :param resource_type: 资源类型
        :param reason:
        :param op_id: 操作 id
        :return:
        """
        raise MaaSBaseException(Err.NOT_IMPLEMENT)


