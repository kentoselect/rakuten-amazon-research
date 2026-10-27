import streamlit as st
import pandas as pd
import requests
from urllib.parse import quote
from pathlib import Path
from bs4 import BeautifulSoup


def check_yahoo_stock(url):
    """ヤフオク商品ページの出品状況を自動判定"""

    if not url or "yahoo.co.jp" not in url:
        return "確認待ち"

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15,
            allow_redirects=True,
        )

        if response.status_code in (404, 410):
            return "在庫なし"

        if response.status_code != 200:
            return "確認待ち"

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        ended_words = [
            "このオークションは終了しています",
            "このオークションは終了しました",
            "オークションは終了しました",
            "終了したオークション",
            "商品が見つかりません",
            "指定された商品は存在しません",
            "ページが見つかりません",
            "落札されました",
        ]

        for word in ended_words:
            if word in text:
                return "在庫なし"

        active_words = [
            "入札する",
            "今すぐ落札",
            "現在価格",
            "残り時間",
            "入札件数",
            "開始価格",
        ]

        active_count = sum(
            1 for word in active_words if word in text
        )

        if active_count >= 2:
            return "在庫あり"

        html = response.text.lower()

        ended_patterns = [
            '"isclosed":true',
            '"isended":true',
            '"auctionstatus":"closed"',
        ]

        for pattern in ended_patterns:
            if pattern in html:
                return "在庫なし"

        return "確認待ち"

    except requests.RequestException:
        return "確認待ち"

    except Exception:
        return "確認待ち"


st.set_page_config(
    page_title="ケントセレクト Amazonリサーチ",
    page_icon="📊",
    layout="wide",
)

st.title("ケントセレクト Amazonリサーチ")
st.caption("楽天・ヤフオクからAmazon販売候補をリサーチ")

rakuten_tab, yahoo_tab = st.tabs([
    "楽天 × Amazon",
    "ヤフオク × Amazon中古",
])


# =========================================================
# 楽天 × Amazon
# =========================================================

with rakuten_tab:

    st.header("楽天 × Amazon 利益リサーチ")
    st.subheader("楽天市場の商品検索")

    keyword = st.text_input(
        "検索したい商品名",
        placeholder="例：Panasonic",
        key="rakuten_keyword",
    )

    if st.button("楽天で検索", key="rakuten_search"):

        if not keyword.strip():
            st.warning("商品名を入力してください。")

        else:
            try:
                access_key = st.secrets["RAKUTEN_ACCESS_KEY"]

                response = requests.get(
                    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
                    params={
                        "applicationId": st.secrets["RAKUTEN_APP_ID"],
                        "accessKey": access_key,
                        "keyword": keyword.strip(),
                        "hits": 20,
                        "format": "json",
                    },
                    headers={
                        "Referer": (
                            "https://rakuten-amazon-research-"
                            "tygw8zohahgg2gvwwnasdf.streamlit.app/"
                        ),
                        "Origin": (
                            "https://rakuten-amazon-research-"
                            "tygw8zohahgg2gvwwnasdf.streamlit.app"
                        ),
                        "Authorization": f"Bearer {access_key}",
                    },
                    timeout=15,
                )

                if not response.ok:
                    st.error(
                        f"楽天APIエラー HTTP {response.status_code}: "
                        f"{response.text[:300]}"
                    )
                    st.stop()

                items = response.json().get("Items", [])

                if items:
                    rows = []

                    for entry in items:
                        item = entry.get("Item", entry)
                        name = item.get("itemName", "")

                        rows.append({
                            "商品名": name,
                            "楽天価格": item.get("itemPrice", 0),
                            "楽天URL": item.get("itemUrl", ""),
                            "Amazon検索":
                                "https://www.amazon.co.jp/s?k="
                                + quote(name),
                        })

                    st.dataframe(
                        pd.DataFrame(rows),
                        column_config={
                            "楽天URL":
                                st.column_config.LinkColumn(
                                    "楽天の商品ページ",
                                    display_text="楽天を開く",
                                ),
                            "Amazon検索":
                                st.column_config.LinkColumn(
                                    "Amazonで検索",
                                    display_text="Amazonを開く",
                                ),
                        },
                        hide_index=True,
                        use_container_width=True,
                    )

                else:
                    st.info("該当する商品がありません。")

            except requests.RequestException as e:
                st.error(f"通信エラー: {e}")

            except KeyError:
                st.error(
                    "Streamlit Secretsの楽天API設定を確認してください。"
                )

            except Exception as e:
                st.error(
                    f"検索エラー: {type(e).__name__}: {e}"
                )

    st.divider()
    st.subheader("利益シミュレーション")

    left, right = st.columns(2)

    with left:
        cost = st.number_input(
            "楽天仕入れ価格（円）",
            min_value=0,
            value=500
