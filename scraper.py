from playwright.sync_api import sync_playwright
import re
import os


def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = browser.new_page()
        page.goto(
            "https://goyfield.moe/records/global",
            wait_until="networkidle",
            timeout=60000
        )

        # Wait until real stats are rendered (not 0)
        page.wait_for_function("""
            () => {
                const spans = document.querySelectorAll('span.font-bold');
                for (const s of spans) {
                    if (s.innerText && s.innerText !== '0' && s.innerText !== '0.00%') return true;
                }
                return false;
            }
        """, timeout=30000)

        # Click Standard Headhunting tab
        page.get_by_text("Standard Headhunting", exact=True).first.click()
        page.wait_for_timeout(3000)

        # Dump raw HTML so we can see exact structure
        html = page.content()
        print("=== HTML SNIPPET (searching for font-bold spans) ===")
        # Print every line containing font-bold
        for line in html.split('\n'):
            if 'font-bold' in line or 'Total Users' in line or 'Total Pulls' in line or 'Oroberyl' in line or 'Rate' in line or 'Count' in line or 'Median' in line or 'Stats' in line:
                print(line.strip())

        # Also print full inner text
        print("\n=== FULL INNER TEXT ===")
        print(page.inner_text("body"))

        browser.close()


scrape()
