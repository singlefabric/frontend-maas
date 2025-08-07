# -*- coding: utf-8 -*-
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import List
from typing import Optional

from sqlalchemy import func, and_, desc, asc
from starlette.requests import Request

from src.apps.apikey.curd import apikey_curd
from src.apps.apikey.rsp_schema import ApiKey
from src.apps.base_curd import BaseCURD
from src.apps.billing.curd import billing_curd
from src.apps.gateway.req_schema import FilePurpose
from src.apps.gateway.rsp_schema import Files, FileInfo
from src.apps.rate_limiter.limiter import limiter
from src.common.const.comm_const import MIN_FILENAME_LENGTH, MAX_FILENAME_LENGTH, ResourceModule, FileStatus, \
    MetricUnit, API_KEY_PREFIX, ApiKeyStatus, LAST_TIME_DIC
from src.common.exceptions import GatewayException
from src.common.loggers import logger
from src.common.utils.data import uuid
from src.setting import settings
from src.system.db.sync_db import session_manage


async def validate_auth(model: str, request: Request, unit: Optional[MetricUnit] = None, check_billing=True, check_limit=True):
    """
    校验接口权限
    """
    api_key = request.headers.get("Authorization")
    if not api_key:
        raise GatewayException("未提供令牌", HTTPStatus.UNAUTHORIZED)
    api_key = api_key.removeprefix(API_KEY_PREFIX)
    api_key_data: ApiKey = await apikey_curd.query_by_id_and_cache(api_key)
    if not api_key_data:
        raise GatewayException(f"无效的令牌:{api_key}", HTTPStatus.UNAUTHORIZED)
    if api_key_data.status != ApiKeyStatus.ACTIVE:
        raise GatewayException("令牌未生效", HTTPStatus.UNAUTHORIZED)

    if check_billing and not billing_curd.valid_balance(api_key_data.creator, model, unit):
        raise GatewayException("账户余额不足", HTTPStatus.PAYMENT_REQUIRED)

    if check_limit and not await limiter.check_rpm_and_tpm_limit(api_key_data.creator, model):
        raise GatewayException("请求频率超过限制", HTTPStatus.TOO_MANY_REQUESTS)

    LAST_TIME_DIC[api_key] = datetime.now()
    return api_key_data


class GatewayFileCURD(BaseCURD[Files]):
    def _parse_multipart_boundary(self, content_type: str) -> str:
        """解析multipart/form-data的boundary
        
        Args:
            content_type: HTTP请求头中的Content-Type值
            
        Returns:
            解析后的boundary字符串
        """
        if "multipart/form-data" in content_type:
            for part in content_type.split(";"):
                part = part.strip()
                if part.startswith("boundary="):
                    boundary = part[len("boundary="):]
                    if boundary.startswith('"') and boundary.endswith('"'):
                        boundary = boundary[1:-1]
                    return f"--{boundary}"
        raise GatewayException("未知的Content-Type", HTTPStatus.BAD_REQUEST)

    def _process_content(self, content: bytes, current_part: str, file_content: bytearray,
                         received_size: int, used_size: int) -> tuple[bytearray, int, str]:
        """处理文件内容
        Args:
            content: 要处理的内容
            current_part: 当前处理的部分类型（"file"或"purpose"）
            file_content: 文件内容缓冲区
            received_size: 已接收的文件大小
            used_size: 用户已使用的总存储空间
            
        Returns:
            tuple: 包含更新后的文件内容、接收大小和purpose值的元组
            
        Raises:
            GatewayException: 当文件大小超过限制或purpose无效时抛出异常
        """
        purpose = None

        if current_part == "file":
            file_content.extend(content)
            received_size += len(content)
            if received_size > settings.MAX_SINGLE_FILE_SIZE:
                raise GatewayException("文件大小超过限制", HTTPStatus.BAD_REQUEST)
            if used_size + received_size > settings.MAX_TOTAL_FILE_SIZE:
                raise GatewayException("存储空间超过限制", HTTPStatus.BAD_REQUEST)
        elif current_part == "purpose":
            purpose = content.decode('utf-8', errors='ignore').strip()
            if purpose not in FilePurpose.__members__.values():
                raise GatewayException("无效的purpose参数", HTTPStatus.BAD_REQUEST)

        return file_content, received_size, purpose

    async def process_upload_stream(self, request: Request, api_key_data: ApiKey):
        """处理文件上传流
        Args:
            request: HTTP请求对象
            file_path: 文件保存路径
            used_size: 用户已使用的总存储空间
            
        Returns:
            tuple: 包含文件名、purpose和文件大小的元组
        """
        # 检查文件数量限制
        file_count, used_size = await gateway_file_curd.get_user_file_stats(api_key_data.creator)
        if file_count >= settings.MAX_FILE_COUNTS:
            raise GatewayException("文件数量超过限制", HTTPStatus.BAD_REQUEST)

        content_type = request.headers.get("content-type", "")
        boundary = self._parse_multipart_boundary(content_type)

        # 初始化变量
        buffer = bytearray()
        file_content = bytearray()
        boundary_bytes = boundary.encode()
        boundary_end_bytes = (boundary + "--").encode()
        received_size = 0
        filename = None
        purpose = None
        file_path = None

        # 状态变量
        state = "FIND_BOUNDARY"  # 初始状态：查找边界
        current_part = None

        try:
            async for chunk in request.stream():
                buffer.extend(chunk)

                # 根据当前状态处理数据
                while buffer:
                    if state == "FIND_BOUNDARY":
                        # 查找边界
                        boundary_pos = buffer.find(boundary_bytes)
                        if boundary_pos == -1:
                            # 没找到边界，保留最后的部分以防边界被分割
                            if len(buffer) > len(boundary_bytes):
                                buffer = buffer[-len(boundary_bytes):]
                            break

                        # 找到边界，移动到边界后
                        buffer = buffer[boundary_pos + len(boundary_bytes):]

                        # 检查是否是结束边界
                        if buffer.startswith(b"--"):
                            buffer = bytearray()
                            break

                        # 跳过CRLF
                        if buffer.startswith(b"\r\n"):
                            buffer = buffer[2:]

                        state = "PARSE_HEADERS"

                    elif state == "PARSE_HEADERS":
                        # 查找头部结束位置
                        headers_end = buffer.find(b"\r\n\r\n")
                        if headers_end == -1:
                            # 头部不完整，等待更多数据
                            break

                        # 解析头部
                        headers = buffer[:headers_end].decode('utf-8', errors='ignore')

                        # 判断当前部分类型
                        if 'name="file"' in headers:
                            current_part = "file"
                            # 提取文件名
                            filename_start = headers.find('filename="')
                            if filename_start != -1:
                                filename_end = headers.find('"', filename_start + 10)
                                if filename_end != -1:
                                    filename = headers[filename_start + 10:filename_end]
                                    # 校验文件名
                                    if len(filename) < MIN_FILENAME_LENGTH or len(filename) > MAX_FILENAME_LENGTH:
                                        raise GatewayException(
                                            f"文件名长度超过限制{MIN_FILENAME_LENGTH}~{MAX_FILENAME_LENGTH}",
                                            HTTPStatus.BAD_REQUEST)

                        elif 'name="purpose"' in headers:
                            current_part = "purpose"

                        # 跳过头部
                        buffer = buffer[headers_end + 4:]
                        state = "PARSE_CONTENT"

                    elif state == "PARSE_CONTENT":
                        # 查找下一个边界
                        next_boundary_pos = buffer.find(b"\r\n" + boundary_bytes)

                        if next_boundary_pos == -1:
                            # 检查是否包含结束边界
                            end_boundary_pos = buffer.find(b"\r\n" + boundary_end_bytes)
                            if end_boundary_pos != -1:
                                # 找到结束边界
                                content = buffer[:end_boundary_pos]
                                file_content, received_size, part_purpose = self._process_content(
                                    content, current_part, file_content, received_size, used_size)
                                if part_purpose:
                                    purpose = part_purpose
                                buffer = bytearray()
                                break

                            # 没找到边界，保留最后部分以防边界被分割
                            if len(buffer) > 100:
                                content = buffer[:-100]
                                file_content, received_size, part_purpose = self._process_content(
                                    content, current_part, file_content, received_size, used_size)
                                if part_purpose:
                                    purpose = part_purpose
                                buffer = buffer[-100:]
                            break

                        # 找到下一个边界
                        content = buffer[:next_boundary_pos]
                        file_content, received_size, part_purpose = self._process_content(
                            content, current_part, file_content, received_size, used_size)
                        if part_purpose:
                            purpose = part_purpose

                        # 移动到边界位置
                        buffer = buffer[next_boundary_pos + 2:]  # +2 跳过\r\n
                        state = "FIND_BOUNDARY"

            # 将文件内容写入文件
            file_id = uuid(ResourceModule.FILE, length=24)
            if file_content:
                user_dir = Path(f"{settings.USER_FILE_DIR}/{api_key_data.creator}")
                user_dir.mkdir(parents=True, exist_ok=True)
                file_path = user_dir / file_id
                with open(file_path, "wb") as f:
                    f.write(file_content)

            if not filename:
                filename = "uploaded_file"

            now = datetime.now()
            file_info = {
                "id": file_id,
                "filename": filename,
                "purpose": purpose,
                "bytes": received_size,
                "creator_id": api_key_data.creator,
                "created_at": now,
                "updated_at": now
            }

            await gateway_file_curd.save_one(file_info)

            return FileInfo(
                id=file_id,
                bytes=received_size,
                created_at=int(now.timestamp()),
                filename=filename,
                purpose=purpose
            )

        except Exception as e:
            logger.exception(f"文件上传失败:")
            # 发生错误时清理文件
            if file_path and file_path.exists():
                file_path.unlink()
            if isinstance(e, GatewayException):
                raise e
            raise GatewayException(f"文件上传失败", HTTPStatus.INTERNAL_SERVER_ERROR)

    @session_manage()
    async def get_user_files(
            self,
            creator_id: str,
            after: Optional[str] = None,
            limit: int = 10,
            order: str = "desc",
            purpose: Optional[str] = None
    ) -> List[dict]:
        """获取用户文件列表"""
        query = self.session.query(self.ModelT).filter(
            and_(
                self.ModelT.creator_id == creator_id,
                self.ModelT.status == FileStatus.ACTIVE
            )
        )

        if purpose:
            query = query.filter(self.ModelT.purpose == purpose)

        if after:
            after_file = self.session.query(self.ModelT).filter(self.ModelT.id == after).first()
            if after_file:
                if order == "desc":
                    query = query.filter(self.ModelT.created_at < after_file.created_at)
                else:
                    query = query.filter(self.ModelT.created_at > after_file.created_at)

        # 添加排序
        if order == "desc":
            query = query.order_by(desc(self.ModelT.created_at), desc(self.ModelT.id))
        else:
            query = query.order_by(asc(self.ModelT.created_at), asc(self.ModelT.id))

        query = query.limit(limit)

        files = query.all()
        return [file.to_dict() for file in files]

    @session_manage()
    async def get_user_file_stats(self, creator_id: str) -> tuple[int, int]:
        """获取用户文件统计信息（文件数量和总存储空间）"""
        query = self.session.query(
            func.count().label('count'),
            func.sum(self.ModelT.bytes).label('total_size')
        ).select_from(self.ModelT).filter(
            and_(
                self.ModelT.creator_id == creator_id,
                self.ModelT.status == FileStatus.ACTIVE
            )
        )
        result = query.first()
        count = result.count if result else 0
        total_size = result.total_size or 0
        return count, total_size

    @session_manage()
    async def update_expired_files_status(self, file_ids: List[str], status: str, updated_at: datetime = None) -> int:
        """批量更新文件状态
        
        Args:
            file_ids: 文件ID列表
            status: 更新后的状态
            updated_at: 更新时间，默认为当前时间
            
        Returns:
            更新的记录数量
        """
        if not file_ids:
            return 0

        # 如果未提供更新时间，则使用当前时间
        if updated_at is None:
            updated_at = datetime.now()
        update_data = {
            "status": status,
            "updated_at": updated_at
        }
        from sqlalchemy import update
        stmt = update(self.ModelT).where(
            self.ModelT.id.in_(file_ids)
        ).values(update_data)

        result = self.session.execute(stmt)
        return result.rowcount


gateway_file_curd = GatewayFileCURD()
