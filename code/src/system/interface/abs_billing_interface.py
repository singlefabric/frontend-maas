# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod

from src.common.const.comm_const import TokenType, MetricUnit
from src.common.const.err_const import Err
from src.common.exceptions import MaaSBaseException


class AbsBillingInterface(ABC):

    @abstractmethod
    def check_balance(self, user_id: str, model_category: str, model: str, token_type: TokenType, mount: int, unit: MetricUnit):
        """
        检查余额
        :param user_id: 用户id
        :param model_category: 模型大类（qwen）
        :param model: 模型名称（qwen2-6b-instant）
        :param token_type: token 类型
        :param mount: 数量（如：千 token）
        :param unit: 计量单位
        :return:
        """
        raise MaaSBaseException(Err.NOT_IMPLEMENT)

    @abstractmethod
    def get_charge_records(self, resource_id: str, user_id: str, offset: int = 0, limit: int = 20):
        """
        获取消费记录
        :param resource_id: 资源id
        :param user_id: 用户id
        :param offset: 分页偏移
        :param limit: 数量
        :return: 消费记录
        """
        raise MaaSBaseException(Err.NOT_IMPLEMENT)

    @abstractmethod
    def get_lease_contracts(self, contracts: list[str]):
        """
        获取计费合同信息
        :param contracts 合同id列表
        :return: 合同信息列表
        """
        raise MaaSBaseException(Err.NOT_IMPLEMENT)

