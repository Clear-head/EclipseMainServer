import asyncio
import json
from playwright.async_api import async_playwright, TimeoutError, Error
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# 로거 import 및 초기화
from logger.logger_handler import get_logger
logger = get_logger('crawling_kakao')

async def initialize_browser_and_page():
    """
    브라우저를 초기화하고 카카오맵 페이지로 이동합니다.
    
    Returns:
        tuple: (browser, page) 객체
    """
    try:
        p = async_playwright()
        playwright = await p.start()
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page()
        
        await page.goto("https://map.kakao.com/")
        return browser, page, playwright
    except Exception as e:
        logger.error(f"브라우저 초기화 중 오류 발생: {e}")
        raise

async def search_restaurants(page, search_keyword="노량진동 스타벅스"):
    """
    음식점을 검색하고 검색 결과 목록이 나타날 때까지 기다립니다.
    
    Args:
        page: Playwright 페이지 객체
        search_keyword: 검색할 키워드
        
    Returns:
        bool: 검색 성공 여부
    """
    try:
        logger.info(f"'{search_keyword}' 크롤링 시작")
        
        # 검색어 입력
        await page.locator("#search\\.keyword\\.query").fill(search_keyword)
        # 엔터 키 눌러 검색 실행
        await page.keyboard.press("Enter")

        # 검색 결과 목록이 나타날 때까지 기다립니다.
        await page.wait_for_selector("#info\\.search\\.place\\.list > li", timeout=10000)
        await asyncio.sleep(2)
        return True
    except TimeoutError:
        logger.error("검색 결과 목록을 찾지 못했습니다.")
        return False
    except Exception as e:
        logger.error(f"검색 중 오류 발생: {e}")
        return False

async def get_restaurant_name(page, item_index):
    """
    특정 항목의 음식점 이름을 가져옵니다.
    
    Args:
        page: Playwright 페이지 객체
        item_index (int): 항목 인덱스 (1부터 시작)
        
    Returns:
        str: 음식점 이름
    """
    try:
        name_selector = f"#info\\.search\\.place\\.list > li:nth-child({item_index}) .head_item .tit_name > a.link_name"
        name_element = page.locator(name_selector)
        name = await name_element.text_content()
        return name.strip() if name else None
    except Exception as e:
        logger.error(f"이름 추출 중 오류 (항목 {item_index}): {e}")
        return None

async def get_restaurant_category(page, item_index):
    """
    특정 항목의 음식점 카테고리를 가져옵니다.
    
    Args:
        page: Playwright 페이지 객체
        item_index (int): 항목 인덱스 (1부터 시작)
        
    Returns:
        str: 음식점 카테고리
    """
    try:
        category_selector = f"#info\\.search\\.place\\.list > li:nth-child({item_index}) > div.head_item.clickArea > span"
        category_element = page.locator(category_selector)
        category = await category_element.text_content()
        return category.strip() if category else None
    except Exception as e:
        logger.error(f"카테고리 추출 중 오류 (항목 {item_index}): {e}")
        return None

async def get_restaurant_address(page, item_index):
    """
    특정 항목의 음식점 주소를 가져옵니다.
    
    Args:
        page: Playwright 페이지 객체
        item_index (int): 항목 인덱스 (1부터 시작)
        
    Returns:
        str: 음식점 주소
    """
    try:
        address_selector = f"#info\\.search\\.place\\.list > li:nth-child({item_index}) > div.info_item > div.addr > p:nth-child(1)"
        address_element = page.locator(address_selector)
        address = await address_element.text_content()
        return address.strip() if address else None
    except Exception as e:
        logger.error(f"주소 추출 중 오류 (항목 {item_index}): {e}")
        return None

async def click_more_button(page):
    """
    '더보기' 버튼을 클릭하여 더 많은 검색 결과를 로드합니다.
    
    Args:
        page: Playwright 페이지 객체
        
    Returns:
        bool: 더보기 버튼 클릭 성공 여부
    """
    more_button_selector = "#info\\.search\\.place\\.more"
    retry_count = 3
    
    for i in range(retry_count):
        try:
            await page.wait_for_selector(more_button_selector, state='visible', timeout=5000)
            await asyncio.sleep(3)
            await page.locator(more_button_selector).click(force=True)
            await page.locator(more_button_selector).click(force=True)
            await asyncio.sleep(3) # 추가 결과 로딩 대기
            return True
        except (TimeoutError, Error) as e:
            logger.error(f"더보기 버튼 클릭 실패: {e}")
            await asyncio.sleep(2) # 잠시 대기 후 재시도
        logger.error("더보기 버튼 클릭 재시도")
    
    logger.error("더보기 버튼 클릭에 최종 실패했습니다.")
    return False

async def scrape_page_restaurants(page):
    """
    현재 페이지의 음식점 정보(이름, 카테고리, 주소)를 스크래핑합니다.
    
    Args:
        page: Playwright 페이지 객체
        
    Returns:
        list: 음식점 정보 딕셔너리 리스트
    """
    restaurants = []
    
    try:
        # 검색 결과 리스트의 모든 항목 개수 확인
        restaurant_list_items = await page.locator("#info\\.search\\.place\\.list > li").all()
        
        for i in range(1, len(restaurant_list_items) + 1):
            try:
                # 각 함수를 사용하여 정보 추출
                name = await get_restaurant_name(page, i)
                category = await get_restaurant_category(page, i)
                address = await get_restaurant_address(page, i)
                
                restaurant_info = {
                    "name": name,
                    "category": category,
                    "address": address
                }
                
                restaurants.append(restaurant_info)
            
            except Exception as e:
                logger.error(f"항목 {i} 스크래핑 중 오류: {e}")
                continue
    except Exception as e:
        logger.error(f"페이지 스크래핑 중 오류: {e}")
    
    return restaurants

async def navigate_to_page(page, page_number):
    """
    특정 페이지 번호로 이동합니다.
    
    Args:
        page: Playwright 페이지 객체
        page_number (int): 이동할 페이지 번호 (1-5)
        
    Returns:
        bool: 페이지 이동 성공 여부
    """
    page_selector = f"#info\\.search\\.page\\.no{page_number}"
    try:
        await page.wait_for_selector(page_selector, state='visible', timeout=10000)
        await page.locator(page_selector).click()
        await asyncio.sleep(2) # 페이지 로딩 대기
        return True
    except TimeoutError:
        logger.error(f"페이지 {page_number} 이동 실패")
        return False
    except Exception as e:
        logger.error(f"페이지 {page_number} 이동 중 오류: {e}")
        return False

async def navigate_to_next_page_group(page):
    """
    다음 페이지 그룹으로 이동합니다.
    
    Args:
        page: Playwright 페이지 객체
        
    Returns:
        bool: 다음 페이지 그룹 이동 성공 여부
    """
    next_button_selector = "#info\\.search\\.page\\.next"
    
    try:
        # '다음' 버튼이 활성화된 상태인지 확인합니다.
        if await page.locator(next_button_selector).get_attribute("class") == "next disabled":
            return False
        
        await page.wait_for_selector(next_button_selector, state='visible', timeout=3000)
        await page.locator(next_button_selector).click()
        await asyncio.sleep(2) # 새 페이지 그룹 로딩 대기
        return True
    except TimeoutError:
        logger.error(f"다음 페이지 그룹 이동 실패")
        return False
    except Exception as e:
        logger.error(f"다음 페이지 그룹 이동 중 오류: {e}")
        return False

async def scrape_all_pages(page):
    """
    모든 페이지의 음식점 정보를 스크래핑합니다.
    
    Args:
        page: Playwright 페이지 객체
        
    Returns:
        list: 전체 음식점 정보 리스트
    """
    all_restaurants = []
    
    try:
        while True:
            # 1페이지부터 5페이지까지 순회
            for i in range(1, 6):
                if not await navigate_to_page(page, i):
                    break  # 페이지가 없으면 루프 탈출
                
                # 현재 페이지의 음식점 스크래핑
                restaurants = await scrape_page_restaurants(page)
                all_restaurants.extend(restaurants)
            
            # 다음 페이지 그룹으로 이동 (5페이지를 모두 스크래핑한 후)
            if not await navigate_to_next_page_group(page):
                break  # 다음 페이지 그룹이 없으면 반복문 종료
    except Exception as e:
        logger.error(f"모든 페이지 스크래핑 중 오류: {e}")
    
    return all_restaurants

def save_to_json(restaurants, file_path="restaurants.json"):
    """
    음식점 데이터를 JSON 파일로 저장합니다.
    
    Args:
        restaurants (list): 음식점 정보 딕셔너리 리스트
        file_path (str): 저장할 파일 경로
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(restaurants, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"JSON 파일 저장 중 오류: {e}")

async def scrape_restaurants(search_keyword="노량진동 스타벅스"):
    """
    카카오맵에서 음식점 정보(이름, 카테고리, 주소)를 여러 페이지에 걸쳐 스크래핑하여 JSON 파일로 저장합니다.
    """
    browser = None
    playwright = None
    
    try:
        # 브라우저 초기화
        browser, page, playwright = await initialize_browser_and_page()
        
        # 음식점 검색
        if not await search_restaurants(page, search_keyword):
            logger.error("검색에 실패했습니다. 스크래핑을 종료합니다.")
            return
        
        # 더보기 버튼 클릭 (선택사항)
        await click_more_button(page)
        
        # 모든 페이지의 음식점 스크래핑
        restaurants = await scrape_all_pages(page)
        
        logger.info(f"'{search_keyword}' 크롤링 완료")
        
        # JSON 파일로 저장
        save_to_json(restaurants)
        
    except Exception as e:
        logger.error(f"스크래핑 중 오류가 발생했습니다: {e}")
    
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()

# 메인 실행부
if __name__ == "__main__":
    asyncio.run(scrape_restaurants())