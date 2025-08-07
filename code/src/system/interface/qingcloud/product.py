# -*- coding: utf-8 -*-
import json
import pydash
from cachetools import TTLCache

from src.common.asyncache import cached
from src.common.const.comm_const import MetricUnit, TTLTime, ResourceModule
from src.common.event_manage import EvictEventSubscriber
from src.common.loggers import logger
from src.common.utils.data import date_to_utc_fmt, map_user, uuid
from src.setting import settings as conf
from src.common.const.err_const import Err
from src.common.dto import ProductDTO, ChargeDTO
from src.common.exceptions import MaaSBaseException
from src.setting import settings
from src.system.interface.abs_product_interface import AbsProductInterface
from src.system.interface.qingcloud.iaas_client import iaas_client


class QingcloudProduct(AbsProductInterface):

    def get_model_category(self) -> list:
        ret = iaas_client.send_request("ProductCenterQueryRequest", {
            "action": "ProductCenterQueryRequest",
            "path": "/v1/catalogs",
            "method": "GET",
            "params": json.dumps({
                "cata_id": "inference" # 产品中心“AI API”目录
            })
        })
        if not ret.get("catalogs"):
            raise MaaSBaseException(Err.OBJECT_NOT_EXISTS, fields="AI API产品目录")
        products = pydash.get(ret.get("catalogs")[0], 'child_cata.0.products') or []
        return [pydash.pick(prod, ['prod_code', 'status', 'name', 'prod_id']) for prod in products]

    @cached(cache=TTLCache(maxsize=1024, ttl=TTLTime.PRODUCT.value), evict=EvictEventSubscriber(module=ResourceModule.PRODUCT))
    def get_prd_list(self) -> list[ProductDTO]:
        prd_list = []
        if settings.CUSTOM_PROD:
            prd_arr = json.loads(settings.CUSTOM_PROD)
            for prd in prd_arr:
                prd.update({'sku_id': '', 'sku_code': ''})
                prd_list.append(ProductDTO(**prd))
            return prd_list

        # 1. 查询产品中心AI目录并遍历
        for category in self.get_model_category():
            model_category = category['prod_code']

            # 2. 查询每个目录下不同计量方式的规格
            for unit in MetricUnit:
                params = {
                    "prod_id": model_category, # qwen
                    "console_id": settings.QINGCLOUD_CONSOLE_ID,
                    "region_id": [settings.QINGCLOUD_REGION],
                    "status": ["sale"],
                    "field_mask": ["price"],
                    "version": "latest",
                    "spec_id": unit.value,
                    "limit": 1000,
                }

                ret = iaas_client.send_request("ProductCenterQueryRequest", {
                    "action": "ProductCenterQueryRequest",
                    "path": "/v1/skus:search",
                    "method": "POST",
                    "params": json.dumps(params)
                }, strict=False)
                if ret['ret_code'] == 0:
                    for sku in ret.get("skus"):
                        for item in sku['filters']:
                            sku[item['attr_id']] = item['attr_value']
                        if not sku['prices']:
                            continue
                        price = sku['prices'][0]['price']
                        prd_list.append(ProductDTO(sku_id=sku['sku_id'], sku_code=sku['sku_code'], model=sku['model_version'],
                                                   model_category=model_category, token_type=sku['token_type'], unit=unit,
                                                   price=price, model_description=sku.get('model_description')))
                else:
                    logger.error(f'查询产品数据[{params}]失败: [{ret}]')
        logger.info(f'加载[{len(prd_list)}]条规格数据')
        return prd_list

    def charge(self, model_category, charge_data_list: list[ChargeDTO], start_time: str, end_time: str=None):
        end_time = end_time or date_to_utc_fmt()
        data_list = []
        for charge_data in charge_data_list:
            user_id = map_user(charge_data.user_id)
            event_id = uuid(None, length=16)
            charge_data.event_id = event_id
            data_list.append({
            'resource_id_ext_attrs': {
                'user_id': user_id,
                'zone_id': conf.QINGCLOUD_ZONE,
                'spec_code': charge_data.unit.value,
                'token_type': charge_data.token_type,
                'model_version': charge_data.model
            },
            'event_id': event_id,
            'meters': {charge_data.unit.value: charge_data.mount},
            'start_time': start_time,
            'end_time': end_time,
            'params': {'channel_id': charge_data.channel_id}
        })
        params = {
            'prod_code': model_category,
            'data': data_list,
        }

        # {
        #     'action': 'RequestGlueServerResponse',
        #     'data': [
        #         {'event_id': 'admin_Qwen1.5-32B-Chat_3_io_2024-09-09T10:45:23.438Z', 'result_msg': '', 'result': 'success', 'resource_id_ext': '63f7843ea185fac494bbb57e26a01a1e'},
        #         {'event_id': 'usr-GUeyohMU_Qwen1.5-32B-Chat_2_io_2024-09-09T10:45:23.438Z', 'result_msg': '', 'result': 'success', 'resource_id_ext': 'aa295182a63b001d9cb921db6b50a1a7'}],
        #     'ret_code': 0
        # }
        ret = iaas_client.send_request("RequestGlueServer", {
            "action": "RequestGlueServer",
            "path": "/api/v1/collect/PushCollectEvents",
            "method": "POST",
            "body": json.dumps(params)
        })
        trace_id = ret.get('trace_id', '')
        charge_ret_dict = pydash.group_by(ret.get('data'), 'event_id')
        for charge_data in charge_data_list:
            event_id = charge_data.event_id
            event_ret = charge_ret_dict.get(event_id)
            if not event_ret:
                # TODO 扣费问题，需要告警
                logger.error(f"计费: 缺少[{event_id}]扣费结果")
                charge_data.charge_msg = 'no response from billing'
                continue
            if event_ret[0]['result'] != 'success':
                # TODO 扣费问题，需要告警
                logger.error(f"[计费: {event_id}]扣费失败 {event_ret[0]}")
                charge_data.charge_msg = event_ret[0].get('result_msg')
            charge_data.charge_success = True
            charge_data.trace_id = trace_id


qingcloud_product = QingcloudProduct()
