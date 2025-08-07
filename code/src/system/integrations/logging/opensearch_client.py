# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta, timezone
from typing import Union, List, Dict, Optional

from cachetools import TTLCache
from opensearchpy import OpenSearch, helpers, OpenSearchException

from src.common.loggers import logger
from src.setting import settings


class OpenSearchClient:

    def __init__(self):
        if settings.OPENSEARCH_ENABLE:
            self.client = self.init_client()
            self.api_log_index_prefix = 'imaas-api-log-'
            self.billing_index_prefix = 'imaas-billing-'
            self.lifecycle_policy_name = 'imaas_lifecycle_policy'
            self.init_template([{
                'name': 'imaas_api_template',
                'body': {
                    'index_patterns': [self.api_log_index_prefix + '*'],
                    'mappings': {
                        'properties': {
                            'trace_id': {'type': 'keyword'},
                            'user_id': {'type': 'keyword'},
                            'channel_id': {'type': 'keyword'},
                            'model': {'type': 'keyword'},
                            'api_key': {'type': 'keyword'},
                            'date_time': {'type': 'date'},
                            'cost_time': {'type': 'float', 'index': False},
                            'model_tag': {'type': 'keyword', 'index': False},

                            'prompt_tokens': {'type': 'integer', 'index': False},
                            'completion_tokens': {'type': 'integer', 'index': False},
                            'cached_tokens': {'type': 'integer', 'index': False},
                            'total_tokens': {'type': 'integer', 'index': False},

                            'speech_length': {'type': 'integer', 'index': False},
                        }
                    }
                }
            }, {
                'name': 'imaas_billing_template',
                'body': {
                    'index_patterns': [self.billing_index_prefix + '*'],
                    'mappings': {
                        'properties': {
                            'trace_id': {'type': 'keyword'},
                            'user_id': {'type': 'keyword'},
                            'token_type': {'type': 'keyword', 'index': False},
                            'unit': {'type': 'keyword', 'index': False},
                            'model': {'type': 'keyword'},
                            'mount': {'type': 'integer', 'index': False},
                            'event_id': {'type': 'keyword'},
                            'charge_msg': {'type': 'keyword', 'index': False},
                            'charge_success': {'type': 'keyword'},
                            'date_time': {'type': 'date'},
                        }
                    }
                }
            }])
            # self.init_lifecycle()
            self.index_exists_cache = TTLCache(maxsize=10000, ttl=24*3600)

    @staticmethod
    def init_client():
        return OpenSearch(
            hosts=[settings.OPENSEARCH_HOST],
            http_auth=(settings.OPENSEARCH_USER, settings.OPENSEARCH_PASSWORD),
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False)

    def init_template(self, templates: list[dict[str, any]]):
        """
        初始化索引模板，服务启动时检查一次
        """
        for template in templates:
            name = template.get('name')
            if not self.client.indices.exists_template(name):
                logger.info(f'初始化 opensearch 索引模板[{name}]')
                self.client.indices.put_template(name, template.get('body'))

    def init_lifecycle(self):
        """
        初始化索引生命周期策略
        """
        try:
            self.client.http.put('/_ilm/policy/' + self.lifecycle_policy_name, body={
                "policy": {
                    "phases": {
                        "delete": {
                            "min_age": f'{settings.API_LOG_EXPIRE_DAYS}d',
                            "actions": {"delete": {}}
                        }
                    }
                }
            })
            logger.error('初始化 lifecycle policy 成功')
        except Exception as e:
            logger.error('初始化 lifecycle policy 失败:', e)

    def init_index(self, index_name, date_field, shards=1, replicas=0):
        """
        初始化索引，防止调用过于频繁，已经初始化的索引名缓存
        """
        if index_name in self.index_exists_cache:
            return
        if self.client.indices.exists(index_name):
            self.index_exists_cache[index_name] = True
            return
        self.client.indices.create(index=index_name, body={
            'settings': {
                'number_of_shards': shards,
                'number_of_replicas': replicas,
                # 'index.lifecycle.name': self.lifecycle_policy_name,
            },
            'mappings': {
                'properties': {
                    date_field: {
                        'type': 'date',
                        'format': 'strict_date_optional_time||epoch_millis',
                    }
                }
            }
        })
        logger.info(f'创建索引[{index_name}]')
        self.index_exists_cache[index_name] = True

    def submit_api_log(self, api_logs: list[dict]):
        """
        日志写入索引（批量）
        """
        if not api_logs or not settings.OPENSEARCH_ENABLE:
            return
        today = datetime.now().strftime('%Y%m%d')
        docs = []
        for api_log in api_logs:
            index = f'{self.api_log_index_prefix}{today}'
            docs.append({'_index': index, '_id': api_log['trace_id'], '_source': api_log})
            self.init_index(index, 'date_time', settings.API_LOG_SHARDS, settings.API_LOG_REPLICAS)
        helpers.bulk(self.client, docs)
        logger.info(f'写入 api 调用索引日志[{len(api_logs)}]条')

    def submit_billing_log(self, billing_logs: list[dict]):
        """
        计费日志写入索引
        """
        if not billing_logs or not settings.OPENSEARCH_ENABLE:
            return
        today = datetime.now().strftime('%Y%m%d')
        docs = []
        for billing_log in billing_logs:
            index = f'{self.billing_index_prefix}{today}'
            docs.append({'_index': index, '_id': billing_log['event_id'], '_source': billing_log})
            self.init_index(index, 'date_time', settings.API_LOG_SHARDS, settings.BILLING_LOG_REPLICAS)
        helpers.bulk(self.client, docs)
        logger.info(f'写入计费索引日志[{len(billing_logs)}]条')

    def query_metrics(
            self,
            index_prefix: str,
            start_time: Union[datetime, str],
            end_time: Union[datetime, str],
            metrics: List[Dict[str, str]],
            group_by: List[str] = None,
            model_list: List[str] = None,
            user_id_list: List[str] = None,
            time_zone: str = "+08:00"
    ) -> Optional[Dict]:
        """查询并聚合 OpenSearch 数据"""
        if not self.client:
            logger.warning("OpenSearch 客户端未初始化")
            return None
        # 生成索引列表
        indices = self._get_indices_in_range(index_prefix, start_time, end_time)
        # 构建查询 DSL
        query = self._build_aggregation_query(
            start_time=start_time,
            end_time=end_time,
            metrics=metrics,
            group_by=group_by,
            time_zone=time_zone,
            model_list=model_list,
            user_id_list=user_id_list,
        )
        try:
            response = self.client.search(
                index=indices,
                body=query,
                size=0  # 不返回原始文档
            )
            logger.debug(f"原始响应:\n{json.dumps(response, indent=2)}")
            return self._parse_aggregation_response(response, metrics, group_by)
        except OpenSearchException as e:
            logger.error(f"查询失败: {str(e)}")
            return None

    def _get_indices_in_range(self, prefix: str, start: datetime, end: datetime) -> List[str]:
        """生成符合时间范围的索引列表"""
        # 统一转换为 UTC 时区的 datetime 对象
        def to_utc(dt: Union[datetime, str]) -> datetime:
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        # 转换输入时间为 UTC
        utc_start = to_utc(start)
        utc_end = to_utc(end)

        # 标准化到日期边界（UTC）
        current_day = utc_start.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_day = utc_end.replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        indices = []
        while current_day <= end_day:
            indices.append(f"{prefix}{current_day.strftime('%Y%m%d')}")
            current_day += timedelta(days=1)
        # 批量检查索引存在性
        existing_indices = [index for index in indices if self.client.indices.exists(index=index)]
        if not existing_indices:
            logger.debug(f"无可用索引: {indices}")
        return existing_indices

    def _build_aggregation_query(
            self,
            start_time: Union[datetime, str],
            end_time: Union[datetime, str],
            metrics: List[Dict[str, str]],
            group_by: List[str],
            time_zone: str,
            model_list: List[str] = None,
            user_id_list: List[str] = None
    ) -> Dict:
        """构建聚合查询 DSL"""
        time_filter = {
            "range": {
                "date_time": {
                    "gte": start_time.isoformat() if isinstance(start_time, datetime) else start_time,
                    "lte": end_time.isoformat() if isinstance(end_time, datetime) else end_time,
                    "time_zone": time_zone
                }
            }
        }
        # 构建查询条件
        query_filters = [time_filter]
        # 添加 model 过滤条件
        if model_list and len(model_list) > 0:
            model_filter = {
                "terms": {
                    "model": model_list  # model 字段的过滤条件
                }
            }
            query_filters.append(model_filter)
            # 添加 user_id 过滤条件
        if user_id_list and len(user_id_list) > 0:
            user_id_filter = {
                "terms": {
                    "user_id": user_id_list  # user_id 字段的过滤条件
                }
            }
            query_filters.append(user_id_filter)
        aggs = {}
        # 字段分组聚合
        if group_by:
            current_agg = aggs
            for i, field in enumerate(group_by):
                current_agg[f"group_{i}"] = {
                    "terms": {
                        "field": f"{field}",
                        "size": 100000
                    },
                    "aggs": {}
                }
                current_agg = current_agg[f"group_{i}"]["aggs"]
        # 指标聚合
        for metric in metrics:
            agg_type = metric["agg"]
            field = metric["field"]
            current_agg[f"{field}_{agg_type}"] = {
                agg_type: {"field": field}
            }
        return {
            "query": {"bool": {"filter": query_filters}},
            "aggs": aggs
        }

    def _parse_aggregation_response(
            self,
            response: Dict,
            metrics: List[Dict[str, str]],
            group_by: List[str],
    ) -> Dict:
        """解析 OpenSearch 聚合响应"""
        def extract_metrics(bucket, metrics):
            """从分桶中提取指标值"""
            result = {}
            for metric in metrics:
                key = f"{metric['field']}_{metric['agg']}"
                result[key] = bucket.get(key, {}).get("value", 0)  # 默认值为 0
            return result

        # if group_by:
        #     # 如果有分组，返回每个分组的指标结果
        #     buckets = response["aggregations"]["group_0"]["buckets"]
        #     grouped_result = {}
        #     for bucket in buckets:
        #         group_key = bucket["key"]  # 分组字段的值（如 model 名称）
        #         grouped_result[group_key] = extract_metrics(bucket, metrics)
        #     return grouped_result
        # else:
        #     # 如果没有分组，直接返回总和
        #     total_result = {}
        #     for metric in metrics:
        #         key = f"{metric['field']}_{metric['agg']}"
        #         total_result[key] = response["aggregations"].get(key, {}).get("value", 0)  # 默认值为 0
        #     return {
        #         "total": total_result
        #     }
            # 无分组时直接返回总和
        if not group_by:
            return {
                "total": extract_metrics(response["aggregations"]["group_0"]["buckets"][0], metrics)
            }

        # 递归解析嵌套分组
        def parse_dynamic_groups(buckets, current_level=0):
            results = {}
            for bucket in buckets:
                current_key = bucket["key"]

                # 判断是否还有下一层分组
                next_level_key = f"group_{current_level + 1}"
                if next_level_key in bucket:
                    # 递归处理下一层
                    nested_results = parse_dynamic_groups(
                        bucket[next_level_key]["buckets"],
                        current_level + 1
                    )
                    # 合并当前层key和嵌套结果
                    # for nested_key, metrics_val in nested_results.items():
                    #     combined_key = f"{current_key}|{nested_key}" if nested_key else current_key
                    #     results[combined_key] = metrics_val
                    results[current_key] = nested_results
                else:
                    # 最底层，直接提取指标
                    results[current_key] = extract_metrics(bucket, metrics)
            return results

        top_level_buckets = response["aggregations"]["group_0"]["buckets"]
        return parse_dynamic_groups(top_level_buckets)

opensearch_client = OpenSearchClient()