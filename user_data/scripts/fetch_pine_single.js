#!/usr/bin/env node
/**
 * TradingView Pine Script Fetcher
 * Uses Playwright to fetch Pine Script source from TradingView pages
 *
 * Usage: node fetch_pine_single.js <script_url> <hash> <output_file>
 */

const { chromium } = require('/tmp/node_modules/playwright');
const fs = require('fs');

const CHROME_PATH = '/home/brian/.cache/puppeteer/chrome/linux-146.0.7680.153/chrome-linux64/chrome';

const args = process.argv.slice(2);
const url = args[0] || 'https://www.tradingview.com/script/532dzfsg-Hyperbolic-Hull-Moving-Average-HHMA-QuantAlgo/';
const hash = args[1] || '532dzfsg';
const outFile = args[2] || '/home/brian/freqtrade/user_data/.tv_scout/playwright_scripts/' + hash + '.pine';

async function fetchPineScript() {
  console.log('Fetching Pine Script: ' + hash);
  console.log('URL: ' + url);
  console.log('Output: ' + outFile);

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
    } else {
      console.log('No Source code button found');
    }

    // Extract source
    const bodyText = await page.evaluate(() => document.body.innerText);

    if (bodyText.includes('@version=')) {
      const idx = bodyText.indexOf('@version=');
      const source = bodyText.slice(idx, idx + 15000);

      // Ensure directory exists
      const dir = outFile.substring(0, outFile.lastIndexOf('/'));
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      fs.writeFileSync(outFile, source);
      console.log('SUCCESS: ' + hash + ' (' + source.length + ' chars)');
    } else if (bodyText.includes('Pro') || bodyText.includes('Premium') || bodyText.includes('source is not published')) {
      console.log('PRO/CLOSED: ' + hash);
    } else {
      console.log('NO_CODE: ' + hash);
      // Save page for debugging
      fs.writeFileSync(outFile.replace('.pine', '_page.txt'), bodyText.slice(0, 5000));
    }

  } catch(e) {
    console.log('ERR: ' + hash + ' - ' + e.message.slice(0, 100));
  }

  await browser.close();
}

fetchPineScript().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
