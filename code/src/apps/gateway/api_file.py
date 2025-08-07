from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter
from starlette.requests import Request

from src.apps.apikey.rsp_schema import ApiKey
from src.apps.gateway.curd import gateway_file_curd, validate_auth
from src.apps.gateway.req_schema import FilePurpose
from src.apps.gateway.rsp_schema import FileInfo, FileListResponse
from src.common.const.comm_const import FileStatus
from src.common.exceptions import GatewayException
from src.setting import settings

api_router = APIRouter(prefix="/v1", tags=["文件管理接口"])


@api_router.post("/files")
async def upload_file(
        request: Request,
):
    """
    上传文件接口 - 流式处理上传文件
    """
    api_key_data: ApiKey = await validate_auth('', request=request, check_billing=False, check_limit=False)
    # 处理文件上传
    return await gateway_file_curd.process_upload_stream(request, api_key_data)


@api_router.get("/files")
async def list_files(
        request: Request,
        after: Optional[str] = None,
        limit: int = 10,
        order: Optional[Literal["asc", "desc"]] = "desc",
        purpose: Optional[FilePurpose] = None
):
    """
    查询文件列表
    """
    api_key_data: ApiKey = await validate_auth('', request=request, check_billing=False, check_limit=False)

    files = await gateway_file_curd.get_user_files(
        creator_id=api_key_data.creator,
        after=after,
        limit=limit,
        order=order,
        purpose=purpose
    )

    return FileListResponse(
        data=[
            FileInfo(
                id=f["id"],
                bytes=f["bytes"],
                created_at=int(f["created_at"].timestamp()),
                filename=f["filename"],
                purpose=f["purpose"]
            )
            for f in files
        ]
    )


async def _get_file(request: Request, file_id: str):
    api_key_data: ApiKey = await validate_auth('', request=request, check_billing=False, check_limit=False)

    filter_conditions = [
        {"column_name": "id", "operator": "eq", "value": file_id},
        {"column_name": "status", "operator": "eq", "value": FileStatus.ACTIVE},
        {"column_name": "creator_id", "operator": "eq", "value": api_key_data.creator}
    ]
    file_info = await gateway_file_curd.get_by_filter(filter_conditions)
    file_info = file_info[0].to_dict() if file_info else None

    if not file_info:
        raise GatewayException("文件不存在", HTTPStatus.NOT_FOUND)
    return file_info, api_key_data


@api_router.get("/files/{file_id}")
async def get_file(
        request: Request,
        file_id: str
):
    """
    查询单个文件信息
    """
    file_info, _ = await _get_file(request, file_id)

    return FileInfo(
        id=file_info["id"],
        bytes=file_info["bytes"],
        created_at=int(file_info["created_at"].timestamp()),
        filename=file_info["filename"],
        purpose=file_info["purpose"]
    )


@api_router.delete("/files/{file_id}")
async def delete_file(
        request: Request,
        file_id: str
):
    """
    删除文件
    """
    _, api_key_data = await _get_file(request, file_id)

    # 删除物理文件
    file_path = Path(f"{settings.USER_FILE_DIR}/{api_key_data.creator}") / file_id
    if file_path.exists():
        file_path.unlink()

    # 更新数据库状态
    update_conditions = {
        "status": FileStatus.DELETE,
        "updated_at": datetime.now()
    }
    await gateway_file_curd.base_update(
        data_id=file_id,
        data=update_conditions,
        strict=True
    )

    return {
        "id": file_id,
        "object": "file",
        "deleted": True
    }
