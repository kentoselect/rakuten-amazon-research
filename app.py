import streamlit as st
import pandas as pd
import requests
import json
import re
from urllib.parse import quote
from pathlib import Path
from bs4 import BeautifulSoup


# =========================================================
# ヤフオク在庫判定
# =========================================================
def check_yahoo_stock(url):
    url = str(url).strip()

    if not url:
        return "確認エラー"

    if "yahoo.co.jp" not in url:
        return "確認エラー"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/18.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://auctions.yahoo.co.jp/",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=20,
            allow_redirects=True
        )

        # -------------------------
        # HTTPステータス判定
        # -------------------------
        if response.status_code in (404, 410):
            return "在庫なし"

        if response.status_code in (403, 429):
            return "確認エラー"

        if response.status_code != 200:
            return "確認エラー"

        final_url = response.url.lower()

        # Yahooトップなどへ飛ばされた場合
        if (
            "auctions.yahoo.co.jp" in final_url
            and "page.auctions.yahoo.co.jp" not in final_url
            and "/auction/" not in final_url
        ):
            return "確認エラー"

        html = response.text
        html_lower = html.lower()

        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(" ", strip=True)

        # =====================================================
        # 1. 明確な終了・削除判定
        # =====================================================
        ended_words = [
            "このオークションは終了しています",
            "このオークションは終了しました",
            "オークションは終了しました",
            "終了したオークション",
            "この商品は終了しました",
            "この商品は削除されました",
            "商品が見つかりません",
            "指定された商品は存在しません",
            "ページが見つかりません",
            "落札されました",
            "出品が終了しました",
            "この出品は終了しました",
            "このページは削除されました",
        ]

        for word in ended_words:
            if word in page_text:
                return "在庫なし"

        # =====================================================
        # 2. HTML / JSON 内の終了フラグ
        # =====================================================
        ended_patterns = [
            r'"isClosed"\s*:\s*true',
            r'"isEnded"\s*:\s*true',
            r'"isFinished"\s*:\s*true',
            r'"closed"\s*:\s*true',
            r'"ended"\s*:\s*true',
            r'"auctionStatus"\s*:\s*"closed"',
            r'"auctionStatus"\s*:\s*"ended"',
            r'"status"\s*:\s*"closed"',
            r'"status"\s*:\s*"ended"',
            r'"status"\s*:\s*"sold"',
        ]

        for pattern in ended_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                return "在庫なし"

        # =====================================================
        # 3. JSON-LDを確認
        # =====================================================
        for script in soup.find_all(
            "script",
            attrs={"type": "application/ld+json"}
        ):
            try:
                if not script.string:
                    continue

                data = json.loads(script.string)

                objects = data if isinstance(data, list) else [data]

                for obj in objects:
                    if not isinstance(obj, dict):
                        continue

                    offers = obj.get("offers")

                    if isinstance(offers, dict):
                        availability = str(
                            offers.get("availability", "")
                        ).lower()

                        if "outofstock" in availability:
                            return "在庫なし"

                        if "soldout" in availability:
                            return "在庫なし"

                        if "instock" in availability:
                            return "在庫あり"

            except Exception:
                pass

        # =====================================================
        # 4. 購入可能な表示を確認
        # =====================================================
        active_words = [
            "入札する",
            "今すぐ落札",
            "購入手続きへ",
            "購入する",
            "現在価格",
            "残り時間",
            "入札件数",
            "開始価格",
            "即決価格",
        ]

        active_count = sum(
            1 for word in active_words if word in page_text
        )

        # 「入札する」「購入する」等があるなら強く在庫あり判定
        strong_active_words = [
            "入札する",
            "今すぐ落札",
            "購入手続きへ",
            "購入する",
        ]

        if any(word in page_text for word in strong_active_words):
            return "在庫あり"

        # 複数の出品中情報が存在
        if active_count >= 2:
            return "在庫あり"

        # =====================================================
        # 5. HTML内部の在庫あり判定
        # =====================================================
        active_patterns = [
            r'"isClosed"\s*:\s*false',
            r'"isEnded"\s*:\s*false',
            r'"isFinished"\s*:\s*false',
            r'"auctionStatus"\s*:\s*"open"',
            r'"auctionStatus"\s*:\s*"active"',
            r'"status"\s*:\s*"open"',
            r'"status"\s*:\s*"active"',
            r'inStock',
        ]

        for pattern in active_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                return "在庫あり"

        # =====================================================
        # 6. ヤフオク商品ページ自体が正常表示されている場合
        # =====================================================
        title = soup.title.get_text(" ", strip=True) if soup.title else ""

        product_indicators = [
            "Yahoo!オークション",
            "ヤフオク",
            "Yahoo! JAPAN",
        ]

        has_product_page = any(
            word in title or word in page_text
            for word in product_indicators
        )

        # 商品ページだが明確な状態が取れない
        if has_product_page:
            return "確認エラー"

        return "確認エラー"

    except requests.exceptions.Timeout:
        return "確認エラー"

    except requests.exceptions.RequestException:
        return "確認エラー"

    except Exception:
        return "確認エラー"


# =========================================================
# Streamlit基本設定
# =========================================================
st.set_page_config(
    page_title="ケントセレクト Amazonリサーチ",
    page_icon="📊",
    layout="wide"
)

st.title("ケントセレクト Amazonリサーチ")
st.caption("楽天・ヤフオクからAmazon販売候補をリサーチ")

rakuten_tab, yahoo_tab = st.tabs(
    ["楽天 × Amazon", "ヤフオク × Amazon中古"]
)


# =========================================================
# 楽天 × Amazon
# =========================================================
with rakuten_tab:

    st.header("楽天 × Amazon 利益リサーチ")

    st.subheader("楽天市場の商品検索")

    keyword = st.text_input(
        "検索したい商品名",
        placeholder="例：Panasonic",
        key="rakuten_keyword"
    )

    if st.button(
        "楽天で検索",
        key="rakuten_search"
    ):

        if not keyword.strip():

            st.warning("商品名を入力してください。")

        else:

            try:

                access_key = st.secrets["RAKUTEN_ACCESS_KEY"]

                r = requests.get(
                    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
                    params={
                        "applicationId": st.secrets["RAKUTEN_APP_ID"],
                        "accessKey": access_key,
                        "keyword": keyword.strip(),
                        "hits": 20,
                        "format": "json"
                    },
                    headers={
                        "Authorization": f"Bearer {access_key}"
                    },
                    timeout=15
                )

                if not r.ok:

                    st.error(
                        f"楽天APIエラー HTTP {r.status_code}: "
                        f"{r.text[:300]}"
                    )

                else:

                    rows = []

                    for entry in r.json().get("Items", []):

                        item = entry.get("Item", entry)

                        name = item.get("itemName", "")

                        rows.append({
                            "商品名": name,
                            "楽天価格": item.get(
                                "itemPrice",
