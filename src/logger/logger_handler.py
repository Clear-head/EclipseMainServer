import logging
import logging.config
import json
import os
from pathlib import Path
import datetime
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
    
    log_path = Path(logger_abs_path).parent.parent.joinpath('logs').joinpath(name)

    cache_key = (name, log_path)
    if cache_key in logger_cache:
        return logger_cache[cache_key]

    if not Path(log_path).exists():
        Path(log_path).mkdir(parents=True, exist_ok=True)

    # 새로운 로거 생성 (root 로거와 분리)
    new_logger = logging.getLogger(name)
    
    # 기존 핸들러 모두 제거
    new_logger.handlers.clear()
    
    # 파일 핸들러 생성
    log_filename = Path(log_path).joinpath(
        f"{name}-{datetime.datetime.now().strftime('%Y-%m-%d')}.txt"
    )
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 포맷터 설정
    formatter = logging.Formatter(
        '[%(levelname)s][%(asctime)s][%(filename)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # 콘솔 핸들러 생성
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 핸들러 등록
    new_logger.addHandler(file_handler)
    new_logger.addHandler(console_handler)
    new_logger.setLevel(logging.INFO)
    
    # 핵심: root 로거로의 전파 차단
    new_logger.propagate = False
    
    logger_cache[cache_key] = new_logger

    return new_logger