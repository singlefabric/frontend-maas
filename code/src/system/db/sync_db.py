# -*- coding: utf-8 -*-

from typing import Callable, Dict

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Query
from sqlmodel import Session

from src.common.context import Context
from src.setting import settings

engine: Engine = create_engine(
    settings.DB_CONNECTION_STR,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    echo=settings.DB_ECHO,
    echo_pool=True,
    future=True
)


session_maker: Callable[..., Session] = sessionmaker(
    bind=engine, class_=Session, expire_on_commit=False, autoflush=False)


# def get_session(session_args: Optional[Dict]) -> Session:
#     with session_maker(**(session_args or {})) as session:
#         yield session

def _inject_sess(inject_list: list[Query]):
    for _query in inject_list:
        _query.session = Context.THREAD_SESSION.get()


def session_manage(commit_on_exit=True):
    def decorator(func):
        async def wrapper(self, *args, **kwargs):

            # 事务传播，有 session 直接用，没有 session 才开启
            if Context.THREAD_SESSION.get():
                result = await func(self, *args, **kwargs)
            else:
                with SessionWrapper(commit_on_exit=commit_on_exit):
                    result = await func(self, *args, **kwargs)

            # ModelT, = self.target_type
            # func_name = func.__name__
            # if DataT and func_name in ['get_by_id']:
            #     result = DataT(result)

            return result
        return wrapper
    return decorator


class SessionWrapper:
    def __init__(self, session_args: Dict = None, commit_on_exit=True):
        self.token = None
        self.session_args = session_args or {}
        self.commit_on_exit = commit_on_exit

    @classmethod
    def session(cls) -> Session:
        return Context.THREAD_SESSION.get()

    def __enter__(self):
        self.token = Context.THREAD_SESSION.set(session_maker(**self.session_args))
        return type(self)

    def __exit__(self, exc_type, *_):
        """
        退出时自动处理事务，如果有报错，自动回滚。如果没有报错自动提交。完成后回收 sess 和线程变量
        :param exc_type: 不为 None 时代表有错误
        :param _:
        :return: 有错误时返回 False，继续抛出异常
        """
        sess = Context.THREAD_SESSION.get()
        if exc_type is not None:
            sess.rollback()
        elif self.commit_on_exit:
            sess.commit()
        sess.close()
        Context.THREAD_SESSION.reset(self.token)

        # 如果出现异常，回收资源后再次抛出
        return exc_type is None
