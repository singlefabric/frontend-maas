# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod

from src.common.const.err_const import Err
from src.common.dto import ProductDTO, ChargeDTO
from src.common.exceptions import MaaSBaseException


class AbsProductInterface(ABC):
    """
    产品相关接口
    """

    @abstractmethod
    def get_model_category(self) -> list:
        """
        查询产品大类
        :return: 产品大类信息
        """
        raise MaaSBaseException(Err.NOT_IMPLEMENT)

    @abstractmethod
    def get_prd_list(self) -> list[ProductDTO]:
        """
        根据模型类别查询模型及定价信息
        :return: 模型及定价信息
        """
        raise MaaSBaseException(Err.NOT_IMPLEMENT)

    @abstractmethod
    def charge(self, model_category, charge_data_list: list[ChargeDTO], start_time: str, end_time: str=None):
        """
        token 计费
        :param model_category: 模型类别，如：qwen
        :param charge_data_list: 扣费数据列表
        :param start_time: 当前批次起始时间
        :param end_time: 当前批次结束时间
        """
        raise MaaSBaseException(Err.NOT_IMPLEMENT)