const { chromium } = require('@playwright/test');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    const logs = [];
    page.on('console', (m) => logs.push(`${m.type()}: ${m.text()}`));
    page.on('pageerror', (e) => logs.push(`PAGEERROR: ${e.message}`));
    page.on('requestfailed', (r) => logs.push(`REQFAIL: ${r.url()} ${r.failure()?.errorText}`));

    await page.goto('http://127.0.0.1:8765/film/the-dark-knight/');
    await page.locator('[data-open-video]').click();

    await page.waitForTimeout(4000);

    const loader = await page.locator('#video-loader').isVisible().catch(() => 'n/a');
    const video = page.locator('#video-el');
    const state = await video.evaluate((v) => ({
        paused: v.paused, readyState: v.readyState, currentSrc: v.currentSrc,
        error: v.error ? `${v.error.code} ${v.error.message}` : null,
    })).catch(() => null);
    const modalOpen = await page.locator('#video-modal').getAttribute('class');

    console.log('LOADER VISIBLE (4s):', loader);
    console.log('VIDEO STATE:', JSON.stringify(state));
    console.log('MODAL CLASS:', modalOpen);

    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    const loaderAfterClose = await page.locator('#video-loader').isVisible().catch(() => 'n/a');
    console.log('LOADER VISIBLE (after close):', loaderAfterClose);
    console.log('--- BROWSER LOGS ---');
    logs.forEach((l) => console.log(l));
    await browser.close();
})().catch((e) => { console.error('SCRIPT ERROR:', e); process.exit(1); });