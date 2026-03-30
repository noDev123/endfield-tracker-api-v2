from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import json
import os
import time


def get_stats(page):
    return page.evaluate("""() => {
        function getText(el) { return el.innerText ? el.innerText.trim() : ''; }
        function getValueNear(label) {
            for (const el of document.querySelectorAll('*')) {
                if (el.children.length > 0) continue;
                if (getText(el) === label) {
                    for (const s of el.parentElement.children)
                        if (s !== el && getText(s)) return getText(s);
                    for (const c of el.parentElement.parentElement.children)
                        if (c !== el.parentElement && getText(c)) return getText(c);
                }
            }
            return null;
        }
        function getStarSection(n) {
            for (const el of document.querySelectorAll('*')) {
                const t = getText(el);
                if (t.startsWith(String(n)) && t.includes('Stats') && el.children.length <= 3) {
                    const leaves = [...el.closest('section,div').querySelectorAll('*')]
                        .filter(e => e.children.length === 0 && getText(e));
                    let rate=null, count=null, pity=null, won=null;
                    for (let i=0; i<leaves.length; i++) {
                        const t=getText(leaves[i]), nx=leaves[i+1]?getText(leaves[i+1]):null;
                        if (t==='Rate'&&!rate) rate=nx;
                        if (t==='Count'&&!count) count=nx;
                        if (t==='Median Pity'&&!pity) pity=nx;
                        if ((t==='Won 50:50'||t==='Won 25:75')&&!won) won=nx;
                    }
                    if (rate||count||pity) return {rate,count,pity,won};
                }
            }
            return {rate:null,count:null,pity:null,won:null};
        }
        const six=getStarSection(6), five=getStarSection(5);

        let featured_img = null;
        const allImgs = Array.from(document.querySelectorAll('img'));
        const allSrcs = allImgs.map(i => i.getAttribute('src')).filter(s => s && !s.includes('miniIcon') && !s.includes('icon') && !s.includes('currencies') && !s.includes('banner'));
        for (const img of allImgs) {
            const src = img.getAttribute('src') || '';
            if (src.includes('/operators/preview/') || src.includes('/images/weapons/')) {
                featured_img = 'https://goyfield.moe' + src;
                break;
            }
        }
        if (!featured_img) {
            for (const el of document.querySelectorAll('*')) {
                if (el.innerText && el.innerText.trim() === 'TOTAL OBTAINED') {
                    const card = el.closest('div') || el.parentElement.parentElement;
                    const img = card ? card.querySelector('img') : null;
                    if (img) { featured_img = 'https://goyfield.moe' + img.getAttribute('src'); break; }
                }
            }
        }
        if (!featured_img && allSrcs.length > 0) {
            const candidate = allSrcs.find(s => s.split('/').length >= 4);
            if (candidate) featured_img = 'https://goyfield.moe' + candidate;
        }

        let total_obtained = null;
        for (const el of document.querySelectorAll('*')) {
            if (el.children.length === 0 && getText(el).includes('TOTAL OBTAINED')) {
                const parent = el.parentElement;
                const gp = parent.parentElement;
                for (const s of parent.children)
                    if (s !== el && getText(s).match(/^[0-9 ]+$/)) { total_obtained = getText(s).replace(/ /g,''); break; }
                if (!total_obtained) {
                    for (const c of gp.children)
                        if (c !== parent && getText(c).match(/^[0-9 ]+$/)) { total_obtained = getText(c).replace(/ /g,''); break; }
                }
                break;
            }
        }
        if (!total_obtained) {
            const cards = [...document.querySelectorAll('div, section')].filter(el => {
                const t = el.innerText || '';
                return t.includes('TOTAL') || t.includes('Total Obtained') || t.includes('obtained');
            });
            for (const card of cards) {
                const leaves = [...card.querySelectorAll('*')].filter(e => e.children.length === 0 && getText(e));
                for (const leaf of leaves) {
                    if (getText(leaf).match(/^[0-9 ]{1,6}$/) && parseInt(getText(leaf).replace(/ /g,'')) > 0) {
                        total_obtained = getText(leaf).replace(/ /g,'');
                        break;
                    }
                }
                if (total_obtained) break;
            }
        }

        let featured_pct = null;
        for (const el of document.querySelectorAll('*')) {
            if (el.children.length === 0) {
                const t = getText(el);
                if (t.match(/^[0-9]+[.][0-9]+%$/) && !featured_pct) {
                    featured_pct = t;
                    break;
                }
            }
        }

        return {
            total_users: getValueNear('Total Users'),
            total_pulls: getValueNear('Total Pulls'),
            oroberyl_spent: getValueNear('Oroberyl Spent'),
            total_obtained,
            rate6:six.rate, count6:six.count, pity6:six.pity, won6:six.won,
            rate5:five.rate, count5:five.count,
            featured_pct,
            featured_img,
        };
    }""")


def clean(v):
    if v is None: return None
    n = v.replace(' ','').replace(',','').replace('\xa0','').replace('\u202f','')
    try: return int(n)
    except:
        try: return float(n)
        except: return v


def build_entry(raw, include_obtained=False):
    entry = {
        "Total Users":    clean(raw.get('total_users')),
        "Total Pulls":    clean(raw.get('total_pulls')),
        "Oroberyl Spent": clean(raw.get('oroberyl_spent')),
        "6-Star": {
            "Rate":        raw.get('rate6'),
            "Count":       clean(raw.get('count6')),
            "Median Pity": clean(raw.get('pity6')),
            "Won":         raw.get('won6')
        },
        "5-Star": {"Rate": raw.get('rate5'), "Count": clean(raw.get('count5'))}
    }
    if include_obtained:
        entry["Total Obtained"] = clean(raw.get('total_obtained'))
        entry["Featured 6-Star %"] = raw.get('featured_pct')
        entry["Featured Image"] = raw.get('featured_img')
    return entry


def switch_banner_type(page, target: str, timeout=15000):
    """
    Click the banner-type tab/button for `target`.
    Tries up to 3 times in case the dropdown closes before the click lands.
    """
    for attempt in range(3):
        try:
            # Find any visible button that currently acts as the type selector
            # (the one whose dropdown contains our target).
            # Open whatever selector is currently shown.
            selector_btn = page.locator('button').filter(has_not=page.locator('img')).first
            selector_btn.click(timeout=5000)
            # Wait for the list item to appear
            item = page.get_by_text(target, exact=True)
            item.wait_for(state="visible", timeout=timeout)
            item.click()
            page.wait_for_timeout(3000)
            print(f"  Switched to: {target}")
            return
        except PWTimeout:
            print(f"  switch_banner_type attempt {attempt+1} timed out, retrying…")
            page.wait_for_timeout(2000)
    raise RuntimeError(f"Could not switch to banner type '{target}' after 3 attempts")


def get_banner_trigger(page, exclude_text='Headhunting'):
    """Get the banner dropdown trigger button (has img, not the type selector)."""
    return page.locator('button').filter(has=page.locator('img')).filter(has_not_text=exclude_text).first


def scrape_sub_banners(page, trigger):
    """Generic: scrape all sub-banners from a dropdown trigger. Returns dict of {name: data}."""
    result = {}

    # Scrape the default (already selected) banner first without clicking
    default_banner = trigger.inner_text().strip()
    print(f"  Default: {default_banner}")
    result[default_banner] = build_entry(get_stats(page), include_obtained=True)
    print(f"    done")

    # Open dropdown and get other banner names
    trigger.click()
    page.wait_for_timeout(2000)

    other_banners = []
    for li in page.locator('li').all():
        name = li.inner_text().strip()
        if name and len(name) > 1 and name != default_banner:
            other_banners.append(name)

    print(f"  Others: {other_banners}")

    for name in other_banners:
        try:
            if not page.locator('li').first.is_visible():
                trigger.click()
                page.wait_for_timeout(2000)
            for li in page.locator('li').all():
                if name in li.inner_text():
                    li.click()
                    break
            page.wait_for_timeout(3000)
            result[name] = build_entry(get_stats(page), include_obtained=True)
            print(f"    {name} done")
        except Exception as e:
            print(f"    {name} error: {e}")
            result[name] = None

    return result


def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = browser.new_page()
        page.goto("https://goyfield.moe/records/global", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(8000)

        result = {}

        # ── Standard Headhunting ─────────────────────────────────────────────
        switch_banner_type(page, "Standard Headhunting")
        result["Standard Headhunting"] = build_entry(get_stats(page))
        print("Standard Headhunting done")

        # ── Special Headhunting ──────────────────────────────────────────────
        switch_banner_type(page, "Special Headhunting")
        print("Scraping Special Headhunting...")
        trigger = get_banner_trigger(page, exclude_text='Headhunting')
        result["Special Headhunting"] = scrape_sub_banners(page, trigger)

        # ── Event Weapon ─────────────────────────────────────────────────────
        switch_banner_type(page, "Event Weapon")
        print("Scraping Event Weapon...")
        trigger_weapon = get_banner_trigger(page, exclude_text='Event Weapon')
        result["Event Weapon"] = scrape_sub_banners(page, trigger_weapon)

        # ── Standard Weapon ──────────────────────────────────────────────────
        switch_banner_type(page, "Standard Weapon")
        print("Scraping Standard Weapon...")
        trigger_std_weapon = get_banner_trigger(page, exclude_text='Standard Weapon')
        result["Standard Weapon"] = scrape_sub_banners(page, trigger_std_weapon)

        browser.close()

        os.makedirs('docs', exist_ok=True)
        with open('docs/stats.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\nDone:")
        print(json.dumps(result, indent=2, ensure_ascii=False))


scrape()
