from bs4 import BeautifulSoup
from playwright_stealth import Stealth
from playwright.async_api import async_playwright
import asyncio


async def scrape_player_stats(url):
    # initialize Stealth with Playwright
    async with Stealth().use_async(async_playwright()) as p:
        # launch headless browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        # wait for the page to load completely
        await asyncio.sleep(5)
        response = await page.content()
        await browser.close()
    return response

    # with open('fbref.html', 'wb+') as file:
    #     file.write(response)
    # 1. tarayıcı aç
    # 2. sayfaya git
    # 3. HTML al
    # 4. tarayıcı kapat

    # 5. BeautifulSoup ile parse et
    # 6. tabloyu bul
    # 7. satırları dict'e çevir
    # 8. liste döndür


# link = 'https://fbref.com/en/players/b6f54c31/all_comps/Finn-Azaz-Stats---All-Competitions#all_stats_standard'
link = 'https://example.com'
result = asyncio.run(scrape_player_stats(link))
print(result)




