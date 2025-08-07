# -*- coding: utf-8 -*-
import time
from dataclasses import dataclass
from typing import Any, Union

import json
from cachetools import Cache
from cachetools.keys import hashkey

from src.common.const.comm_const import EventAction, ResourceModule, SERVER_EVENT_QUEUE
from src.common.loggers import logger
from src.setting import settings
from src.system.integrations.cache.redis_client import redis_client


@dataclass
class Event:
    action: EventAction
    data: dict

    def __init__(self, action, data: Union[dict, str]):
        self.action = action
        if isinstance(data, str):
            data = json.loads(data)
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        return {'action': self.action.value, 'data': json.dumps(self.data)}


@dataclass
class EventSubscriber:
    action: EventAction

    def on_event(self, event: Event):
        ...


@dataclass
class EvictEventSubscriber(EventSubscriber):
    module: ResourceModule = None
    action: EventAction = EventAction.EVICT_CACHE
    cache: Cache = None

    def on_event(self, event: Event):
        data = event.data
        params = data.get('params', [])
        if not self.cache or not data or data.get('module') != self.module.value:
            return

        key = hashkey(*params)
        if key in self.cache:
            del self.cache[key]
            logger.info(f'[事件] 清理模块[{self.module}]缓存[{params}]')

    def __str__(self):
        return f'action: {self.action.value}, module: {self.module.value}'


class EventManager:

    def __init__(self):
        self.event_subscriber: list[EventSubscriber] = []

    def register(self, event_subscriber: EventSubscriber):
        logger.info(f'[事件] 注册监听模块[{event_subscriber}]')
        self.event_subscriber.append(event_subscriber)

    @staticmethod
    async def emit(event: Event):
        logger.info(f'[事件] 发送[{event}]')
        await redis_client.product_msg(SERVER_EVENT_QUEUE, event.to_dict(), max_len=settings.SERVER_EVENT_QUEUE_MAX_LEN)

    def on_event(self, event: Event):
        logger.info(f'[事件] 收到[{event}]')
        for subscriber in self.event_subscriber:
            if subscriber.action == event.action:
                try:
                    subscriber.on_event(event)
                except Exception:
                    logger.exception(f'[事件] 消费[{event}]失败')

    def consume_event_msg(self):
        stream_name = settings.REDIS_PREFIX + SERVER_EVENT_QUEUE
        latest = redis_client.conn.xrevrange(stream_name, count=1)
        last_id = latest[0][0] if latest else '0'
        logger.info(f'启动监听服务事件线程 [{last_id}]')
        while True:
            messages = redis_client.conn.xread({stream_name: last_id}, 10, 10000)
            if messages:
                for message in messages:
                    _, message_data = message
                    message_id, data = message_data[0]
                    self.on_event(Event(**data))
                    last_id = message_id
            time.sleep(1)


event_manager = EventManager()