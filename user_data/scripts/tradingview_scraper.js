#!/usr/bin/env node
/**
 * TradingView Scripts Page Scraper
 * Scrapes ALL scripts from TradingView scripts page (strategy + indicators)
 * for conversion to Freqtrade strategies
 *
 * Usage: node tradingview_scraper.js [--pages N]
 */

const { chromium } = require('/home/brian/.npm/_npx/a80a913f4f8f2557/node_modules/playwright');

const CHROME_PATH = '/home/brian/.cache/puppeteer/chrome/linux-146.0.7680.153/chrome-linux64/chrome';
const OUT_DIR = '/home/brian/freqtrade/user_data/.tv_scout';
const SCRAPE_LIST_PATH = OUT_DIR + '/tv_scripts_page.json';

// P1-IMPROVE (2026-06-12): switch to strategy-only filter that TradingView actually honors.
// Verified by direct fetch: 19 scripts, ~63% have "Strategy" in slug (vs 0% on default recent page).
// Note: TradingView's script_type=strategies filter does NOT paginate (page=2 returns same 19),
// so bumping pages gives a slightly deeper recent pool but limited diversity.
const PAGE_URL = 'https://www.tradingview.com/scripts/?script-source-pub=public&sort=recent_extended&script_type=strategies';
const args = process.argv.slice(2);
const pagesArg = args.find(function(a) { return a.startsWith('--pages='); });
const PAGES_TO_SCRAPE = pagesArg ? parseInt(pagesArg.split('=')[1]) : 3;

async function scrapeTVScripts() {
  console.log('=== TradingView Scripts Scraper (Playwright) ===\n');
  console.log(`Target: ${PAGE_URL}`);
  console.log(`Pages: ${PAGES_TO_SCRAPE}\n`);

  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME_PATH
  });

  const page = await browser.newPage();
  const allScripts = [];

  for (let pageNum = 1; pageNum <= PAGES_TO_SCRAPE; pageNum++) {
    const url = pageNum === 1 ? PAGE_URL : `${PAGE_URL}&page=${pageNum}`;
    console.log(`[Page ${pageNum}/${PAGES_TO_SCRAPE}] Navigating...`);
    await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });
    await page.waitForTimeout(5000);

    // Scroll to bottom to load all scripts
    console.log(`[Page ${pageNum}] Scrolling to load content...`);
    for (let scroll = 0; scroll < 10; scroll++) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(2000);

      // Try to click "Load more" button if exists
      try {
        const loadMoreBtn = await page.$('button[class*="load"]');
        if (loadMoreBtn) {
          console.log(`[Page ${pageNum}] Clicking Load more...`);
          await loadMoreBtn.click();
          await page.waitForTimeout(3000);
        }
      } catch (e) {}
    }

    // Extract all script URLs
    const scripts = await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('a[href*="/script/"]'));
      return links
        .map(a => a.href.split('?')[0].split('#')[0])
        .filter(h => h.match(/tradingview\.com\/script\/[A-Za-z0-9]+-.+/))
        .filter((v, i, a) => a.indexOf(v) === i); // unique
    });

    console.log(`[Page ${pageNum}] Found ${scripts.length} scripts`);
    allScripts.push(...scripts.map(s => ({ url: s, page: pageNum })));
  }

  await browser.close();

  // Deduplicate
  const unique = allScripts.filter((v, i, a) => a.findIndex(s => s.url === v.url) === i);

  console.log(`\n=== Total: ${unique.length} unique scripts (${PAGES_TO_SCRAPE} page(s)) ===\n`);

  // Save full URL list (new URLs at FRONT so Phase 2 head-N picks the freshest).
  // P1-IMPROVE (2026-06-12): was appending new to end of existing, but Phase 2 uses
  // `head -N TV_PHASE2_MAX` to grab freshest URLs, so append-at-end meant the head
  // always re-grabbed the OLDEST entries (mostly already-PRO or already-converted).
  const fs = require('fs');
  const existing = fs.existsSync(SCRAPE_LIST_PATH) ? JSON.parse(fs.readFileSync(SCRAPE_LIST_PATH, 'utf8')) : [];
  const existingUrls = new Set(existing.map(s => typeof s === 'string' ? s : s.url));
  const newScripts = unique.filter(s => !existingUrls.has(s.url));
  const combined = [
    ...newScripts.map(s => ({ url: s.url, page: s.page })),
    ...existing.map(s => typeof s === 'string' ? { url: s, page: 0 } : s)
  ];

  fs.writeFileSync(SCRAPE_LIST_PATH, JSON.stringify(combined, null, 2));
  console.log(`Saved to ${SCRAPE_LIST_PATH}`);
  console.log(`New scripts this run: ${newScripts.length}`);
  console.log(`Total collected: ${combined.length}`);

  return combined;
}

// Run
scrapeTVScripts().catch(e => {
  console.error('Error:', e);
  process.exit(1);
});
