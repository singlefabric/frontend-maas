# -*- coding: utf-8 -*-

import os

from src.system.interface.abs_billing_interface import AbsBillingInterface
from src.system.interface.abs_product_interface import AbsProductInterface
from src.system.interface.abs_push_interface import AbsPushInterface
from src.system.interface.abs_user_interface import AbsUserInterface


class PlatInterface:
    user_interface: AbsUserInterface
    billing_interface: AbsBillingInterface
    product_interface: AbsProductInterface
    push_interface: AbsPushInterface


PI = PlatInterface()

interface_plat = os.getenv("INTERFACE_PLAT", "qingcloud")

if interface_plat == 'qingcloud':
    from src.system.interface.qingcloud import qingcloud_user, qingcloud_product
    PI.user_interface = qingcloud_user
    PI.product_interface = qingcloud_product

    # 如果不开启计费，则跳过计费相关逻辑
    from src.setting import settings
    if settings.BILLING_ENABLE:
        from src.system.interface.qingcloud import qingcloud_billing
        PI.billing_interface = qingcloud_billing
    else:
        from src.system.interface.mock.mock import mock_billing
        PI.billing_interface = mock_billing

elif interface_plat == 'mock':
    from src.system.interface.mock.mock import mock_user, mock_billing, mock_product, mock_push
    PI.user_interface = mock_user
    PI.billing_interface = mock_billing
    PI.product_interface = mock_product
    PI.push_interface = mock_push
