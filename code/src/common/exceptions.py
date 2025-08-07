# -*- coding: utf-8 -*-

import re
from src.common.const.err_const import Err
from src.common.context import Context


class MaaSBaseException(Exception):

    def __init__(self, err: Err = Err.SERVER_ERR, *args: object, **kwargs) -> None:
        super().__init__(*args)
        self.err = err
        self.prams = kwargs

    def __str__(self) -> str:
        return f'{self.err.code} {self.prams}'

    def __repr__(self) -> str:
        return f'{self.err.code} {self.prams}'


class GatewayException(Exception):
    """
    网关处理逻辑异常
    """
    def __init__(self, msg: str, code=200):
        self.msg = f'{msg}(request id: {Context.TRACE_ID.get()})'
        self.code = code


class InterfaceException(MaaSBaseException):
    def __init__(self, action: str, message: str, *args: object) -> None:
        err = Err.INTERFACE_FAILED

        # 接口请求失败信息包装
        # NotEnoughMoney, The need to total cost [0.1], coupons deduction:[0], [0.1] need cash, your available
        # balance [0], not enough to support the operation, please recharge
        if action == "CheckResourcesBalance" and "NotEnoughMoney" in message:
            _match = re.match(r".*\[([^,\]]+)] need cash", message)
            if _match:
                err = Err.NOT_ENOUGH_MONEY
                super().__init__(err, *args, **{"need_cash": _match.group(1)})
                return

        super().__init__(err, *args, **{"action": action, "message": message})
