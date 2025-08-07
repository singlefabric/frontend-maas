# -*- coding: utf-8 -*-

from typing import Optional, List, Any

from pydantic import BaseModel
from sqlmodel import SQLModel


class PriceInfo:
    replicas: int


class Contract(BaseModel):
    charge_mode: str
    next_charge_mode: Optional[str]
    create_time: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    price_info: Optional[PriceInfo]
    discount: int
    price: float
    duration: str
    auto_renew: int


class LeaseInfo(SQLModel, table=False):
    status: str
    lease_time: Optional[str]
    status_time: str
    unlease_time: Optional[str]
    renewal_time: Optional[str]
    renewal: str
    contract: Contract


class Price(SQLModel, table=False):
    original_price: float
    available_coupon: float
    price: float
    normal_price: float
    discount: float
    discount_details: dict
    available_coupon_set: List[Any]


class ChargeRecord(SQLModel, table=False):
    unit: str
    start_time: str
    charge_time: str
    duration: str
    fee: str
    end_time: str
    remarks: str
    discount: float
    total_sum: float
    price: str
    contract_id: str


class ChargeData(SQLModel, table=False):
    charge_record_set: List[ChargeRecord]
    total_sum: str
    total_count: int
