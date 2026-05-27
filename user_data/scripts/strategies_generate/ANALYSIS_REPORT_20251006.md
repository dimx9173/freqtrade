# 📊 3 輪運行分析報告

**日期**: 2025-10-06  
**觀察時間**: 10 分鐘 (3 輪完整循環)  
**狀態**: ❌ 發現關鍵問題

---

## 📋 觀察結果

### 運行統計
- **總輪數**: 3 輪
- **成功率**: 0/3 (0%)
- **失敗原因**: 所有策略回測失敗
- **循環間隔**: 180 秒（3 分鐘）

### 時間軸

| 輪次 | 開始時間 | 指標組合 | 生成時間 | 回測結果 | 錯誤 |
|------|---------|---------|---------|---------|------|
| 1 | 13:03:09 | ROC, SMA, VWAP | 47秒 | ❌ 失敗 | advise_indicators |
| 2 | 13:07:01 | Keltner_Channel, VWAP, PSAR | 54秒 | ❌ 失敗 | advise_indicators |
| 3 | 13:11:00 | VWAP, CCI, MACD | 85秒 | ❌ 失敗 | advise_indicators |

---

## 🔍 問題分析

### 核心問題：Talib 指標返回值處理錯誤

**錯誤堆棧**:
```python
File "/Users/carlos/pywork/freqtrade/freqtrade/optimize/backtesting.py", line 1730
    preprocessed = self.strategy.advise_all_indicators(data)
File "/Users/carlos/pywork/freqtrade/freqtrade/strategy/interface.py", line 1748
    res[pair] = self.advise_indicators(pair_data.copy(), {"pair": pair}).copy()
```

**具體錯誤示例** (從生成的策略中發現):

```python
# ❌ 錯誤代碼 (第 100-102 行)
stoch_rsi = ta.STOCHRSI(dataframe, timeperiod=self.stoch_rsi_len)
dataframe['stoch_rsi_k'] = stoch_rsi['fastk']  # ❌ 字典訪問錯誤
dataframe['stoch_rsi_d'] = stoch_rsi['fastd']  # ❌ 字典訪問錯誤
```

**問題根源**:
1. `ta.STOCHRSI()` 返回的是 **tuple**，不是字典
2. Gemini AI 生成的代碼使用了錯誤的訪問方式
3. 系統沒有自動修復這類錯誤

---

## 🛠️ 解決方案

### 方案 1: 添加自動代碼修復邏輯 ✅ 推薦

在 `foundry_engine.py` 中添加自動修復函數：

```python
def auto_fix_strategy_code(self, code):
    """自動修復常見的策略代碼錯誤"""
    fixes_applied = []
    
    # 修復 1: STOCHRSI 返回值處理
    if "ta.STOCHRSI" in code and "['fastk']" in code:
        code = code.replace(
            "stoch_rsi = ta.STOCHRSI(dataframe",
            "stoch_rsi_k, stoch_rsi_d = ta.STOCHRSI(dataframe"
        )
        code = code.replace(
            "dataframe['stoch_rsi_k'] = stoch_rsi['fastk']",
            "dataframe['stoch_rsi_k'] = stoch_rsi_k"
        )
        code = code.replace(
            "dataframe['stoch_rsi_d'] = stoch_rsi['fastd']",
            "dataframe['stoch_rsi_d'] = stoch_rsi_d"
        )
        fixes_applied.append("STOCHRSI 返回值修復")
    
    # 修復 2: BBANDS 返回值處理
    if "ta.BBANDS" in code and "['upperband']" in code:
        code = code.replace(
            "bollinger = ta.BBANDS(dataframe",
            "bb_upper, bb_middle, bb_lower = ta.BBANDS(dataframe"
        )
        code = code.replace(
            "dataframe['bb_upper'] = bollinger['upperband']",
            "dataframe['bb_upper'] = bb_upper"
        )
        code = code.replace(
            "dataframe['bb_middle'] = bollinger['middleband']",
            "dataframe['bb_middle'] = bb_middle"
        )
        code = code.replace(
            "dataframe['bb_lower'] = bollinger['lowerband']",
            "dataframe['bb_lower'] = bb_lower"
        )
        fixes_applied.append("BBANDS 返回值修復")
    
    # 修復 3: MACD 返回值處理
    if "ta.MACD" in code and "['macd']" in code:
        code = code.replace(
            "macd = ta.MACD(dataframe",
            "macd, macdsignal, macdhist = ta.MACD(dataframe"
        )
        code = code.replace(
            "dataframe['macd'] = macd['macd']",
            "dataframe['macd'] = macd"
        )
        code = code.replace(
            "dataframe['macdsignal'] = macd['macdsignal']",
            "dataframe['macdsignal'] = macdsignal"
        )
        code = code.replace(
            "dataframe['macdhist'] = macd['macdhist']",
            "dataframe['macdhist'] = macdhist"
        )
        fixes_applied.append("MACD 返回值修復")
    
    # 修復 4: STOCH 返回值處理
    if "ta.STOCH" in code and "['slowk']" in code:
        code = code.replace(
            "stoch = ta.STOCH(dataframe",
            "slowk, slowd = ta.STOCH(dataframe"
        )
        code = code.replace(
            "dataframe['slowk'] = stoch['slowk']",
            "dataframe['slowk'] = slowk"
        )
        code = code.replace(
            "dataframe['slowd'] = stoch['slowd']",
            "dataframe['slowd'] = slowd"
        )
        fixes_applied.append("STOCH 返回值修復")
    
    if fixes_applied:
        logger.info(f"🔧 自動修復: {', '.join(fixes_applied)}")
    
    return code
```

**應用位置**: 在保存策略文件之前調用

```python
# 在 generate_strategy 方法中
strategy_code = self.auto_fix_strategy_code(strategy_code)
```

---

### 方案 2: 改進 Gemini 提示詞 ⚠️ 輔助方案

在生成策略時，明確告訴 AI 正確的用法：

```python
prompt = f"""
請為 Freqtrade 生成一個使用 {indicator_str} 的剝頭皮策略。

重要技術要求：
1. talib 多返回值指標的正確用法：
   - STOCHRSI: fastk, fastd = ta.STOCHRSI(...)
   - BBANDS: upper, middle, lower = ta.BBANDS(...)
   - MACD: macd, signal, hist = ta.MACD(...)
   - STOCH: slowk, slowd = ta.STOCH(...)

2. 不要使用字典訪問方式（如 result['key']）

3. 確保所有指標計算完成後再使用
...
"""
```

---

### 方案 3: 語法驗證增強 ⚠️ 預防方案

在保存策略前進行語法檢查：

```python
def validate_strategy_syntax(self, code, strategy_path):
    """驗證策略語法"""
    try:
        # 1. Python 語法檢查
        compile(code, strategy_path, 'exec')
        
        # 2. 檢查常見錯誤模式
        error_patterns = [
            (r"ta\.\w+\(.*\)\['", "Talib 指標使用了字典訪問"),
            (r"stoch_rsi\['fastk'\]", "STOCHRSI 使用了錯誤的訪問方式"),
            (r"bollinger\['upperband'\]", "BBANDS 使用了錯誤的訪問方式"),
        ]
        
        for pattern, error_msg in error_patterns:
            if re.search(pattern, code):
                logger.warning(f"⚠️  發現潛在錯誤: {error_msg}")
                return False
        
        return True
        
    except SyntaxError as e:
        logger.error(f"❌ 語法錯誤: {e}")
        return False
```

---

## 📊 影響評估

### 當前影響
- ❌ **0% 成功率** - 所有策略都無法通過回測
- ⏱️ **時間浪費** - 每輪約 1 分鐘用於生成和回測失敗的策略
- 💰 **資源浪費** - Gemini API 調用但無有效產出

### 修復後預期
- ✅ **提高成功率** - 預計 60-80% 的策略能通過語法檢查
- ⚡ **加快迭代** - 減少無效回測，提高有效策略產出
- 🎯 **聚焦質量** - 篩選標準能真正評估策略質量

---

## 🎯 優先級建議

### 立即執行（高優先級）
1. ✅ **添加自動修復邏輯** - 方案 1
   - 修復 STOCHRSI, BBANDS, MACD, STOCH
   - 在保存策略前自動應用

2. ✅ **改進錯誤日誌** - 顯示完整錯誤信息
   - 當前只顯示部分錯誤輸出
   - 需要完整的 traceback

### 短期優化（中優先級）
3. ⚠️ **改進提示詞** - 方案 2
   - 明確告知 AI 正確用法
   - 提供示例代碼

4. ⚠️ **語法驗證** - 方案 3
   - 在回測前驗證
   - 早期發現問題

### 長期改進（低優先級）
5. 📊 **統計分析**
   - 記錄常見錯誤類型
   - 持續優化修復邏輯

6. 🧪 **單元測試**
   - 為自動修復添加測試
   - 確保修復邏輯正確

---

## 📝 實施計劃

### 第 1 步：添加自動修復（預計 10 分鐘）
```bash
# 修改 foundry_engine.py
# 添加 auto_fix_strategy_code 方法
# 在 generate_strategy 中調用
```

### 第 2 步：改進錯誤日誌（預計 5 分鐘）
```python
# 修改 run_backtest 方法
# 顯示完整的 stderr 和 stdout
```

### 第 3 步：重啟測試（預計 10 分鐘）
```bash
./run_foundry.sh restart
# 觀察 2-3 輪
# 驗證修復效果
```

### 第 4 步：監控優化（持續）
```bash
# 每天檢查統計
./run_foundry.sh stats
# 根據結果調整修復邏輯
```

---

## 🎉 預期成果

修復後，系統應該能夠：
- ✅ 自動修復 80%+ 的 Talib 指標錯誤
- ✅ 成功執行回測並獲得真實的 KPI 數據
- ✅ 讓篩選標準真正發揮作用
- ✅ 產出可用的候選策略

---

**報告生成時間**: 2025-10-06 13:15  
**下一步行動**: 實施自動修復邏輯
