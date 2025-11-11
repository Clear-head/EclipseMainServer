"""
설정 로더 유틸리티: src/resources/crawl/*.json 파일을 읽어 옵니다.
"""
import json
from pathlib import Path
from typing import Any, Dict

from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


def load_json_resource(filename: str) -> Dict[str, Any]:
    """
    src/resources/crawl/{filename} 을 읽어서 dict로 반환.
    예외 발생 시 빈 dict 반환.
    """
    try:
        resources_dir = Path(__file__).resolve().parents[1] / "resources" / "crawl"
        file_path = resources_dir / filename
        if not file_path.exists():
            logger.error(f"설정 파일이 없습니다: {file_path}")
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"설정 파일 로드 오류 ({filename}): {e}")
        return {}