# -*- coding: utf-8 -*-

import os
from time import sleep

import pydash

from src.apps.metrics.curd import metrics_curd
from src.apps.metrics.schema import ApiInvokeInfoBuilder, BaseApiInvokeInfo
from src.common.const.comm_const import API_INVOKE_EVENT_QUEUE, API_CONSUME_GROUP, API_ERROR_EVENT_QUEUE
from src.common.loggers import logger
from src.global_server_job import global_task
from src.setting import settings
from src.system.integrations.cache.redis_client import redis_client
from src.system.integrations.logging.opensearch_client import opensearch_client


@global_task('api 调用事件消费', async_exec=True)
def consume_api_event():
    consumer_name = os.getenv('HOSTNAME') or 'DEFAULT_CONSUMER'
    redis_client.init_consume_group(API_INVOKE_EVENT_QUEUE, API_CONSUME_GROUP)
    while True:
        try:
            messages = redis_client.consume_msg(API_INVOKE_EVENT_QUEUE, API_CONSUME_GROUP, consumer_name)
            if not messages:
                continue
            logger.info(f'队列[{API_INVOKE_EVENT_QUEUE}]消费事件数[{len(messages)}]')
        except Exception as e:
            logger.error(f'从队列[{API_INVOKE_EVENT_QUEUE}]中消费失败：', e)
            sleep(5)
            continue

        success_msg_ids = []
        for msg_id, data in messages:
            try:
                # 往 prometheus 的 metrics 写数据
                api_invoke_info: BaseApiInvokeInfo = ApiInvokeInfoBuilder.build(data)
                metrics_curd.submit_token(api_invoke_info)
                # 往 redis 的待计费写数据
                if settings.BILLING_ENABLE:
                    token_type_mount = api_invoke_info.token_type_mount()
                    for (token_type, mount, _) in token_type_mount:
                        key = f'{api_invoke_info.user_id}:{api_invoke_info.model}:{api_invoke_info.channel_id}:{token_type}'
                        redis_client.zincrby(api_invoke_info.cache_key, key, mount)

                success_msg_ids.append(msg_id)
            except Exception as e:
                logger.exception(f'处理 api 事件[{msg_id}][{data}]失败：')

        try:
            # 往 opensearch 写数据
            opensearch_client.submit_api_log([msg for _, msg in messages])
        except Exception:
            logger.exception(f'写流水日志到 opensearch 失败:')

        try:
            if success_msg_ids:
                logger.info(f'成功消费消息:{success_msg_ids}')
                redis_client.ack_msg(API_INVOKE_EVENT_QUEUE, API_CONSUME_GROUP, success_msg_ids)
        except Exception as e:
            logger.error(f'确认消息[{success_msg_ids}]失败：', e)
        sleep(2)


@global_task('api 调用异常事件消费', async_exec=True)
def consume_api_error_event():
    consumer_name = os.getenv('HOSTNAME') or 'DEFAULT_CONSUMER'
    redis_client.init_consume_group(API_ERROR_EVENT_QUEUE, API_CONSUME_GROUP)
    while True:
        try:
            messages = redis_client.consume_msg(API_ERROR_EVENT_QUEUE, API_CONSUME_GROUP, consumer_name)
            if not messages:
                continue
            logger.info(f'队列[{API_ERROR_EVENT_QUEUE}]消费事件数[{len(messages)}]')
            for msg_id, data in messages:
                labels = pydash.pick(data, ['model', 'channel_id', 'user_id', 'api_key', 'err', 'stream'])
                metrics_curd.submit_api_error(labels)
            redis_client.ack_msg(API_ERROR_EVENT_QUEUE, API_CONSUME_GROUP, [msg_id for msg_id, _ in messages])
        except Exception as e:
            logger.error(f'从队列[{API_INVOKE_EVENT_QUEUE}]中消费失败：', e)
        sleep(2)