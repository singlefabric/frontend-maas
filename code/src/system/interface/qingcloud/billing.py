# -*- coding: utf-8 -*-
import json

from src.common.const.comm_const import TokenType, MetricUnit
from src.common.utils.data import map_user
from src.setting import settings
from src.system.interface.abs_billing_interface import AbsBillingInterface
from src.system.interface.qingcloud.iaas_client import iaas_client


# 云平台计费配置
ZONE = settings.QINGCLOUD_ZONE


class QingcloudBilling(AbsBillingInterface):

    def get_lease_contracts(self, contracts: list[str]):
        return iaas_client.send_request("GetLeaseContracts", {"contracts": contracts})

    def get_charge_records(self, model_category: str, user_id: str, offset: int = 0, limit: int = 20, start_time=None, end_time=None):
        return iaas_client.send_request("GetChargeRecords", {
            "resource_type": model_category,
            "user": map_user(user_id),
            "zone": ZONE,
            "offset": offset,
            "limit": limit,
            "start_time": start_time,
            "end_time": end_time,
        })


    def check_balance(self, user_id: str, model_category: str, model: str, token_type: TokenType, mount: int, unit: MetricUnit):
        price_info = {
            "spec_id": unit,
            "model_version": model,
            "token_type": token_type,
            unit: mount,
            "attr_bill_mode": "usage_resource"
        }
        return iaas_client.send_request("CheckResourcesBalance", {
            "user": map_user(user_id),
            "zone": ZONE,
            "currency": "cny",
            "price_type": "new",
            "resources": [{
                "resource_type": model_category,
                "price_info": json.dumps(price_info)
            }]
        }, strict=False)

qingcloud_billing = QingcloudBilling()