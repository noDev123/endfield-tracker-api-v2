from playwright.sync_api import sync_playwright
import re
import json
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

        # Wait for JS to hydrate the page
        page.wait_for_timeout(8000)

        # ── Get banner tab names ──────────────────────────────────────────────
        # Tabs are rendered as clickable elements in the Global Statistics section
        tab_elements = page.locator('button, [role="tab"]').all()
        banner_names = []
        for tab in tab_elements:
            name = tab.inner_text().strip()
            if name and name not in ('', 'Dark', 'English'):
                banner_names.append(name)

        # Fallback: read from visible text if no tab elements found
        if not banner_names:
            body = page.inner_text("body")
            # Known banner sections on goyfield
            for candidate in ['Special Headhunting', 'Standard Headhunting', 'Crossover Headhunting']:
                if candidate in body:
                    banner_names.append(candidate)

        stats = {}
        banners = []

        for name in banner_names:
            try:
                # Click the banner tab
                page.locator(f'button:has-text("{name}"), [role="tab"]:has-text("{name}")').first.click()
                page.wait_for_timeout(2000)
            except Exception:
                pass

            content = page.inner_text("body")

            # ── Overview ─────────────────────────────────────────────────────
            users_match  = re.search(r'Total Users\s*\n\s*([\d\s,]+)', content)
            pulls_match  = re.search(r'Total Pulls\s*\n\s*([\d\s,]+)', content)
            oro_match    = re.search(r'Oroberyl Spent\s*\n.*?\n\s*([\d\s,]+)', content)

            # ── 6★ stats ─────────────────────────────────────────────────────
            rate6_match  = re.search(r'6 Stats\s*\n.*?Rate\s*\n\s*([\d.]+%)', content, re.DOTALL)
            count6_match = re.search(r'6 Stats\s*\n.*?Count\s*\n\s*([\d\s,]+)', content, re.DOTALL)
            pity6_match  = re.search(r'Median Pity\s*\n\s*([\d]+)', content)

            # ── 5★ stats ─────────────────────────────────────────────────────
            rate5_match  = re.search(r'5 Stats\s*\n.*?Rate\s*\n\s*([\d.]+%)', content, re.DOTALL)
            count5_match = re.search(r'5 Stats\s*\n.*?Count\s*\n\s*([\d\s,]+)', content, re.DOTALL)

            def g(m, grp=1):
                return m.group(grp).strip().replace('\n', '').replace(' ', '') if m else 'N/A'

            banner_data = {
                'name':           name,
                'total_users':    g(users_match),
                'total_pulls':    g(pulls_match),
                'oroberyl_spent': g(oro_match),
                '6star_rate':     g(rate6_match),
                '6star_count':    g(count6_match),
                '6star_median_pity': g(pity6_match),
                '5star_rate':     g(rate5_match),
                '5star_count':    g(count5_match),
            }
            banners.append(banner_data)

            # Store Standard Headhunting as top-level for easy access
            if 'Standard' in name:
                stats['total_pulls']    = banner_data['total_pulls']
                stats['total_users']    = banner_data['total_users']
                stats['oroberyl_spent'] = banner_data['oroberyl_spent']
                stats['6star_rate']     = banner_data['6star_rate']
                stats['6star_count']    = banner_data['6star_count']
                stats['6star_median_pity'] = banner_data['6star_median_pity']
                stats['5star_rate']     = banner_data['5star_rate']
                stats['5star_count']    = banner_data['5star_count']

        stats['banners'] = banners
        browser.close()
        return stats


# ── Run ───────────────────────────────────────────────────────────────────────
data = scrape()

# Format banner line like friend's style
banner_parts = []
for b in data['banners']:
    banner_parts.append(
        f"{{{b['name']}, {b['total_pulls']} pulls, "
        f"{b['6star_rate']} 6-star, {b['5star_rate']} 5-star, "
        f"{b['total_users']} users}}"
    )
banner_line = ', '.join(banner_parts) if banner_parts else 'Not found'

# Write to docs/stats.txt
os.makedirs('docs', exist_ok=True)
with open('docs/stats.txt', 'w', encoding='utf-8') as f:
    f.write(
        f"total-pulls: {data.get('total_pulls', 'N/A')}\n"
        f"total-users: {data.get('total_users', 'N/A')}\n"
        f"oroberyl-spent: {data.get('oroberyl_spent', 'N/A')}\n"
        f"6star-rate: {data.get('6star_rate', 'N/A')}\n"
        f"6star-count: {data.get('6star_count', 'N/A')}\n"
        f"6star-median-pity: {data.get('6star_median_pity', 'N/A')}\n"
        f"5star-rate: {data.get('5star_rate', 'N/A')}\n"
        f"5star-count: {data.get('5star_count', 'N/A')}\n"
        f"\nheadhunt-banners: {banner_line}\n"
    )

print("Done:", json.dumps(data, indent=2, ensure_ascii=False))