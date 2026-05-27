import requests
import json

TOP_CRYPTO = 25


def get_top_crypto():
    """
    取得 CoinMarketCap 市佔率前 TOP_CRYPTO 名的加密貨幣，並將其與 USDT 配對。
    排除穩定幣（如 USDT、USDC 等）。

    Returns:
        dict: 包含加密貨幣配對列表和 refresh_period 的字典。
             如果 API 請求失敗，則返回 None。
    """
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    parameters = {
        "start": "1",
        "limit": "100",  # 获取前 X 个，以便过滤后得到至少 TOP_CRYPTO 个
        "convert": "USD",
    }
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": "86423e6b-25f0-4fe2-8be4-18fca8b3b866",  # 替換成你的 API 金鑰
    }

    try:
        response = requests.get(url, params=parameters, headers=headers)
        response.raise_for_status()  # 如果请求失败，会抛出 HTTPError 异常
        data = response.json()

        stablecoins = {
            "USDT",
            "USDe",
            "USDE",
            "USDC",
            "BUSD",
            "DAI",
            "TUSD",
            "USDP",
            "GUSD",
            "USTC",
            "FRAX",
            "USDN",
        }  # 加入更多稳定币
        symbols = []
        count = 0  # 计数器，确保获取到 TOP_CRYPTO 个非稳定币

        for coin in data["data"]:
            symbol = coin["symbol"]
            if symbol not in stablecoins and count < TOP_CRYPTO and symbol != "USDT":
                symbols.append(f"{symbol}/USDT")
                count += 1

        return {"pairs": symbols, "refresh_period": 1800}

    except requests.exceptions.RequestException as e:
        print(f"API 請求錯誤: {e}")
        return None


if __name__ == "__main__":
    result = get_top_crypto()

    if result:
        with open("user_data/config/coinmarketcap-pairlist.json", "w") as f:
            json.dump(result, f, indent=4)  # 使用 indent 格式化输出，方便阅读
            print(f"已將配對列表儲存至 user_data/config/coinmarketcap-pairlist.json: {result}")

        pairs_only = result["pairs"]
        with open("user_data/config/coinmarketcap-pairs.json", "w") as f:
            json.dump(pairs_only, f, indent=4)  # 使用 indent 格式化输出，方便阅读
            print(f"已將配對列表儲存至 user_data/config/coinmarketcap-pairs.json: {pairs_only}")

        future_pairs = [f"{pair}:{pair.split('/')[1]}" for pair in pairs_only]
        with open("user_data/config/coinmarketcap-future-pairs.json", "w") as f:
            json.dump(future_pairs, f, indent=4)
            print(
                f"已將期貨配對列表儲存至 user_data/config/coinmarketcap-future-pairs.json: {future_pairs}"
            )

        with open("user_data/config/coinmarketcap-future-pairlist.json", "w") as f:
            json.dump({"pairs": future_pairs, "refresh_period": 1800}, f, indent=4)
            print(
                f"已將期貨配對列表儲存至 user_data/config/coinmarketcap-future-pairlist.json: {{'pairs': {future_pairs}, 'refresh_period': 1800}}"
            )

    else:
        print("無法取得加密貨幣配對列表。")
