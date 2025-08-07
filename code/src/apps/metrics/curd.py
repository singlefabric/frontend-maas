# -*- coding: utf-8 -*-
import datetime

import httpx
import pydash

from prometheus_client import Counter, Gauge
from src.system.integrations.logging.opensearch_client import opensearch_client

from src.apps.base_curd import BaseCURD
from src.apps.metrics.req_schema import ApiMetricsQuery, ApiModelTokenMetricsQuery, ApiUserTokenMetricsQuery
from src.apps.metrics.schema import BaseApiInvokeInfo, ApiInvokeInfoBuilder
from src.common.const.comm_const import UserPlat, MetricsAggrType
from src.common.const.err_const import Err
from src.common.context import Context
from src.common.exceptions import MaaSBaseException
from src.common.loggers import logger
from src.setting import settings
from src.system.interface import qingcloud_user


class MetricsCURD(BaseCURD):
    def __init__(self):
        super().__init__()
        self.token_counter = Counter('token_usage', 'Token Usage For LLM Service',
                                     ['user_id', 'model', 'api_key', 'token_type', 'unit'])
        self.channel_health = Gauge('channel_health', 'Channel Health For LLM Service',
                                    ['channel_id', 'model'])
        self.imaas_api_error = Counter('imaas_api_error', 'IMAAS API Error For LLM Service',
                                       ['model', 'channel_id', 'user_id', 'api_key', 'err', 'stream'])

    @staticmethod
    def find_latest_metric_val(labels: dict[str, str]) -> int:
        """
        防止 counter 类型 metrics 由于服务重启导致 reset，如果内存中没有对应 label 的 metrics，主动到 Prometheus 中查询一次最新数据
        窗口期为30天，即：由于服务重启导致 counter 数据重置，30天之内有相同的 label 数据上报，仍能正常统计。
        """
        expr_arr = [f'{label}="{val}"' for label, val in labels.items()]
        response = httpx.get(f'http://{settings.PROMETHEUS_HOST}/api/v1/query', params={
            'query': f'max(last_over_time(token_usage_total{{{",".join(expr_arr)}}}[30d]))'
        }, timeout=10)
        ret = response.json()
        if ret.get('status') == 'success' and ret.get('data').get('result'):
            timestamp, value = pydash.get(ret, 'data.result.0.value')
            logger.debug(f'指标[token_usage_total]label[{labels}]发生过重置，恢复数据时间[{timestamp}]，数值[{value}]')
            return int(value)
        else:
            return 0

    def submit_token(self, api_invoke_info: BaseApiInvokeInfo):
        """
        提交接口调用消耗 token 数据
        """
        for (token_type, mount, unit) in api_invoke_info.token_type_mount():
            labels = {
                'user_id': api_invoke_info.user_id,
                'model': api_invoke_info.model,
                'api_key': api_invoke_info.api_key,
                'token_type': token_type,
                'unit': unit,
            }
            metrics = self.token_counter.labels(**labels)
            if not metrics._value.get():
                mount += self.find_latest_metric_val(labels)
            metrics.inc(mount)

    def submit_api_error(self, labels):
        self.imaas_api_error.labels(**labels).inc(1)

    def submit_channel_health(self, channel_id: str, model: str, health: int):
        self.channel_health.labels(channel_id=channel_id, model=model).set(health)

    async def query_api_metrics(self, query_params: ApiMetricsQuery):
        """
        查询接口调用消耗量（token、count、seconds 等）
        """
        if Context.USER.get().plat == UserPlat.QC_CONSOLE:
            query_params.user_id = [Context.USER.get().user_id]

        label_arr = []
        group_arr = []
        step = query_params.step
        for field in ['user_id', 'api_key', 'model', 'token_type', 'unit']:
            vals = getattr(query_params, field)
            if vals:
                label_arr.append(f'{field}=~"{"|".join(vals)}"')
                group_arr.append(field)
            elif field == 'token_type' and not vals:
                label_arr.append(f'{field}=~"input|output"')

        # 比率
        bill_rate = 1
        if query_params.unit:
            for meta_info in ApiInvokeInfoBuilder.BillMetaInfo:
                if meta_info.unit.value == query_params.unit[0]:
                    bill_rate = meta_info.rate.value

        if query_params.aggr_type == MetricsAggrType.RANGE:
            query = f"sum(token_usage_total{{{','.join(label_arr)}}}) by ({','.join(group_arr)}) / {bill_rate}"
        else:
            # sum(increase(token_usage_total{api_key=~"sk-uvzESo",token_type=~"input|output"}[4800s]))by(api_key, token_type)
            query = f"sum(increase(token_usage_total{{{','.join(label_arr)}}}[{step}s])) by ({','.join(group_arr)}) / {bill_rate}"

        # 为了判断第一个点是新增还是持续，多查两个周期的数据
        params = {
            "query": query,
            "start": query_params.start_time - step * 2,
            "end": query_params.end_time,
            "step": step,
        }
        async with httpx.AsyncClient() as client:
            response = None
            try:
                response = await client.get(f'http://{settings.PROMETHEUS_HOST}/api/v1/query_range', params=params, timeout=10)
                metrics_data = response.json()

                # sum 类型，只保留最后一条数据
                # range 类型手动计算单位时间的增量，并计算总量
                for metrics in metrics_data.get('data', {}).get('result', []):
                    if query_params.aggr_type == MetricsAggrType.SUM:
                        metrics['value'] = metrics['values'][-1]
                        metrics['value'][-1] = float(metrics['value'][-1])
                    else:
                        # 第一个点的时间大于 start_time，说明这个点是增量
                        [first_time, _val] = metrics['values'][0]
                        _tmp = 0 if first_time > query_params.start_time else float(_val)
                        _sum = 0
                        _delta = 0
                        for value in metrics['values']:
                            # 倒反天罡，说明发生了 reset，需要把后面的所有值都加上 delta
                            cur_val = float(value[1]) + _delta
                            if cur_val < _tmp:
                                _delta += (_tmp - cur_val)
                                cur_val = _tmp
                            inc_val = cur_val - _tmp
                            value[1] = str(inc_val)
                            _tmp = cur_val
                            _sum += inc_val
                        metrics['sum'] = round(_sum, 3)
                return metrics_data
            except Exception:
                logger.exception(f'查询指标[{params}]失败，响应码[{response.status_code if response else ""}]')
                raise MaaSBaseException(Err.SERVER_ERR)


    async def query_model_token_metrics(self, query_params: ApiModelTokenMetricsQuery):
        """
        查询接口调用消耗量（token、count、seconds 等）
        """
        model_list = []
        if query_params.model:
            model_list = query_params.model.split(",")
        result = opensearch_client.query_metrics(
            index_prefix="imaas-api-log-",
            start_time=query_params.start_time,
            end_time=query_params.end_time,
            metrics=[
                {"field": "total_tokens", "agg": "sum"},
                {"field": "prompt_tokens", "agg": "sum"},
                {"field": "completion_tokens", "agg": "sum"},
                {"field":"cached_tokens", "agg": "sum"}
            ],
            model_list=model_list,
            group_by=["model"]
        )
        list_data = [{key: value} for key, value in result.items()]
        sorted_data = sorted(list_data, key=lambda x: list(x.values())[0][query_params.order_by], reverse=bool(query_params.reverse))
        # 重新组织数据
        modified_data = []
        for item in sorted_data:
            for model_name, values in item.items():
                modified_data.append({
                    "model_name": model_name,
                    "total_tokens_sum": values["total_tokens_sum"],
                    "prompt_tokens_sum": values["prompt_tokens_sum"],
                    "completion_tokens_sum": values["completion_tokens_sum"],
                    "cached_tokens_sum": values["cached_tokens_sum"]
                })
        # 输出结果
        page = query_params.page - 1
        start = int(page * query_params.size)
        return modified_data[start:start + int(query_params.size)], len(modified_data)

    async def query_user_token_metrics(self, query_params: ApiUserTokenMetricsQuery):
        """
        查询接口调用消耗量（token、count、seconds 等）
        """
        model_list = []
        user_list = []
        if query_params.model:
            model_list = query_params.model.split(",")
        if query_params.user:
            user_list = query_params.user.split(",")
        result = opensearch_client.query_metrics(
            index_prefix="imaas-api-log-",
            start_time=query_params.start_time,
            end_time=query_params.end_time,
            metrics=[
                {"field": "total_tokens", "agg": "sum"},
            ],
            model_list=model_list,
            user_id_list=user_list,
            group_by=["user_id", "model"]
        )
        list_data = [{key: value} for key, value in result.items()]
        # 重新组织数据
        modified_data = []
        for item in list_data:
            user_info = {}
            for user_id, model_info in item.items():
                user_info["user_id"] = user_id
                user_info["user_name"] = qingcloud_user.get_user_by_id(user_id).user_name
                user_info["total_tokens_sum"] = 0
                user_info["model"] = []
                for model_name, values in model_info.items():
                    user_info["model"].append({
                        "model_name": model_name,
                        "total_tokens_sum": values["total_tokens_sum"],
                    })
                    user_info["total_tokens_sum"] += int(values["total_tokens_sum"])
            modified_data.append(user_info)

        # 输出结果
        page = query_params.page - 1
        start = int(page * query_params.size)
        return modified_data[start:start + int(query_params.size)], len(modified_data)



metrics_curd = MetricsCURD()