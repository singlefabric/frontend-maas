# -*- coding: utf-8 -*-

from qingcloud.iaas import APIConnection

from src.common.exceptions import InterfaceException
from src.common.loggers import logger
from src.setting import settings as conf


class IaasClient:

    def __init__(self) -> None:
        self.iaas_client = APIConnection(conf.QINGCLOUD_ACCESS_KEY_ID,
                                         conf.QINGCLOUD_SECRET_ACCESS_KEY,
                                         conf.QINGCLOUD_ZONE,
                                         host=conf.QINGCLOUD_HOST,
                                         port=conf.QINGCLOUD_PORT,
                                         protocol=conf.QINGCLOUD_PROTOCOL)

    def send_request(self, action, req, url='/iaas/', verb='GET', strict=True):
        rsp = self.iaas_client.send_request(action, req, url=url, verb=verb)
        logger.debug("[qingcloud] action[%s] req[%s] url[%s] verb[%s] ret[%s]" % (action, req, url, verb, rsp))
        if rsp['ret_code'] != 0:
            logger.warning("[qingcloud] request failed [%s]: [%s]" % (action, rsp))
            if strict:
                raise InterfaceException(action, rsp.get("message"))
        return rsp


iaas_client = IaasClient()

