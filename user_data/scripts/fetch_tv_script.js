#!/usr/bin/env node
/**
 * TradingView Strategy Scout - Playwright Fetch Module
 * Uses Playwright to fetch Pine Script source from TradingView pages
 */

const { chromium } = require('/tmp/node_modules/playwright');
const fs = require('fs');

const CHROME_PATH = '/home/brian/.cache/puppeteer/chrome/linux-146.0.7680.153/chrome-linux64/chrome';

const url = process.argv[2] || 'https://www.tradingview.com/script/532dzfsg-Hyperbolic-Hull-Moving-Average-HHMA-QuantAlgo/';
const hash = process.argv[3] || '532dzfsg';
const outFile = process.argv[4] || '/tmp/pine_test.pine';

async function fetchPineScript() {
  console.log(`Fetching ${hash} from ${url}...`);

  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME_PATH
  });

  const page = await browser.newPage();

  try {
    await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });
    await page.waitForTimeout(3000);

    // Click Source code button
    const btn = await page.$('button:has-text("Source code")');
    if (btn) {
      await btn.click();
      await page.waitForTimeout(5000);
      console.log('Clicked Source code button');
    }

    // Extract source
    const bodyText = await page.evaluate(() => document.body.innerText);

    if (bodyText.includes('@version=')) {
      const idx = bodyText.indexOf('@version=');
      const source = bodyText.slice(idx, idx + 15000);
      fs.writeFileSync(outFile, source);
      console.log(`FOUND: ${hash} (${source.length} chars)`);
    } else if (bodyText.includes('Pro') || bodyText.includes('Premium')) {
      console.log(`PRO: ${hash} - Closed source`);
    } else {
      console.log(`NOCODE: ${hash} - No code found`);
    }

  } catch(e) {
    console.log(`ERR: ${hash} - ${e.message.slice(0, 100)}`);
  }

  await browser.close();
}

fetchPineScript();
