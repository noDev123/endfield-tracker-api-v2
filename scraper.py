from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import json
import os

BANNER_TYPES = ["Special Headhunting", "Standard Headhunting", "Event Weapon", "Standard Weapon"]
SCREENSHOT_DIR = "debug_screenshots"


def save_screenshot(page, name):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    print(f"  [screenshot] {path}")


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
        if (!featured_img) {
            const allSrcs = allImgs.map(i => i.getAttribute('src')).filter(s => s
                && !s.includes('miniIcon') && !s.includes('icon')
                && !s.includes('currencies') && !s.includes('banner'));
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
                if (t.match(/^[0-9]+[.][0-9]+%$/) && !featured_pct) { featured_pct = t; break; }
            }
        }

        return {
            total_users: getValueNear('Total Users'),
            total_pulls: getValueNear('Total Pulls'),
            oroberyl_spent: getValueNear('Oroberyl Spent'),
            total_obtained,
            rate6:six.rate, count6:six.count, pity6:six.pity, won6:six.won,
            rate5:five.rate, count5:five.count,
            featured_pct, featured_img,
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


def js_click_by_text(page, target: str) -> bool:
    """
    Use JavaScript to find and click any visible element whose trimmed
    innerText exactly matches `target`. Works regardless of element type
    (div, button, li, span, etc.) — no Playwright locator assumptions needed.
    """
    return page.evaluate("""(target) => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            if (el.children.length > 0) continue;  // leaf nodes only
            const text = (el.innerText || '').trim();
            if (text === target) {
                el.click();
                return true;
            }
        }
        // Second pass: allow parent elements (e.g. button wrapping a span)
        for (const el of all) {
            const text = (el.innerText || '').trim();
            if (text === target) {
                el.click();
                return true;
            }
        }
        return false;
    }""", target)


def dump_visible_texts(page):
    """Print all unique short leaf-node texts — helps diagnose what's on screen."""
    texts = page.evaluate("""() => {
        const seen = new Set();
        for (const el of document.querySelectorAll('*')) {
            if (el.children.length > 0) continue;
            const t = (el.innerText || '').trim();
            if (t && t.length < 60) seen.add(t);
        }
        return [...seen].slice(0, 80);
    }""")
    print("  [DOM texts]", texts)


def get_type_selector(page):
    """Find the banner-type selector button by matching known type names."""
    for t in BANNER_TYPES:
        btn = page.locator(f'button:has-text("{t}")').first
        if btn.is_visible():
            return btn, t
    raise RuntimeError("Could not find the banner-type selector button")


def switch_banner_type(page, target: str):
    """
    Switch to a banner type tab. Strategy:
      1. Find which type is currently shown and click its button to open the picker.
      2. Wait 3s for the picker to render.
      3. Use JS to click any element whose text exactly matches `target`
         (avoids assumptions about li/div/button element type).
      4. Verify the switch worked; retry up to 3 times.
    """
    for attempt in range(3):
        btn, current = get_type_selector(page)
        if current == target:
            print(f"  Already on: {target}")
            return

        print(f"  Opening picker (current='{current}', want='{target}')…")
        btn.click()
        page.wait_for_timeout(3000)  # give the picker time to render

        save_screenshot(page, f"picker_open_attempt{attempt+1}_{target.replace(' ','_')}")
        dump_visible_texts(page)

        clicked = js_click_by_text(page, target)
        if clicked:
            page.wait_for_timeout(3000)
            # Verify the switch actually happened
            _, new_current = get_type_selector(page)
            if new_current == target:
                print(f"  Switched to: {target}")
                return
            print(f"  Click landed but still on '{new_current}', retrying…")
        else:
            print(f"  js_click_by_text could not find '{target}' in DOM, retrying…")
            page.wait_for_timeout(2000)

    save_screenshot(page, f"switch_failed_{target.replace(' ','_')}")
    raise RuntimeError(f"Could not switch to banner type '{target}' after 3 attempts")


def get_sub_banner_trigger(page):
    """
    Sub-banner selector: a button with an <img> whose text isn't a banner type name.
    """
    for btn in page.locator('button').filter(has=page.locator('img')).all():
        text = btn.inner_text().strip()
        if not any(t in text for t in BANNER_TYPES):
            return btn
    raise RuntimeError("Could not find sub-banner trigger button")


def scrape_sub_banners(page, trigger):
    """Scrape all sub-banners from a dropdown trigger."""
    result = {}

    default_banner = trigger.inner_text().strip()
    print(f"  Default sub-banner: {default_banner}")
    result[default_banner] = build_entry(get_stats(page), include_obtained=True)
    print(f"    done")

    trigger.click()
    page.wait_for_timeout(2000)

    other_banners = []
    # Try li first, fall back to any visible short-text elements in a popup
    lis = page.locator('li').all()
    candidates = lis if lis else []
    for li in candidates:
        name = li.inner_text().strip()
        if name and len(name) > 1 and name != default_banner:
            other_banners.append(name)

    # Fallback: JS scan for new popup items
    if not other_banners:
        other_banners = page.evaluate(f"""(defaultBanner) => {{
            const names = [];
            for (const el of document.querySelectorAll('li, [role="option"], [role="menuitem"]')) {{
                const t = (el.innerText || '').trim();
                if (t && t.length > 1 && t !== defaultBanner) names.push(t);
            }}
            return [...new Set(names)];
        }}""", default_banner)

    print(f"  Other sub-banners: {other_banners}")

    for name in other_banners:
        try:
            # Re-open dropdown if closed
            if not page.locator('li').first.is_visible():
                trigger.click()
                page.wait_for_timeout(2000)

            clicked = js_click_by_text(page, name)
            if not clicked:
                # fallback: find li containing the name
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
        save_screenshot(page, "00_page_loaded")

        result = {}

        # ── Standard Headhunting ─────────────────────────────────────────────
        switch_banner_type(page, "Standard Headhunting")
        result["Standard Headhunting"] = build_entry(get_stats(page))
        print("Standard Headhunting done")

        # ── Special Headhunting ──────────────────────────────────────────────
        switch_banner_type(page, "Special Headhunting")
        print("Scraping Special Headhunting...")
        result["Special Headhunting"] = scrape_sub_banners(page, get_sub_banner_trigger(page))

        # ── Event Weapon ─────────────────────────────────────────────────────
        switch_banner_type(page, "Event Weapon")
        print("Scraping Event Weapon...")
        result["Event Weapon"] = scrape_sub_banners(page, get_sub_banner_trigger(page))

        # ── Standard Weapon ──────────────────────────────────────────────────
        switch_banner_type(page, "Standard Weapon")
        print("Scraping Standard Weapon...")
        result["Standard Weapon"] = scrape_sub_banners(page, get_sub_banner_trigger(page))

        browser.close()

        os.makedirs('docs', exist_ok=True)
        with open('docs/stats.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\nDone:")
        print(json.dumps(result, indent=2, ensure_ascii=False))


scrape()
