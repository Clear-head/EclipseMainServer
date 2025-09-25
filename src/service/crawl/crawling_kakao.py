import asyncio
import json
from playwright.async_api import async_playwright, TimeoutError, Error

async def scrape_restaurants():
    """
    카카오맵에서 음식점 이름을 여러 페이지에 걸쳐 스크래핑하여 JSON 파일로 저장합니다.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print("카카오맵 페이지로 이동 중...")
        await page.goto("https://map.kakao.com/")

        # 검색창에 '음식점' 입력 후 검색 버튼 클릭
        print("음식점 검색 중...")
        # '음식점' 검색어 입력
        await page.locator("#search\\.keyword\\.query").fill("음식점")
        # 엔터 키 눌러 검색 실행
        await page.keyboard.press("Enter")

        # 검색 결과 목록이 나타날 때까지 기다립니다.
        try:
            await page.wait_for_selector("#info\\.search\\.place\\.list > li", timeout=10000)
            await asyncio.sleep(2)
        except TimeoutError:
            print("검색 결과 목록을 찾지 못했습니다. 스크래핑을 종료합니다.")
            await browser.close()
            return
        
        # '더보기' 버튼을 클릭합니다.
        # 여러 번 시도하여 안정성을 높입니다.
        more_button_selector = "#info\\.search\\.place\\.more"
        retry_count = 3
        is_clicked = False
        for i in range(retry_count):
            try:
                print(f"더보기 버튼 클릭 시도 중... (시도 {i+1}/{retry_count})")
                await page.wait_for_selector(more_button_selector, state='visible', timeout=5000)
                await asyncio.sleep(3)
                await page.locator(more_button_selector).click(force=True)
                await page.locator(more_button_selector).click(force=True)
                print("더보기 버튼 클릭 성공.")
                is_clicked = True
                await asyncio.sleep(3) # 추가 결과 로딩 대기
                break
            except (TimeoutError, Error) as e:
                print(f"클릭 실패: {e}")
                await asyncio.sleep(2) # 잠시 대기 후 재시도
        
        if not is_clicked:
            print("더보기 버튼 클릭에 최종 실패했습니다. 다음 단계로 넘어갑니다.")

        restaurants = []
        
        while True:
            # 1페이지부터 5페이지까지 순회
            for i in range(1, 6):
                page_selector = f"#info\\.search\\.page\\.no{i}"
                try:
                    await page.wait_for_selector(page_selector, state='visible', timeout=10000)
                    await page.locator(page_selector).click()
                    print(f"{i} 페이지로 이동 중...")
                    await asyncio.sleep(2) # 페이지 로딩 대기

                    # 음식점 이름 스크래핑
                    restaurant_elements = await page.locator("#info\\.search\\.place\\.list .PlaceItem .head_item .tit_name > a.link_name").all()
                    for element in restaurant_elements:
                        name = await element.text_content()
                        if name:
                            print(name)
                            restaurants.append(name.strip())
                            
                    
                    print(f"현재까지 총 {len(restaurants)}개의 음식점을 찾았습니다.")

                except TimeoutError:
                    print(f"페이지 {i}가 없거나 클릭할 수 없습니다. 다음 단계로 넘어갑니다.")
                    break # 페이지가 없으면 루프 탈출

            # 다음 페이지 그룹으로 이동 (5페이지를 모두 스크래핑한 후)
            next_button_selector = "#info\\.search\\.page\\.next"
            # '다음' 버튼이 활성화된 상태인지 확인합니다.
            if await page.locator(next_button_selector).get_attribute("class") == "next disabled":
                print("더 이상 다음 페이지가 없습니다. 스크래핑을 종료합니다.")
                break
            try:
                await page.wait_for_selector(next_button_selector, state='visible', timeout=3000)
                await page.locator(next_button_selector).click()
                print("다음 페이지 그룹으로 이동합니다.")
                await asyncio.sleep(2) # 새 페이지 그룹 로딩 대기
            except TimeoutError:
                print("더 이상 다음 페이지가 없습니다. 스크래핑을 종료합니다.")
                break # '다음 페이지' 버튼이 없으면 반복문 종료

        await browser.close()
        
    print(f"스크래핑 완료. 총 {len(restaurants)}개의 음식점을 찾았습니다.")
    
    # 추출한 데이터를 JSON 파일로 저장
    file_path = "restaurants.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=4)
        
    print(f"데이터가 '{file_path}' 파일에 성공적으로 저장되었습니다.")
