# -*- coding: utf-8 -*-
from dataclasses import asdict
from http import HTTPStatus
from time import sleep

import pydash

from src.apps.base_curd import BaseCURD
from src.apps.metrics.schema import ApiInvokeInfoBuilder
from src.apps.product.curd import product_curd
from src.common.const.comm_const import Switch, MetricUnit, TTLTime
from src.common.dto import ChargeDTO
from src.common.exceptions import GatewayException
from src.common.loggers import logger
from src.common.utils.data import date_to_utc_fmt
from src.setting import settings
from src.system.integrations.cache.redis_client import redis_client
from src.system.integrations.logging.opensearch_client import opensearch_client
from src.system.interface import PI


class BillingCURD(BaseCURD):

    # @cached(cache=TTLCache(maxsize=1024, ttl=TTLTime.BALANCE.value))
    @staticmethod
    def valid_balance(user_id: str, model: str, unit: MetricUnit) -> bool:
        """
        校验用户余额
        数据缓存在 redis 和内存中，内存缓存2分钟，redis缓存10分钟
        :param user_id: 账户
        :param model: 模型 (qwen2-1.5b-instant)
        :param unit: 计量单位
        :return: 是否有足够的余额(代金券)
        """
        prod_list = product_curd.get_prd(model=model, unit=unit)
        if not prod_list:
            raise GatewayException(f'模型[{model}]不存在', HTTPStatus.NOT_FOUND)
        prod_dto = prod_list[0]

        key = f'bal-enough:{user_id}:{model}'
        bal_enough = redis_client.get(key)
        if bal_enough is None:
            ret = PI.billing_interface.check_balance(user_id, prod_dto.model_category, model, prod_dto.token_type, 1, unit=unit)
            bal_enough = str(ret['ret_code'] == 0)
            redis_client.set(key, bal_enough, ex=settings.EXP_TIME_BAL_ENOUGH)
        return bal_enough == Switch.ON

    @staticmethod
    def evict_balance_cache(user_id: str):
        models = pydash.uniq(pydash.map_(product_curd.get_prd(), 'model'))
        keys = [f'{settings.REDIS_PREFIX}bal-enough:{user_id}:{model}' for model in models]
        count = redis_client.conn.delete(*keys)
        if count:
            logger.info(f'【计费事件】清理[{user_id}]余额缓存数[{count}]')

    @staticmethod
    def async_charge():
        """
        计费
        """
        logger.info('token 用量计费')
        start_time = date_to_utc_fmt()
        for meta_info in ApiInvokeInfoBuilder.BillMetaInfo:
            # todo 需要考虑原子性
            key = f'{settings.REDIS_PREFIX}{meta_info.cache_key}'
            items = redis_client.conn.zrangebyscore(key, meta_info.rate.value, float('inf'), withscores=True)
            # [('usr-GUeyohMU:Qwen2-7B-Instruct:ch-000001:input', 1618.0), ('usr-Nl0Qvcx9:Qwen2-7B-Instruct:ch-000002:input', 3712.0),
            # ('usr-Q6KHaObi:Qwen2-7B-Instruct:ch-000003:input', 13239.0), ('usr-Q6KHaObi:Qwen2-7B-Instruct:ch-000003:output', 18034.0)]
            for item in items:
                # 兼容新旧两种格式
                field_arr = item[0].split(':')
                if len(field_arr) == 4:
                    [user_id, model, channel_id, token_type] = field_arr
                else:
                    [user_id, model, token_type] = field_arr
                    channel_id = ''
                mount = item[1]
                try:
                    prd_dto_list = product_curd.get_prd(model=model, token_type=token_type, unit=meta_info.unit)
                    if not prd_dto_list:
                        logger.error(f'找不到产品信息[{model}][{token_type}][{meta_info.unit}], 无法扣费: {item[0]}')
                        continue
                    prd_dto = prd_dto_list[0]

                    # 扣费
                    charge_mount = mount //  meta_info.rate.value
                    charge_dto = ChargeDTO(user_id, token_type, model, channel_id, charge_mount, prd_dto.unit, start_time)
                    PI.product_interface.charge(prd_dto.model_category, [charge_dto], start_time)
                    if not charge_dto.charge_success:
                        logger.error(f'扣费失败: {charge_dto}')
                    else:
                        redis_client.conn.zincrby(key, charge_mount * meta_info.rate.value * -1, item[0])
                    logger.info(f'扣费信息: {charge_dto}')
                    opensearch_client.submit_billing_log([asdict(charge_dto)])
                    sleep(0.1)
                except Exception as e:
                    logger.exception(f'处理扣费项[{item}]异常')
            redis_client.conn.zremrangebyscore(key, 0, 0)
            logger.info(f'[{meta_info.cache_key}]剩余未计费数量[{redis_client.conn.zcard(key)}]')

    async def get_charge_records(self, user_id: str, offset: int = 0, limit: int = 20, start_time=None, end_time=None):
        """
        扣费记录查询
        """
        category_list = PI.product_interface.get_model_category()
        charge_record_set = []
        total_count = 0
        total_sum = 0
        for category in category_list:
            charge_record_ret = PI.billing_interface.get_charge_records(category['prod_code'], user_id, offset, limit, start_time, end_time)
            records = charge_record_ret['charge_record_set']
            if not records:
                continue
            contracts = [record['contract_id'] for record in records if record.get('contract_id')]
            contracts_dict = PI.billing_interface.get_lease_contracts(contracts).get('lease_contract_set', {})

            for record in records:
                _record = pydash.pick(record, ['resource_type', 'fee', 'charge_time', 'total_sum', 'contract_id'])
                contract_id = record.get('contract_id')
                if contract_id in contracts_dict:
                    _record.update(pydash.pick(contracts_dict[contract_id].get('price_info'), ['spec_id', 'token_type', 'model_version']))

                charge_record_set.append(_record)
            total_count += charge_record_ret['total_count']
            total_sum += float(charge_record_ret['total_sum'])
        charge_record_set.sort(key=lambda x: x['charge_time'], reverse=True)
        return {
            'charge_record_set': charge_record_set[0: limit],
            'total_count': total_count,
            'total_sum': total_sum
        }

billing_curd = BillingCURD()