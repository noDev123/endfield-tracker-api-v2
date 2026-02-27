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
        page.wait_for_timeout(8000)

        # It's a custom dropdown - click the trigger to open it, then pick Standard Headhunting
        try:
            # Click the dropdown trigger (shows current selection like "Special Headhunting")
            page.locator('button:has-text("Special Headhunting"), button:has-text("Headhunting")').first.click()
            page.wait_for_timeout(1000)
            # Now click Standard Headhunting from the opened list
            page.get_by_text("Standard Headhunting", exact=True).click()
            page.wait_for_timeout(4000)
            print("Switched to Standard Headhunting via dropdown")
        except Exception as e:
            print(f"Dropdown attempt 1 failed: {e}")
            try:
                # Fallback: native select
                page.select_option('select', label='Standard Headhunting')
                page.wait_for_timeout(4000)
                print("Switched via native select")
            except Exception as e2:
                print(f"Dropdown attempt 2 failed: {e2}")

        content = page.inner_text("body")
        browser.close()

        lines = [l.strip().replace('\xa0', '').replace('\u202f', '') for l in content.splitlines()]
        lines = [l for l in lines if l]

        def after(label, offset=1):
            for i, l in enumerate(lines):
                if l == label:
                    t = i + offset
                    return lines[t] if t < len(lines) else 'N/A'
            return 'N/A'

        total_users = after('Total Users')
        total_pulls = after('Total Pulls')

        # Oroberyl: find the line, then grab next line that's purely a big number
        oroberyl_spent = 'N/A'
        for i, l in enumerate(lines):
            if l == 'Oroberyl Spent':
                for j in range(i + 1, min(i + 5, len(lines))):
                    if re.match(r'^[\d\s,]+$', lines[j]) and len(lines[j].replace(' ', '').replace(',', '')) > 4:
                        oroberyl_spent = lines[j]
                        break
                break

        # 6★ Stats - use 'in' check to handle emoji like "6 🏔 Stats"
        rate6 = count6 = median_pity = 'N/A'
        for i, l in enumerate(lines):
            if '6' in l and 'Stats' in l and '5' not in l:
                for j in range(i + 1, min(i + 20, len(lines))):
                    if '5' in lines[j] and 'Stats' in lines[j]: break
                    if lines[j] == 'Rate'        and j+1 < len(lines): rate6       = lines[j+1]
                    if lines[j] == 'Count'       and j+1 < len(lines): count6      = lines[j+1]
                    if lines[j] == 'Median Pity' and j+1 < len(lines): median_pity = lines[j+1]
                break

        # 5★ Stats
        rate5 = count5 = 'N/A'
        for i, l in enumerate(lines):
            if '5' in l and 'Stats' in l:
                for j in range(i + 1, min(i + 15, len(lines))):
                    if lines[j] == 'Rate'  and j+1 < len(lines): rate5  = lines[j+1]
                    if lines[j] == 'Count' and j+1 < len(lines): count5 = lines[j+1]
                break

        os.makedirs('docs', exist_ok=True)
        with open('docs/stats.txt', 'w', encoding='utf-8') as f:
            f.write(
                f"[Standard Headhunting]\n"
                f"  Total Users    : {total_users}\n"
                f"  Total Pulls    : {total_pulls}\n"
                f"  Oroberyl Spent : {oroberyl_spent}\n"
                f"\n"
                f"  6-Star\n"
                f"    Rate         : {rate6}\n"
                f"    Count        : {count6}\n"
                f"    Median Pity  : {median_pity}\n"
                f"\n"
                f"  5-Startest\n"
                f"    Rate         : {rate5}\n"
                f"    Count        : {count5}\n"
            )
        print("Done")


scrape()
