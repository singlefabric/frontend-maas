# -*- coding: utf-8 -*-
import os
import threading
import time

from src.common.loggers import logger
from src.system.integrations.cache.redis_client import redis_client


class DLock:
    """
    基于 redis 的分布式锁，能够自动续约
    """
    def __init__(self, lock_key, expire_time, value=None):
        self.lock_key = lock_key
        # 过期时间(秒)
        self.expire_time = expire_time
        self.is_locked = False
        # value 默认使用 pod id + 进程号
        self.value = value or (os.getenv('HOSTNAME') or '' + '-' + str(os.getpid()))

    def acquire(self):
        # 重入锁
        if redis_client.get(self.lock_key) == self.value:
            return True
        if not redis_client.set(self.lock_key, self.value, nx=True, ex=self.expire_time):
            return False
        threading.Thread(target=self._renew_lock, daemon=True).start()
        logger.info(f'获取[{self.lock_key}]锁成功')
        self.is_locked = True
        return True

    def release(self):
        lock_val = redis_client.get(self.lock_key)
        if lock_val == self.value:
            redis_client.delete(self.lock_key)
            logger.info(f'释放锁[{self.lock_key}]成功')
        else:
            logger.warning(f'非当前进程[{self.value}]占用的锁:[{lock_val}]')
        self.is_locked = False

    def _renew_lock(self):
        while self.is_locked:
            time.sleep(self.expire_time // 3)
            if redis_client.get(self.lock_key) == self.value:
                redis_client.expire(self.lock_key, self.expire_time)
                logger.info(f"续约[{self.lock_key}]锁")
            else:
                logger.warning(f'锁[{self.lock_key}]过期或被抢占，自动释放')
                self.is_locked = False
