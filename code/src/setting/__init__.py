# -*- coding: utf-8 -*-
import os

from dotenv import load_dotenv

from .setting import Settings


def get_project_dir():
    """
        获取manifests目录
    """
    project_dir = os.path.dirname(__file__)
    while not os.path.exists(os.path.join(project_dir, 'manifests')):
        project_dir = os.path.dirname(project_dir)
    return project_dir


if ENV_CONF := os.getenv("ENV_CONF", None):
    root_dir = get_project_dir()

    base_env_path = os.path.join(root_dir, "manifests/base/config.env")
    load_dotenv(dotenv_path=base_env_path)

    ENV_CONF_PATH = os.path.join(root_dir, f'manifests/overlay/{ENV_CONF}/config.env')
    load_dotenv(dotenv_path=ENV_CONF_PATH, override=True)

settings = Settings()
