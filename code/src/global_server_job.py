# -*- coding: utf-8 -*-

import random
import threading
import time

from src.common.loggers import logger
from src.common.utils.dlock import DLock

GLOBAL_JOB_EXPIRE =60 * 10


def global_task(name, async_exec=False):
    def decorator(func):
        global_job.register_task([MaaSAsyncTask(func, name, async_exec)])
    return decorator


class MaaSAsyncTask:

    def __init__(self, task_fun, name=None, async_exec=False):
        self.async_exec = async_exec
        self.name = name
        self.task_fun = task_fun

    def process(self):
        self.task_fun()


class GlobalJob:
    """
    全局单线程任务
    保证多个pod以及多个服务进程中中，仅有一个线程运行的任务
    """

    def __init__(self):
        self.tasks: list[MaaSAsyncTask] = []
        self.lock = None

    def register_task(self, tasks: list[MaaSAsyncTask]):
        self.tasks.extend(tasks)

    def start(self, server_name):

        # 不做无用功
        if not self.tasks:
            return

        # 有锁者执行业务，无锁者努力争取
        self.lock = DLock(f'global-lock:{server_name}', GLOBAL_JOB_EXPIRE)
        while True:
            try:
                if not self.lock.acquire():
                    time.sleep(random.randint(GLOBAL_JOB_EXPIRE // 3, GLOBAL_JOB_EXPIRE // 2))
                else:
                    break
            except Exception as e:
                logger.exception("获取全局锁异常", exc_info=e)
                time.sleep(10)

        # 执行全局任务，必须是异步的
        for task in self.tasks:
            logger.info(f"启动[{task.name}]异步任务")
            if task.async_exec:
                threading.Thread(target=task.process, daemon=True).start()
            else:
                task.process()

    def release(self):
        if self.lock:
            self.lock.release()

global_job = GlobalJob()
