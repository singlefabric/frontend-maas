# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sqlmodel import SQLModel

from src.common.const.comm_const import TokenType


@dataclass
class PrdPriceInfo:
    token_type: TokenType
    price: float
    unit: str
    currency: str

class FeeRate(SQLModel, table=False):
    model: str
    model_category: str
    price: list[PrdPriceInfo] = []
    model_description: str = ''

