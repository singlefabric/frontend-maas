# -*- coding: utf-8 -*-
from sqlmodel import SQLModel, Field
from pydantic import BaseModel
from src.apps.gateway.req_schema import FilePurpose
from datetime import datetime


# 模型相关
class ModelInfo(SQLModel):
    id: str
    object: str = 'model'
    owned_by: str = 'coreshub'
    permission: list = []


class ModelsRsp(SQLModel):
    object: str = 'list'
    data: list[ModelInfo] = []


# 文件相关
class Files(SQLModel, table=True):
    __tablename__ = "files"
    id: str = Field(primary_key=True)
    filename: str
    purpose: str
    bytes: int
    creator_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="active")

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "filename": self.filename,
            "purpose": self.purpose,
            "bytes": self.bytes,
            "creator_id": self.creator_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status
        }


class FileInfo(BaseModel):
    id: str
    object: str = "file"
    bytes: int
    created_at: int
    filename: str
    purpose: FilePurpose


class FileListResponse(BaseModel):
    data: list[FileInfo]
    object: str = "list"
