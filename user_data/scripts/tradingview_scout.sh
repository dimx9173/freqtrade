#!/bin/bash
# ============================================================
# TradingView Strategy Scout v5
# Uses tradingview_scraper.js to fetch from /scripts/?sort=recent_extended
# then converts to Freqtrade strategies
# ============================================================

OUT_DIR="/home/brian/freqtrade/user_data/.tv_scout"
STRAT_DIR="/home/brian/freqtrade/user_data/strategies/test"
PLAYWRIGHT_SCRIPTS="$OUT_DIR/playwright_scripts"
SCRIPT_DIR="/home/brian/freqtrade/user_data/scripts"
SCRAPE_LIST="$OUT_DIR/tv_scripts_page.json"
CHROME_PATH="/home/brian/.cache/puppeteer/chrome/linux-146.0.7680.153/chrome-linux64/chrome"

mkdir -p "$OUT_DIR" "$PLAYWRIGHT_SCRIPTS"

echo "=== TradingView Strategy Scout v5 ==="
echo "時間: $(date -u '+%Y-%m-%d %H:%M UTC')"
echo ""

# Phase 1: Scrape scripts from /scripts/?sort=recent_extended
echo "[Phase 1] 抓取最近腳本..."
if [ ! -f "$SCRAPE_LIST" ]; then
    node "$SCRIPT_DIR/tradingview_scraper.js" --pages=2
fi
total=$(python3 -c "import json; d=json.load(open('$SCRAPE_LIST')); print(len(d))" 2>/dev/null || echo 0)
echo "Scraper 發現 $total 個腳本"

# Phase 2: Count .pine files and unconverted hashes
echo ""
echo "[Phase 2] 待轉換狀態..."
pine_count=$(ls "$OUT_DIR"/*.pine 2>/dev/null | wc -l)
echo "已有 Pine Scripts: $pine_count"

# Phase 3: Fetch Pine Scripts using Playwright
echo ""
echo "[Phase 3] 使用 Playwright 抓取原始碼..."

# Build URL list from tv_scripts_page.json
URL_LIST="/tmp/tv_urls_${$}.txt"
python3 -c "
import json
d = json.load(open('$SCRAPE_LIST'))
for item in d:
    url = item['url'] if isinstance(item, dict) else item
    print(url)
" > "$URL_LIST"

# Create Node.js fetch script
cat > /tmp/fetch_pine_v5.js << 'NODESCRIPT'
const { chromium } = require('/tmp/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/home/brian/.cache/puppeteer/chrome/linux-146.0.7680.153/chrome-linux64/chrome';
const OUT_DIR = '/home/brian/freqtrade/user_data/.tv_scout/playwright_scripts';
const urlList = process.argv[2] || '/tmp/tv_urls.txt';

const urls = fs.readFileSync(urlList, 'utf8').trim().split('\n');

async function fetchAll() {
  const browser = await chromium.launch({ headless: true, executablePath: CHROME_PATH });
  let done = 0, skipped = 0, error = 0;

  for (const url of urls) {
    const hash = url.match(/\/script\/([A-Za-z0-9]+)-/)?.[1];
    if (!hash) continue;

    const outFile = path.join(OUT_DIR, hash + '.pine');
    if (fs.existsSync(outFile)) {
      console.log('SKIP: ' + hash);
      skipped++;
      continue;
    }

    try {
      const page = await browser.newPage();
      await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });
      await page.waitForTimeout(3000);

      const btn = await page.$('button:has-text("Source code")');
      if (btn) { await btn.click(); await page.waitForTimeout(5000); }

      const bodyText = await page.evaluate(() => document.body.innerText);

      if (bodyText.includes('@version=')) {
        const idx = bodyText.indexOf('@version=');
        const source = bodyText.slice(idx, idx + 15000);
        fs.writeFileSync(outFile, source);
        console.log('FOUND: ' + hash + ' (' + source.length + ' chars)');
        done++;
      } else if (bodyText.includes('Pro') || bodyText.includes('Premium')) {
        console.log('PRO: ' + hash);
      } else {
        console.log('NOCODE: ' + hash);
      }
      await page.close();
    } catch(e) {
      console.log('ERR: ' + hash + ' - ' + e.message.slice(0, 80));
      error++;
    }
  }

  await browser.close();
  console.log('\nDone! Found: ' + done + ', Skipped: ' + skipped + ', Error: ' + error);
}

fetchAll().catch(e => { console.error(e); process.exit(1); });
NODESCRIPT

# Run fetch (limit to 20 per run)
head -5 "$URL_LIST" > /tmp/tv_urls_batch.txt
node /tmp/fetch_pine_v5.js /tmp/tv_urls_batch.txt 2>&1

# Phase 4: Copy to main .tv_scout directory
echo ""
echo "[Phase 4] 整理抓取結果..."
cp "$PLAYWRIGHT_SCRIPTS"/*.pine "$OUT_DIR/" 2>/dev/null
api_success=$(ls "$PLAYWRIGHT_SCRIPTS"/*.pine 2>/dev/null | wc -l)
echo "Playwright 成功: $api_success 個"

# Phase 5: List pending conversions
echo ""
echo "[Phase 5] 待轉換..."
count=0
for pine in "$OUT_DIR"/*.pine; do
    [ -f "$pine" ] || continue
    h=$(basename "$pine" .pine)
    strat_file="$STRAT_DIR/TestTV_${h}.py"
    if [ ! -f "$strat_file" ]; then
        echo "  📝 $h"
        ((count++))
    fi
done

rm -f "$URL_LIST" /tmp/tv_urls_batch.txt

echo ""
echo "=== Scout 完成 ==="
echo "待轉換: $count 個"
