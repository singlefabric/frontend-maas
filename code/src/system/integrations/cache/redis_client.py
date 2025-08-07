# -*- coding: utf-8 -*-
from typing import Iterator, Union

import redis
from redis.typing import PatternT

from src.common.loggers import logger
from src.setting import settings


class RedisClient:

    def __init__(self):
        self.prefix = settings.REDIS_PREFIX
        self.conn = redis.StrictRedis(host=settings.REDIS_HOST, password=settings.REDIS_PASSWORD, port=settings.REDIS_PORT, decode_responses=True)

    def set(self, key, value, nx=False, ex=60):
        return self.conn.set(f"{self.prefix}{key}", value, nx=nx, ex=ex)

    def get(self, key):
        return self.conn.get(f"{self.prefix}{key}")

    def delete(self, key):
        return self.conn.delete(f"{self.prefix}{key}")

    def mset(self, data: dict, ex=60):
        if self.conn.mset(data):
            for key in data.keys():
                self.conn.expire(key, ex)

    def mget(self, keys):
        return self.conn.mget(keys)

    def hset(self, name, mappings, ex=60):
        if self.conn.hset(f"{self.prefix}{name}", mapping=mappings):
            self.conn.expire(f"{self.prefix}{name}", ex)

    def hget(self, name, key):
        return self.conn.hget(f"{self.prefix}{name}", key)

    def hget_all(self, name):
        return self.conn.hgetall(f"{self.prefix}{name}")

    def hdel(self, name, key):
        return self.conn.hdel(f"{self.prefix}{name}", key)

    def zincrby(self, name, key, val):
        return self.conn.zincrby(f'{self.prefix}{name}', val, key)

    def expire(self, key, ex):
        return self.conn.expire(f"{self.prefix}{key}", ex)

    async def product_msg(self, queue: str, data: dict, max_len=settings.API_EVENT_QUEUE_MAX_LEN):
        """
        生产数据推送到队列中
        """
        queue = f'{self.prefix}{queue}'
        return self.conn.xadd(queue, data, maxlen=max_len)

    def init_consume_group(self, queue, group_name):
        """
        初始化消费者组，如果已经存在则跳过
        """
        queue = f'{self.prefix}{queue}'
        try:
            self.conn.xgroup_create(queue, group_name, id='0', mkstream=True)
        except redis.exceptions.ResponseError as e:
            if not 'BUSYGROUP Consumer Group name already exists' in str(e):
                logger.error(f'创建消费者组[{group_name}]失败', e)
                raise e

    def consume_msg(self, queue, group_name=None, consumer_name=None, count=100, block=10000):
        """
        消费数据
        """
        queue = f'{self.prefix}{queue}'
        message = self.conn.xreadgroup(group_name, consumer_name, {queue: '>'}, count=count, block=block)
        # pending 数据的处理后面再考虑
        return message[0][1] if message else []

    def ack_msg(self, queue, group_name, message_ids, need_del=True):
        """
        ack 消息并删除
        """
        queue = f'{self.prefix}{queue}'
        self.conn.xack(queue, group_name, *message_ids)
        if need_del:
            self.conn.xdel(queue, *message_ids)

    def scan(self, prefix: str, count=None, _type: Union[str, None] = None, ):
        return self.conn.scan(match=f"{self.prefix}{prefix}", count=count, _type=_type)

    def scan_iter(
            self, prefix: str, count=None, _type: Union[str, None] = None, **kwargs,
    ) -> Iterator:
        yield from self.conn.scan_iter(match=f"{self.prefix}{prefix}", count=count, _type=_type, **kwargs)

    def zadd(self, name, mapping, **kwargs):
        return self.conn.zadd(f"{self.prefix}{name}", mapping, **kwargs)

    def zscan(self, name, cursor=0, match=None, count=None):
        return self.conn.zscan(f"{self.prefix}{name}", cursor, match, count)

    def zrem(self, name, *values):
        return self.conn.zrem(f"{self.prefix}{name}", *values)


redis_client = RedisClient()
