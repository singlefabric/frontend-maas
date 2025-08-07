# -*- coding: utf-8 -*-

import pydash

from src.apps.base_curd import BaseCURD
from src.apps.product.rsp_schema import FeeRate, PrdPriceInfo
from src.common.const.comm_const import MetricUnit, TokenType
from src.common.dto import ProductDTO
from src.system.interface import PI


class ProductCURD(BaseCURD):

    def get_prd(self, model: str=None, unit: MetricUnit=None, token_type: TokenType=None) -> list[ProductDTO]:
        """
        查询产品配置数据
        """
        prd_list = PI.product_interface.get_prd_list()
        return pydash.filter_(prd_list, lambda prd:
        (not model or prd.model == model) and
        (not unit or prd.unit == unit) and
        (not token_type or prd.token_type == token_type))

    def get_model_fee_rate(self, keyword: str=None) -> list[FeeRate]:
        fee_rate_dict: dict[str, FeeRate] = {}

        for prd in self.get_prd():
            if keyword and keyword not in prd.model:
                continue
            if not fee_rate_dict.get(prd.model):
                fee_rate_dict[prd.model] = FeeRate(model=prd.model, model_category=prd.model_category, model_description=prd.model_description or '')
            fee_rate = fee_rate_dict[prd.model]
            fee_rate.price.append(PrdPriceInfo(**pydash.pick(prd, ['token_type', 'price', 'unit', 'currency'])))
        return pydash.sort(pydash.values(fee_rate_dict), key=lambda item: item.model)


product_curd = ProductCURD()