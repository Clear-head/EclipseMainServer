import asyncio
import json
from playwright.async_api import async_playwright, TimeoutError, Error

async def initialize_browser_and_page():
    """
    브라우저를 초기화하고 카카오맵 페이지로 이동합니다.
    
    Returns:
        tuple: (browser, page) 객체
    """
    p = async_playwright()
    playwright = await p.start()
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()
    
    print("카카오맵 페이지로 이동 중...")
    await page.goto("https://map.kakao.com/")
    
    return browser, page, playwright

async def search_restaurants(page):
    """
    음식점을 검색하고 검색 결과 목록이 나타날 때까지 기다립니다.
    
    Args:
        page: Playwright 페이지 객체
        
    Returns:
        bool: 검색 성공 여부
    """
    print("음식점 검색 중...")
    # '음식점' 검색어 입력
    await page.locator("#search\\.keyword\\.query").fill("음식점")
    # 엔터 키 눌러 검색 실행
    await page.keyboard.press("Enter")

    # 검색 결과 목록이 나타날 때까지 기다립니다.
    try:
        await page.wait_for_selector("#info\\.search\\.place\\.list > li", timeout=10000)
        await asyncio.sleep(2)
        return True
    except TimeoutError:
        print("검색 결과 목록을 찾지 못했습니다.")
        return False

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
            print(f"더보기 버튼 클릭 시도 중... (시도 {i+1}/{retry_count})")
            await page.wait_for_selector(more_button_selector, state='visible', timeout=5000)
            await asyncio.sleep(3)
            await page.locator(more_button_selector).click(force=True)
            await page.locator(more_button_selector).click(force=True)
            print("더보기 버튼 클릭 성공.")
            await asyncio.sleep(3) # 추가 결과 로딩 대기
            return True
        except (TimeoutError, Error) as e:
            print(f"클릭 실패: {e}")
            await asyncio.sleep(2) # 잠시 대기 후 재시도
    
    print("더보기 버튼 클릭에 최종 실패했습니다.")
    return False

async def scrape_page_restaurants(page):
    """
    현재 페이지의 음식점 이름들을 스크래핑합니다.
    
    Args:
        page: Playwright 페이지 객체
        
    Returns:
        list: 음식점 이름 리스트
    """
    restaurants = []
    restaurant_elements = await page.locator("#info\\.search\\.place\\.list .PlaceItem .head_item .tit_name > a.link_name").all()
    
    for element in restaurant_elements:
        name = await element.text_content()
        if name:
            print(name)
            restaurants.append(name.strip())
    
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
        print(f"{page_number} 페이지로 이동 중...")
        await asyncio.sleep(2) # 페이지 로딩 대기
        return True
    except TimeoutError:
        print(f"페이지 {page_number}가 없거나 클릭할 수 없습니다.")
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
    
    # '다음' 버튼이 활성화된 상태인지 확인합니다.
    if await page.locator(next_button_selector).get_attribute("class") == "next disabled":
        print("더 이상 다음 페이지가 없습니다.")
        return False
    
    try:
        await page.wait_for_selector(next_button_selector, state='visible', timeout=3000)
        await page.locator(next_button_selector).click()
        print("다음 페이지 그룹으로 이동합니다.")
        await asyncio.sleep(2) # 새 페이지 그룹 로딩 대기
        return True
    except TimeoutError:
        print("더 이상 다음 페이지가 없습니다.")
        return False

async def scrape_all_pages(page):
    """
    모든 페이지의 음식점 정보를 스크래핑합니다.
    
    Args:
        page: Playwright 페이지 객체
        
    Returns:
        list: 전체 음식점 이름 리스트
    """
    all_restaurants = []
    
    while True:
        # 1페이지부터 5페이지까지 순회
        for i in range(1, 6):
            if not await navigate_to_page(page, i):
                break  # 페이지가 없으면 루프 탈출
            
            # 현재 페이지의 음식점 스크래핑
            restaurants = await scrape_page_restaurants(page)
            all_restaurants.extend(restaurants)
            
            print(f"현재까지 총 {len(all_restaurants)}개의 음식점을 찾았습니다.")
        
        # 다음 페이지 그룹으로 이동 (5페이지를 모두 스크래핑한 후)
        if not await navigate_to_next_page_group(page):
            break  # 다음 페이지 그룹이 없으면 반복문 종료
    
    return all_restaurants

def save_to_json(restaurants, file_path="restaurants.json"):
    """
    음식점 데이터를 JSON 파일로 저장합니다.
    
    Args:
        restaurants (list): 음식점 이름 리스트
        file_path (str): 저장할 파일 경로
    """
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=4)
    
    print(f"데이터가 '{file_path}' 파일에 성공적으로 저장되었습니다.")

async def scrape_restaurants():
    """
    카카오맵에서 음식점 이름을 여러 페이지에 걸쳐 스크래핑하여 JSON 파일로 저장합니다.
    """
    browser, page, playwright = await initialize_browser_and_page()
    
    try:
        # 음식점 검색
        if not await search_restaurants(page):
            print("검색에 실패했습니다. 스크래핑을 종료합니다.")
            return
        
        # 더보기 버튼 클릭 (선택사항)
        await click_more_button(page)
        
        # 모든 페이지의 음식점 스크래핑
        restaurants = await scrape_all_pages(page)
        
        print(f"스크래핑 완료. 총 {len(restaurants)}개의 음식점을 찾았습니다.")
        
        # JSON 파일로 저장
        save_to_json(restaurants)
        
    except Exception as e:
        print(f"스크래핑 중 오류가 발생했습니다: {e}")
    
    finally:
        await browser.close()
        await playwright.stop()