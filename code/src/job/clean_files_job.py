# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta
from pathlib import Path

from src.apps.gateway.curd import gateway_file_curd
from src.common.const.comm_const import FileStatus
from src.common.loggers import logger
from src.setting import settings


async def clean_expired_files():
    """清理超过指定天数的文件，先从数据库查询过期文件，再删除文件系统中的文件"""
    try:
        if not os.path.exists(settings.USER_FILE_DIR):
            logger.info(f"用户文件目录不存在: {settings.USER_FILE_DIR}")
            return

        current_time = datetime.now()
        retention_days = settings.FILE_RETENTION_DAYS
        expiration_date = current_time - timedelta(days=retention_days)

        # 从数据库查询超过保留期限的文件
        filter_conditions = [
            {"column_name": "status", "operator": "eq", "value": FileStatus.ACTIVE},
            {"column_name": "created_at", "operator": "lt", "value": expiration_date}
        ]

        expired_files = await gateway_file_curd.get_by_filter(filter_conditions)

        if not expired_files:
            logger.info("没有找到需要清理的过期文件")
            return

        logger.info(f"找到 {len(expired_files)} 个过期文件需要清理")

        file_items = [file.to_dict() for file in expired_files]

        successfully_deleted_files = []

        for file_item in file_items:
            creator_id = file_item["creator_id"]
            file_id = file_item["id"]
            file_path = Path(f"{settings.USER_FILE_DIR}/{creator_id}/{file_id}")

            # 检查并删除文件
            if file_path.exists() and file_path.is_file():
                try:
                    file_path.unlink()
                    successfully_deleted_files.append(file_id)
                    logger.info(f"已删除过期文件: {file_path}")
                except Exception as e:
                    logger.error(f"删除文件 {file_path} 失败: {e}")

        # 更新成功删除文件的数据库状态
        if successfully_deleted_files:
            updated_count = await gateway_file_curd.update_expired_files_status(
                file_ids=successfully_deleted_files,
                status=FileStatus.INACTIVE,
                updated_at=current_time
            )

            logger.info(f"已批量更新 {updated_count} 个文件的数据库状态为过期")

    except Exception as e:
        logger.error(f"清理过期文件时发生错误: {e}", exc_info=True)
