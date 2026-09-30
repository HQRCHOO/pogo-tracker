"""Open a page in headless Chromium, let its scripts finish, wait a little longer,
then return the final HTML, visible text and the page's buttons (text + disabled).

Some retailer pages (GameStop, Nintendo) ship a placeholder "in stock" state and only
swap in the real availability a second or two after loading, so a plain download
reads the placeholder. Needs `playwright` plus `python -m playwright install chromium`
(the poll workflow does both). Raises RenderUnavailable when Playwright isn't installed.
"""
from .util import BROWSER_UA


class RenderUnavailable(Exception):
    pass


def render(url, extra_wait=3.0, timeout=30):
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError as e:
        raise RenderUnavailable("playwright not installed") from e
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=BROWSER_UA, locale="en-US", viewport={"width": 1280, "height": 900})
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            if resp is not None and resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status}")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass  # busy pages never go fully idle; the extra wait below still applies
            page.wait_for_timeout(int(extra_wait * 1000))
            buttons = page.evaluate(r"""() => {
                const h1 = document.querySelector('h1');
                const hb = h1 ? h1.getBoundingClientRect() : null;
                const skip = /recommend|also-like|also_like|similar|carousel|related|upsell|cross-sell|footer|header|nav|menu/i;
                return Array.from(document.querySelectorAll('button, a[role=button], input[type=submit]')).map(e => {
                    const r = e.getBoundingClientRect();
                    let zone = '', n = e;
                    while (n && n !== document.body) {
                        const tag = n.tagName.toLowerCase(), cls = (typeof n.className === 'string' ? n.className : '') + ' ' + (n.id || '');
                        if (['nav', 'header', 'footer', 'aside'].includes(tag) || skip.test(cls)) { zone = 'aside'; break; }
                        n = n.parentElement;
                    }
                    return {
                        t: (e.innerText || e.value || '').trim().replace(/\s+/g, ' ').slice(0, 60),
                        d: !!(e.disabled || e.getAttribute('aria-disabled') === 'true' || /\bdisabled\b/.test(e.className)),
                        a: [e.id, typeof e.className === 'string' ? e.className : '', e.getAttribute('data-testid') || ''].join(' ').slice(0, 160),
                        dist: hb ? Math.round(Math.abs(r.top - hb.bottom) + Math.abs(r.left - hb.left) / 4) : 99999,
                        zone: zone, visible: r.width > 0 && r.height > 0
                    };
                });
            }""")
            return page.content(), page.inner_text("body"), buttons
        finally:
            browser.close()
