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
            wait_until="domcontentloaded",
            timeout=60000
        )
        page.wait_for_timeout(8000)

        # Click the Standard Headhunting tab
        clicked = False
        for sel in [
            'button:has-text("Standard Headhunting")',
            '[role="tab"]:has-text("Standard Headhunting")',
            'a:has-text("Standard Headhunting")',
            'li:has-text("Standard Headhunting")',
            'div[class*="tab"]:has-text("Standard Headhunting")',
            'span[class*="tab"]:has-text("Standard Headhunting")',
        ]:
            try:
                el = page.locator(sel).first
                el.wait_for(state="visible", timeout=3000)
                el.click()
                page.wait_for_timeout(2000)
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            try:
                page.get_by_text("Standard Headhunting", exact=True).first.click()
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"Warning: could not click Standard Headhunting tab: {e}")

        content = page.inner_text("body")

        # Debug snapshot
        print("=== RAW BODY (first 3000 chars) ===")
        print(content[:3000])
        print("====================================")

        browser.close()

        # Parse
        lines = [l.strip().replace('\xa0', '').replace('\u202f', '') for l in content.splitlines()]
        lines = [l for l in lines if l]

        def after(label, offset=1):
            for i, l in enumerate(lines):
                if l == label:
                    t = i + offset
                    return lines[t] if t < len(lines) else 'N/A'
            return 'N/A'

        total_users    = after('Total Users')
        total_pulls    = after('Total Pulls')
        oroberyl_spent = after('Oroberyl Spent', offset=2)
        if not re.match(r'^[\d\s,]+$', oroberyl_spent):
            oroberyl_spent = after('Oroberyl Spent', offset=1)

        rate6 = count6 = median_pity = 'N/A'
        for i, l in enumerate(lines):
            if re.match(r'^6.{0,3}Stats$', l):
                for j in range(i + 1, min(i + 20, len(lines))):
                    if re.match(r'^5.{0,3}Stats$', lines[j]): break
                    if lines[j] == 'Rate'        and j+1 < len(lines): rate6       = lines[j+1]
                    if lines[j] == 'Count'       and j+1 < len(lines): count6      = lines[j+1]
                    if lines[j] == 'Median Pity' and j+1 < len(lines): median_pity = lines[j+1]
                break

        rate5 = count5 = 'N/A'
        for i, l in enumerate(lines):
            if re.match(r'^5.{0,3}Stats$', l):
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
                f"  5-Star\n"
                f"    Rate         : {rate5}\n"
                f"    Count        : {count5}\n"
            )
        print("Done")


scrape()
