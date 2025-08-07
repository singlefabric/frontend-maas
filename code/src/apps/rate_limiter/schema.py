# -*- coding: utf-8 -*-
import enum

from sqlmodel import Field, SQLModel

from src.models.base import TimestampModel

DEFAULT_MODEL_NAME = "Default"


class UpgradePolicy(str, enum.Enum):
    MANUAL = "manual"
    AUTO = "auto"


class UserLevelBase(SQLModel, table=False):
    user_id: str = Field(primary_key=True)
    level: int = Field(0, description="用户等级")
    upgrade_policy: UpgradePolicy = Field(UpgradePolicy.AUTO, description="升级策略, 默认自动升级, 针对大客户可以手动更新等级")


class UserLevel(UserLevelBase, TimestampModel, table=True):
    __tablename__ = "user_level"


class LevelBase(SQLModel, table=False):
    level: int = Field(primary_key=True)
    description: str = Field(..., description="等级描述")


class Level(LevelBase, TimestampModel, table=True):
    __tablename__ = "level"


class RateLimitBase(SQLModel, table=False):
    level: int = Field(..., description="用户等级")
    model_name: str = Field(..., description="模型name")
    model_id: str = Field(..., description="模型ID")
    rpm: int = Field(..., description="每分钟请求数")
    tpm: int = Field(..., description="每分钟token数")

class RateLimitDeleteParam(SQLModel, table=False):
    level: int = Field(..., description="用户等级")
    model_id: str = Field(..., description="模型ID")


class RateLimit(RateLimitBase, TimestampModel, table=True):
    __tablename__ = "rate_limit"
    id: int = Field(primary_key=True)


class UserModelRateLimit(UserLevelBase, RateLimitBase, table=False):
    pass


class UserRateLimits(UserLevelBase, table=False):
    limits: list[RateLimitBase] = Field(default=[])
