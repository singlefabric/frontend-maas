# -*- coding: utf-8 -*-
from src.common.dto import User, AccessKey, ChargeDTO
from src.system.interface import AbsPushInterface
from src.system.interface.abs_billing_interface import AbsBillingInterface
from src.system.interface.abs_product_interface import AbsProductInterface
from src.system.interface.abs_user_interface import AbsUserInterface


class MockUser(AbsUserInterface):

    def get_access_key(self, user_id: str) -> AccessKey:
        return AccessKey(access_key_id="", secret_access_key="")

    def get_user_by_id(self, user_id: str) -> User:
        return User("usr-12345", "user", "测试用户")


class MockPush(AbsPushInterface):

    def push_socket(self, action: str, resource: str, status: str, user_id: str, resource_type: str = None,
                    reason: str = None, op_id: str = None):
        ...


class MockBilling(AbsBillingInterface):

    def get_lease_contracts(self, contracts: list[str]):
        return {"contracts": [], "lease_contract_set": {}, "action": "GetLeaseContractsResponse", "ret_code": 0}

    def get_charge_records(self, resource_id: str, user_id: str, offset: int = 0, limit: int = 20):
        # {'charge_record_set': [{'resource_type': 'qai', 'fee': '44.48', 'user_id': 'usr-mj3o0PTr', 'zone_id': 'staging', 'resource_id': 'qai-inf-88888888', 'start_time': '2024-04-25T09:49:59Z', 'tags': [], 'charge_item': '', 'console_id': 'admin', 'currency': 'cny', 'root_user_id': 'usr-mj3o0PTr', 'resource_name': '', 'remarks': 'resource has been changed, charge fee', 'end_time': '2024-04-25T11:49:59Z', 'duration': '1h', 'charge_time': '2024-04-25T09:49:59Z', 'total_sum': 0, 'discount': 100, 'price': '22.24', 'unit': 'hour', 'contract_id': 'ct-IUjym5Se'}, {'resource_type': 'qai', 'fee': '0.4355', 'user_id': 'usr-mj3o0PTr', 'zone_id': 'staging', 'resource_id': 'qai-inf-88888888', 'start_time': '2024-04-25T09:47:38Z', 'tags': [], 'charge_item': '', 'console_id': 'admin', 'currency': 'cny', 'root_user_id': 'usr-mj3o0PTr', 'resource_name': '', 'remarks': 'resource has been created, charge fee', 'end_time': '2024-04-25T09:49:59Z', 'duration': '1h', 'charge_time': '2024-04-25T09:49:07Z', 'total_sum': 0, 'discount': 100, 'price': '11.12', 'unit': 'hour', 'contract_id': 'ct-cZspIALC'}], 'ret_code': 0, 'total_count': 2, 'total_sum': '44.9155', 'trace_id': 'igPsTjr2', 'action': 'GetChargeRecordsResponse'}
        return {'charge_record_set': [], 'ret_code': 0, 'total_count': 0, 'total_sum': '0', 'action': 'GetChargeRecordsResponse'}

    def check_balance(self, *args, **kwargs):
        # return {'action': 'CheckResourcesBalance', 'message': 'NotEnoughMoney, The need to total cost [33.36], coupons deduction:[0],
        # [33.36] need cash, your available balance [-1196.3891], not enough to support the operation, please recharge'}
        return {'action': 'CheckResourcesBalanceResponse', 'ret_code': 0}


class MockProduct(AbsProductInterface):

    def get_model_category(self) -> list:
        return []

    def charge(self, model_category, charge_data_list: list[ChargeDTO], start_time: str, end_time: str = None):
        ...

    def get_prd_list(self):
        return []


mock_user = MockUser()
mock_billing = MockBilling()
mock_product = MockProduct()
mock_push = MockPush()
