from playwright.sync_api import sync_playwright
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

        // Featured character/weapon image - find img in the character card area
        // The card is the small box top-left with name + TOTAL OBTAINED
        let featured_img = null;
        const allImgs = Array.from(document.querySelectorAll('img'));
        // Log all img srcs for debugging
        const allSrcs = allImgs.map(i => i.getAttribute('src')).filter(s => s && !s.includes('miniIcon') && !s.includes('icon') && !s.includes('currencies') && !s.includes('banner'));
        // Try known operator path first
        for (const img of allImgs) {
            const src = img.getAttribute('src') || '';
            if (src.includes('/operators/preview/') || src.includes('/images/weapons/')) {
                featured_img = 'https://goyfield.moe' + src;
                break;
            }
        }
        // Fallback: find img that's inside the character card (near TOTAL OBTAINED text)
        if (!featured_img) {
            for (const el of document.querySelectorAll('*')) {
                if (el.innerText && el.innerText.trim() === 'TOTAL OBTAINED') {
                    const card = el.closest('div') || el.parentElement.parentElement;
                    const img = card ? card.querySelector('img') : null;
                    if (img) { featured_img = 'https://goyfield.moe' + img.getAttribute('src'); break; }
                }
            }
        }
        // Last resort: any img whose src has a path depth suggesting it's a preview image
        if (!featured_img && allSrcs.length > 0) {
            const candidate = allSrcs.find(s => s.split('/').length >= 4);
            if (candidate) featured_img = 'https://goyfield.moe' + candidate;
        }

        // Total Obtained: number shown in the featured character card
        // Try "TOTAL OBTAINED" label first, then any number near character name
        let total_obtained = null;

        // Strategy 1: find "TOTAL OBTAINED" label and grab nearby number
        for (const el of document.querySelectorAll('*')) {
            if (el.children.length === 0 && getText(el).includes('TOTAL OBTAINED')) {
                const parent = el.parentElement;
                const gp = parent.parentElement;
                // Check siblings
                for (const s of parent.children)
                    if (s !== el && getText(s).match(/^[0-9 ]+$/)) { total_obtained = getText(s).replace(/ /g,''); break; }
                // Check parent siblings
                if (!total_obtained) {
                    for (const c of gp.children)
                        if (c !== parent && getText(c).match(/^[0-9 ]+$/)) { total_obtained = getText(c).replace(/ /g,''); break; }
                }
                break;
            }
        }

        // Strategy 2: find any standalone number in the character card area
        // The card usually has: [img] [name] [TOTAL OBTAINED] [number]
        if (!total_obtained) {
            // Look for a div/section that has both a name-like text and a number
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

        // Featured character % = first % value in the 6-star list table
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

    # Click each and scrape
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
        browser = p.chromium.launch(headless=True,
            args=['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'])
        page = browser.new_page()
        page.goto("https://goyfield.moe/records/global", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(8000)

        result = {}

        # ── Standard Headhunting ─────────────────────────────────────────────
        page.locator('button:has-text("Special Headhunting")').first.click()
        page.wait_for_timeout(1000)
        page.get_by_text("Standard Headhunting", exact=True).click()
        page.wait_for_timeout(3000)
        result["Standard Headhunting"] = build_entry(get_stats(page))
        print("Standard Headhunting done")

        # ── Special Headhunting ──────────────────────────────────────────────
        page.locator('button:has-text("Standard Headhunting")').first.click()
        page.wait_for_timeout(1000)
        page.get_by_text("Special Headhunting", exact=True).click()
        page.wait_for_timeout(3000)
        print("Scraping Special Headhunting...")
        trigger = get_banner_trigger(page, exclude_text='Headhunting')
        result["Special Headhunting"] = scrape_sub_banners(page, trigger)

        # ── Event Weapon ─────────────────────────────────────────────────────
        page.locator('button:has-text("Special Headhunting")').first.click()
        page.wait_for_timeout(1000)
        page.get_by_text("Event Weapon", exact=True).click()
        page.wait_for_timeout(3000)
        print("Scraping Event Weapon...")
        trigger_weapon = get_banner_trigger(page, exclude_text='Event Weapon')
        result["Event Weapon"] = scrape_sub_banners(page, trigger_weapon)

        # ── Standard Weapon ──────────────────────────────────────────────────
        page.locator('button:has-text("Event Weapon")').first.click()
        page.wait_for_timeout(1000)
        page.get_by_text("Standard Weapon", exact=True).click()
        page.wait_for_timeout(3000)
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
