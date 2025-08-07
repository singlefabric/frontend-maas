# -*- coding: utf-8 -*-
import time
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel

from src.common.const.comm_const import DEF_METRICS_POINTS, MetricsAggrType, METRICS_MAX_DAYS
from src.common.const.err_const import Err
from src.common.exceptions import MaaSBaseException
from src.common.utils.data import transform_to_list
from src.setting import settings


class ApiMetricsQuery(BaseModel):
    start_time: int
    end_time: int = int(time.time())
    step: Optional[int]
    user_id: str = ''
    api_key: str = ''
    model: str = ''
    token_type: str = ''
    unit: str = ''
    aggr_type: MetricsAggrType = MetricsAggrType.RANGE

    def __init__(self, **data):
        super().__init__(**data)

        time_range = self.end_time - self.start_time
        if  time_range > 3600 * 24 * METRICS_MAX_DAYS or time_range < 60:
            raise MaaSBaseException(Err.OUT_OF_RANGE, fields='时间区间', range='[1分钟]到[30天]之间')

        # 计算 step 值，sum类型只取一个点位，所以等于时间差；曲线类型根据默认点位总数计算，最小为采集时间间隔，并且向上取整到 5 的倍数
        if self.aggr_type == MetricsAggrType.SUM:
            self.step = time_range
        else:
            self.step = time_range // DEF_METRICS_POINTS

        # 最小时间段区间，防止出现小数
        min_unit = settings.METRICS_SCRAPE_INTERVAL * 2
        self.step = (self.step + min_unit - 1) // min_unit * min_unit

        for field in ['user_id', 'api_key', 'model', 'token_type', 'unit']:
            val = getattr(self, field)
            if val and isinstance(val, str):
                setattr(self, field, transform_to_list(val))


class ApiModelTokenMetricsQuery(BaseModel):
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    order_by: Optional[str] = "total_tokens_sum"
    model: Optional[str]
    reverse:  Optional[int] = 1
    page: Optional[int] = 1
    size: Optional[int] = 10

    def __init__(self, **data):
        super().__init__(**data)
        if self.start_time is None:
            self.start_time = datetime.now() - timedelta(days=1)
        if self.end_time is None:
            self.end_time = datetime.now()
        if self.page < 1:
            raise MaaSBaseException(Err.OUT_OF_RANGE, fields='页数', range='大于0')
        if self.size < 1:
            raise MaaSBaseException(Err.OUT_OF_RANGE, fields='单页数目', range='大于0')


class ApiUserTokenMetricsQuery(ApiModelTokenMetricsQuery):
    user: Optional[str]

