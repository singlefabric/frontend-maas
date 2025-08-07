# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod

from src.common.const.err_const import Err
from src.common.dto import User, AccessKey
from src.common.exceptions import MaaSBaseException


class AbsUserInterface(ABC):
    """
    用户相关接口
    """
    @abstractmethod
    def get_user_by_id(self, user_id: str) -> User:
        """
        查询用户信息
        :param user_id: 用户id
        :return: 用户信息
        """
        raise MaaSBaseException(Err.NOT_IMPLEMENT)

    @abstractmethod
    def get_access_key(self, user_id: str) -> AccessKey:
        """
        查询用户 access key
        :param user_id: 用户 id
        """
        raise MaaSBaseException(Err.NOT_IMPLEMENT)

