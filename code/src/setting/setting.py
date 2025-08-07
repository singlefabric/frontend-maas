# -*- coding: utf-8 -*-
from typing import Union

from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    # app
    PROJECT_NAME: str = "maas-model-server"
    DESCRIPTION: str = "inference service api proxy"
    API_PREFIX = "/imaas"

    # sys
    ERR_LANG: str = "zh"
    BILLING_ENABLE: bool = True
    LOGGING_LEVEL: str = "INFO"

    # Database
    DB_CONNECTION_STR: str = ""
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False

    # Redis
    REDIS_HOST: str = "redis.pitrix.svc"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_PREFIX: str = "imaas:"

    # redis 过期时间(秒)
    EXP_TIME_BAL_ENOUGH = 480

    # 其他
    API_EVENT_QUEUE_MAX_LEN = 1000
    SERVER_EVENT_QUEUE_MAX_LEN = 100
    BILLING_TASK_INTERVAL = 600
    HEALTH_CHECK_INTERVAL = 5
    HEALTH_CHANGE_THRESHOLD = 2
    THINK_MODELS = "DeepSeek-R1.*,QwQ-32B,Qwen3.*"
    PROXY_SERVER_HOST = ""

    # qingcloud
    QINGCLOUD_ACCESS_KEY_ID: str = ""
    QINGCLOUD_SECRET_ACCESS_KEY: str = ""
    QINGCLOUD_ZONE: str = ""
    QINGCLOUD_HOST: str = ""
    QINGCLOUD_PORT: int = 443
    QINGCLOUD_PROTOCOL: str = ""
    QINGCLOUD_CONSOLE_ID: str = ""
    QINGCLOUD_REGION: str = ""

    # opensearch
    OPENSEARCH_ENABLE: bool = True
    OPENSEARCH_HOST: str = "https://opensearch-cluster-master.kubesphere-logging-system.svc:9200"
    OPENSEARCH_USER: str = "admin"
    OPENSEARCH_PASSWORD: str = "admin"
    API_LOG_EXPIRE_DAYS: int = 7
    API_LOG_SHARDS: int = 3
    API_LOG_REPLICAS: int = 0
    BILLING_LOG_REPLICAS: int = 2

    # prometheus
    PROMETHEUS_HOST = "prometheus-k8s.kubesphere-monitoring-system:9090"
    METRICS_SCRAPE_INTERVAL = 10

    ACCOUNT_MAPPING: Union[str, dict] = {}

    mock_user_id: str = ""

    default_rpm: int = 1000
    default_tpm: int = 10000

    # 文件上传
    MAX_SINGLE_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    MAX_FILE_COUNTS = 50  # 50个文件
    MAX_TOTAL_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
    # 文件保存目录
    USER_FILE_DIR = "/file_set"
    # 文件清理配置
    FILE_RETENTION_DAYS = 30  # 文件保留天数
    FILE_CLEANUP_CRON = '0 0 * * *'  # 文件清理任务，每天凌晨0点0分0秒执行一次

    @validator('ACCOUNT_MAPPING', pre=True)
    def parse_dict(cls, value):
        mapping_dict = {}
        if value:
            for item in value.split(','):
                map_arr = item.split(':')
                if len(map_arr) == 2:
                    mapping_dict[map_arr[0]] = map_arr[1]
        return mapping_dict

    # CUSTOM_PROD=('[{"model": "Qwen2-7B-Instruct", "model_category": "qwen", "token_type": "input", "price": 0.8, "unit": "token", "model_description": "无计费"},'
    #              '{"model": "Qwen2-7B-Instruct", "model_category": "qwen", "token_type": "output", "price": 1.2, "unit": "token", "model_description": "无计费"},'
    #              '{"model": "CosyVoice-300M", "model_category": "qwen", "token_type": "output", "price": 0.007, "unit": "seconds", "model_description": "无计费"},'
    #              '{"model": "SenseVoiceSmall", "model_category": "qwen", "token_type": "output", "price": 0.0003, "unit": "words", "model_description": "无计费"}]')
    CUSTOM_PROD: str = ''
