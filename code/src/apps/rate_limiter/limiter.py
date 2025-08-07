# encoding: utf-8
import time
from typing import List

from src.apps.rate_limiter.curd import RateCURD, RateLimitCURD
from src.apps.rate_limiter.schema import DEFAULT_MODEL_NAME, RateLimit
from src.apps.rate_limiter.utils import get_rmp_limit_buckets_key, get_rpm_limit_key_by_level_and_model, get_rpm_limit_scan_prefix, \
    get_tpm_limit_buckets_key, \
    get_tpm_limit_key_by_level_and_model, get_tpm_limit_scan_prefix
from src.common.loggers import logger
from src.setting import settings
from src.system.integrations.cache.redis_client import redis_client

RPM_LUA_SCRIPT = """
    local window_start_time = ARGV[1] - (ARGV[3] * 1000)
    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', window_start_time)
    local now_request = redis.call('ZCARD', KEYS[1])
    if now_request < tonumber(ARGV[2]) then
        redis.call('ZADD', KEYS[1], ARGV[1], ARGV[1])
        redis.call('EXPIRE', KEYS[1], '3600')
        return 1
    else
        return 0
    end
"""


class Limiter:
    """
    限流器
    RPM / TPM

    """

    def __init__(self):
        self.redis = redis_client
        self.window_size = 60  # unit: second
        self.window_size_ms = self.window_size * 1000

    async def refresh_all_limit(self):
        lock = self.redis.conn.lock("refresh_all_limit_lock", timeout=300)
        if lock.acquire(blocking=False):
            logger.info("refresh all models limit")
            try:
                limits_in_pg: List[RateLimit] = await RateLimitCURD().get_all()
                rpm_limits_in_redis = [x for x in self.redis.scan_iter(get_rpm_limit_scan_prefix(), count=1000, _type="STRING")]
                tpm_limits_in_redis = [x for x in self.redis.scan_iter(get_tpm_limit_scan_prefix(), count=1000, _type="STRING")]
                limits_kv = {
                    **{f"imaas:{get_rpm_limit_key_by_level_and_model(limit.level, limit.model_name)}": limit.rpm for limit in limits_in_pg},
                    **{f"imaas:{get_tpm_limit_key_by_level_and_model(limit.level, limit.model_name)}": limit.tpm for limit in limits_in_pg}
                }

                remove_keys = []
                pipeline = self.redis.conn.pipeline()
                for limit in rpm_limits_in_redis + tpm_limits_in_redis:
                    if limit not in limits_kv.keys():
                        remove_keys.append(limit[12:])
                        pipeline.delete(limit)

                refresh_keys = []
                for limit_key, limit_value in limits_kv.items():
                    refresh_keys.append(limit_key[12:])
                    pipeline.set(limit_key, limit_value)

                pipeline.execute()
                logger.info(f"refresh all models limit done, remove {refresh_keys}, refresh {refresh_keys}")
            except Exception as e:
                logger.error(f"refresh all models limit: {e}")
            finally:
                lock.release()
        else:
            return

    async def get_rpm_limit(self, user_id, model_name) -> int:
        """
        获取用户请求限流
        """
        rate_curd = RateCURD()
        user_level = await rate_curd.get_user_level(user_id)
        # search model limit of level
        if (limit := self.redis.get(get_rpm_limit_key_by_level_and_model(user_level, model_name))) is not None:
            return int(limit)
        # search default limit of level
        if (limit := self.redis.get(get_rpm_limit_key_by_level_and_model(user_level, DEFAULT_MODEL_NAME))) is not None:
            return int(limit)

        # if not model match, search user limit in pg
        if (user_limit := await rate_curd.get_level_model_limit(user_level, model_name)) is not None:
            await self.update_rpm_limit(user_level, user_limit.model_name, user_limit.rpm)
            return user_limit.rpm

        logger.warning("No model limit match")
        # not limit
        return settings.default_rpm

    async def check_rmp_limit(self, user_id, model_name) -> bool:
        """
        检查用户请求限流
        """
        limit = await self.get_rpm_limit(user_id, model_name)
        if limit == -1:
            return True

        rmp_limit_buckets_key = f"imaas:{get_rmp_limit_buckets_key(user_id, model_name)}"

        result = self.redis.conn.eval(
            RPM_LUA_SCRIPT, 1, rmp_limit_buckets_key, str(int(time.time() * 1000)), str(limit), str(self.window_size))
        return result == 1

    async def update_rpm_limit(self, user_level, model_name, limit: int):
        """
        更新用户请求限流
        """
        self.redis.set(get_rpm_limit_key_by_level_and_model(user_level, model_name), limit, ex=None)

    async def get_tpm_limit(self, user_id, model_name) -> int:
        """
        获取用户token限流
        """
        rate_curd = RateCURD()
        user_level = await rate_curd.get_user_level(user_id)
        if (limit := self.redis.get(get_tpm_limit_key_by_level_and_model(user_level, model_name))) is not None:
            return limit

        if (limit := self.redis.get(get_tpm_limit_key_by_level_and_model(user_level, DEFAULT_MODEL_NAME))) is not None:
            return limit

        user_limit = await RateCURD().get_level_model_limit(user_level, model_name)
        if user_limit is not None:
            await self.update_tpm_limit(user_level, user_limit.model_name, user_limit.tpm)
            return user_limit.tpm

        logger.warning("No model limit match")
        # not limit
        return settings.default_tpm

    async def set_token_usage(self, user_id, model_name, token_usage: int):
        """
        设置用户token使用量
        """
        key = get_tpm_limit_buckets_key(user_id, model_name)
        self.redis.zincrby(key, int(time.time() * 1000), token_usage)
        self.redis.expire(key, 3600)

    async def check_tpm_limit(self, user_id, model_name) -> bool:
        """
        检查用户token限流
        """
        limit = await self.get_tpm_limit(user_id, model_name)
        if limit == -1:
            return True

        tpm_limit_buckets_key = get_tpm_limit_buckets_key(user_id, model_name)

        # token cal and expire in 60s
        current_time_ms = int(time.time() * 1000)
        total_token_usage = 0
        cursor = 0
        cursor, data = self.redis.zscan(tpm_limit_buckets_key, cursor=cursor)

        for member, score in data:
            timestamp = int(member)  # 解析时间戳

            # 删除过期的记录
            if timestamp < current_time_ms - self.window_size_ms:
                self.redis.zrem(tpm_limit_buckets_key, member)  # 删除过期的数据
            else:
                total_token_usage += float(score)  # 累加未过期的 Token 使用量

        return int(total_token_usage) < int(limit)

    async def update_tpm_limit(self, level, model_name, limit: int):
        """
        更新用户token限流
        """
        self.redis.set(get_tpm_limit_key_by_level_and_model(level, model_name), limit, ex=None)

    async def check_rpm_and_tpm_limit(self, user_id, model_name) -> bool:
        """
        检查用户请求限流和token限流
        """
        try:
            logger.debug(f"check_rpm_and_tpm_limit for user_id: {user_id}, model_name: {model_name}")
            return await self.check_rmp_limit(user_id, model_name) and await self.check_tpm_limit(user_id, model_name)
        except Exception as e:
            logger.exception(f"check_rpm_and_tpm_limit error: {e}")
            return True


limiter = Limiter()
