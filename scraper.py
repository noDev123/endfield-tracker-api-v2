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

        # It's a DROPDOWN - select "Standard Headhunting"
        try:
            # Try native <select>
            page.select_option('select', label='Standard Headhunting')
            page.wait_for_timeout(3000)
        except Exception:
            try:
                # Custom dropdown: click it to open, then click the option
                page.locator('[class*="dropdown"], [class*="select"]').first.click()
                page.wait_for_timeout(1000)
                page.get_by_text("Standard Headhunting", exact=True).click()
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"Warning: dropdown select failed: {e}")

        # Wait for real values to appear (not 0)
        try:
            page.wait_for_function("""
                () => {
                    const text = document.body.innerText;
                    return text.includes('176') || text.includes('1 6');
                }
            """, timeout=15000)
        except Exception:
            pass

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
