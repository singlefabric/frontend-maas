# -*- coding: utf-8 -*-
from typing import Optional

import pydash
from sqlalchemy import delete
from sqlmodel import select

from src.apps.base_curd import BaseCURD
from src.apps.rate_limiter.schema import DEFAULT_MODEL_NAME, Level, LevelBase, RateLimit, RateLimitBase, RateLimitDeleteParam, UserLevel, \
    UserLevelBase, \
    UserModelRateLimit, \
    UserRateLimits
from src.apps.rate_limiter.utils import get_rpm_limit_key_by_level_and_model, get_tpm_limit_key_by_level_and_model, get_user_level_key
from src.system.db.sync_db import session_manage
from src.system.integrations.cache.redis_client import redis_client


class UserLevelCURD(BaseCURD[UserLevel]):

    @session_manage()
    async def put_item(self, item: UserLevelBase):
        stmt = select(UserLevel).where(UserLevel.user_id == item.user_id)
        user_level = self.session.exec(stmt).one_or_none()
        if user_level:
            user_level.sqlmodel_update(item)
        else:
            user_level = UserLevel(**item.dict())
            self.session.add(user_level)
        self.session.commit()
        self.session.refresh(user_level)
        # refresh user level
        redis_client.set(get_user_level_key(item.user_id), item.level, ex=3600)
        return user_level

class LevelCURD(BaseCURD[Level]):
    @session_manage()
    async def put_item(self, item: LevelBase) -> Level:
        stmt = select(Level).where(Level.level == item.level)
        level = self.session.exec(stmt).one_or_none()
        if level:
            level.sqlmodel_update(item)
        else:
            level = Level(**item.dict())
            self.session.add(level)
        self.session.commit()
        self.session.refresh(level)

        return level

    @session_manage()
    async def delete_item(self, level: int):
        # delete table where level = 'level';
        stmt = delete(Level).where(Level.level == level)
        self.session.exec(stmt)
        self.session.commit()


class RateLimitCURD(BaseCURD[RateLimit]):
    def list_page(self, queryDTO):
        pass

    @session_manage()
    async def put_item(self, item: RateLimitBase) -> RateLimit:
        stmt = select(RateLimit).where(RateLimit.model_id == item.model_id, RateLimit.level == item.level)
        rate_limit = self.session.exec(stmt).one_or_none()
        if rate_limit:
            rate_limit.sqlmodel_update(item)
        else:
            rate_limit = RateLimit(**item.dict())
            self.session.add(rate_limit)
        self.session.commit()
        self.session.refresh(rate_limit)

        # refresh limit info
        redis_client.set(get_rpm_limit_key_by_level_and_model(item.level, item.model_name), item.rpm, ex=None)
        redis_client.set(get_tpm_limit_key_by_level_and_model(item.level, item.model_name), item.tpm, ex=None)

        return rate_limit

    @session_manage()
    async def get_model_limit(self, model_id: int) -> list[RateLimitBase]:
        rate_limits = await self.get_by_filter([{"column_name": "model_id", "operator": "is_in", "value": [model_id, 'rate-default']}])
        level_group = pydash.group_by(rate_limits, 'level')
        ret_list = []
        for level, items in level_group.items():
            if len(items) > 1:
                ret_list.append(pydash.find(items, lambda item: item.model_id == model_id))
            else:
                ret_list.append(items[0])
        return pydash.sort_by(ret_list, 'level')

    @session_manage()
    async def delete_item(self, param: RateLimitDeleteParam):
        """
        删除模型的限流信息, 根据 model_id + level 进行删除
        """
        stmt = select(RateLimit).where(RateLimit.model_id == param.model_id, RateLimit.level == param.level)
        rate_limit = self.session.exec(stmt).one_or_none()
        if rate_limit is None:
            return
        stmt = delete(RateLimit).where(RateLimit.model_id == rate_limit.model_id, RateLimit.level == rate_limit.level)
        self.session.exec(stmt)
        self.session.commit()
        # clear cache
        redis_client.delete(get_rpm_limit_key_by_level_and_model(rate_limit.level, rate_limit.model_name))
        redis_client.delete(get_tpm_limit_key_by_level_and_model(rate_limit.level, rate_limit.model_name))


class RateCURD(BaseCURD):

    @session_manage()
    async def get_user_level(self, user_id) -> int:
        user_level_key = get_user_level_key(user_id)
        if (user_level := redis_client.get(user_level_key)) is not None:
            redis_client.expire(user_level_key, ex=3600)
            return int(user_level)

        user_stmt = select(UserLevel).where(UserLevel.user_id == user_id)
        user = self.session.exec(user_stmt).one_or_none()

        if user is None:
            user = UserLevel(user_id=user_id, level=0)
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
        redis_client.set(user_level_key, user.level, ex=3600)
        return user.level

    @session_manage()
    async def get_level_model_limit(self, level: int, model_name: str) -> Optional[RateLimitBase]:
        """
        获取用户限流信息
        :return:
        """
        limit_stmt = select(RateLimit).where(RateLimit.model_name == model_name, RateLimit.level == level)
        limit: RateLimit = self.session.exec(limit_stmt).one_or_none()
        if limit is not None:
            return limit

        default_limit_stmt = select(RateLimit).where(RateLimit.model_name == DEFAULT_MODEL_NAME, RateLimit.level == level)
        default_limit = self.session.exec(default_limit_stmt).one_or_none()
        if default_limit is not None:
            return default_limit

        return None
