"""
주소 파싱 유틸리티
"""
from typing import Tuple

from src.logger.custom_logger import get_logger

logger = get_logger(__name__)


class AddressParser:
    """주소 파싱 유틸리티 클래스"""
    
    @staticmethod
    def parse_address(full_address: str) -> Tuple[str, str, str, str]:
        """
        전체 주소를 do, si, gu, detail_address로 분리
        
        Args:
            full_address: 전체 주소 (예: "서울 마포구 양화로 144")
            
        Returns:
            Tuple[str, str, str, str]: (do, si, gu, detail_address)
        """
        if not full_address:
            return "", "", "", ""
        
        try:
            do = ""
            si = ""
            gu = ""
            detail_address = ""
            
            # 특별시/광역시 매핑 (do 없이 si에만 들어감)
            city_mapping = {
                '서울': '서울특별시',
                '부산': '부산광역시',
                '대구': '대구광역시',
                '인천': '인천광역시',
                '광주': '광주광역시',
                '대전': '대전광역시',
                '울산': '울산광역시',
                '세종': '세종특별자치시'
            }
            
            # 도 단위 매핑 (약칭 처리)
            do_mapping = {
                '경기': '경기도',
                '강원': '강원도',
                '충북': '충청북도',
                '충남': '충청남도',
                '전북': '전북특별자치도',
                '전남': '전라남도',
                '경북': '경상북도',
                '경남': '경상남도',
                '제주': '제주특별자치도'
            }
            
            remaining = full_address
            
            # 1단계: 특별시/광역시/도 처리
            for short_name, full_name in city_mapping.items():
                # "서울" 또는 "서울특별시"로 시작하는 경우
                if remaining.startswith(short_name):
                    si = full_name
                    # "서울" 다음이 공백이거나 구로 끝나는 단어가 오는 경우
                    if len(remaining) > len(short_name):
                        next_char = remaining[len(short_name)]
                        if next_char == ' ':
                            remaining = remaining[len(short_name):].strip()
                        elif next_char in ['구', '시']:
                            remaining = remaining[len(short_name):]
                        else:
                            # "서울특별시"처럼 붙어있는 경우
                            if remaining.startswith(full_name):
                                remaining = remaining[len(full_name):].strip()
                            else:
                                remaining = remaining[len(short_name):]
                    else:
                        remaining = ""
                    break
            
            # 도 단위 처리 (si가 아직 설정되지 않은 경우)
            if not si:
                for short_name, full_name in do_mapping.items():
                    # "경기" 또는 "경기도"로 시작하는 경우
                    if remaining.startswith(short_name):
                        do = full_name
                        # "경기" 다음이 공백이거나 시로 끝나는 단어가 오는 경우
                        if len(remaining) > len(short_name):
                            next_char = remaining[len(short_name)]
                            if next_char == ' ':
                                remaining = remaining[len(short_name):].strip()
                            elif next_char in ['시']:
                                remaining = remaining[len(short_name):]
                            else:
                                # "경기도"처럼 붙어있는 경우
                                if remaining.startswith(full_name):
                                    remaining = remaining[len(full_name):].strip()
                                else:
                                    remaining = remaining[len(short_name):]
                        else:
                            remaining = ""
                        break
                
                # 기존 로직: "경기도", "충청북도" 등 전체 이름으로 끝나는 경우
                if not do:
                    parts = remaining.split(maxsplit=1)
                    if parts:
                        first_word = parts[0]
                        if first_word.endswith('도') or first_word.endswith('특별자치도'):
                            do = first_word
                            remaining = parts[1] if len(parts) > 1 else ""
            
            # 2단계: do가 있는 경우 si 추출 (시)
            if do and not si:
                # 공백으로 구분된 경우
                parts = remaining.split(maxsplit=1)
                if parts:
                    first_part = parts[0]
                    if first_part.endswith('시'):
                        si = first_part
                        remaining = parts[1] if len(parts) > 1 else ""
                    else:
                        # 공백 없이 붙어있는 경우 (예: "수원시권선구")
                        # 시를 찾아서 분리
                        import re
                        match = re.match(r'^([가-힣]+[시])', remaining)
                        if match:
                            si = match.group(1)
                            remaining = remaining[len(si):].strip()
            
            # 3단계: 구 추출
            if remaining:
                # 공백으로 구분된 경우
                parts = remaining.split(maxsplit=1)
                if parts:
                    first_part = parts[0]
                    if first_part.endswith('구'):
                        gu = first_part
                        detail_address = parts[1] if len(parts) > 1 else ""
                    else:
                        # 공백 없이 붙어있는 경우 (예: "권선구곡반정동")
                        import re
                        match = re.match(r'^([가-힣]+[구])', remaining)
                        if match:
                            gu = match.group(1)
                            detail_address = remaining[len(gu):].strip()
                        else:
                            detail_address = remaining
            
            return do, si, gu, detail_address
            
        except Exception as e:
            logger.error(f"주소 파싱 중 오류: {e}")
            return "", "", "", full_address