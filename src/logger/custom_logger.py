import datetime
import json
import logging
import logging.config
import os
from pathlib import Path

from ..utils.path import path_dic

logger_cache = {}
logger_abs_path = os.path.abspath(os.path.dirname(__file__))

def get_logger(name):
    """
    :param name:
        프로세스 이름
    :return:
        로거 객체
    """

    name = list(name.split('.'))
    name = '.'.join(name[:1])

    log_path = Path(logger_abs_path).parent.parent.joinpath('logs').joinpath(name)

    cache_key = (name, log_path)
    if cache_key in logger_cache:
        return logger_cache[cache_key]

    if not Path(log_path).exists():
        Path(log_path).mkdir(parents=True, exist_ok=True)

    config = json.load(open(path_dic["log_config"]))
    config['handlers']['file']['filename'] = f"{name}-{datetime.datetime.now().strftime('%Y-%m-%d')}.txt"
    config['handlers']['file']['filename'] = Path(log_path).joinpath(config['handlers']['file']['filename'])
    logging.config.dictConfig(config)

    new_logger = logging.getLogger(name)
    logger_cache[cache_key] = new_logger

    return new_logger