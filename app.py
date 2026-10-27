import streamlit as st
import pandas as pd
import requests
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

# =========================================================
# 保存先
# =========================================================
DATA_FILE = Path("yahoo_stock_items.json")


# =========================================================
# ヤフオク在庫判定
# =========================================================
def check_yahoo_stock(url):
    url = str(url).strip()

    if not url or "yahoo.co.jp" not in url:
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
            allow_redirects=True,
        )

        if response.status_code in (404, 410):
            return "在庫なし"
        if response.status_code in (403, 429):
            return "確認エラー"
        if response.status_code != 200:
            return "確認エラー"

        final_url = response.url.lower()

        if (
            "auctions.yahoo.co.jp" in final_url
            and "page.auctions.yahoo.co.jp" not in final_url
            and "/auction/" not in final_url
        ):
            return "確認エラー"

        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(" ", strip=True)

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

        for script in soup.find_all(
            "script",
            attrs={"type": "application/ld+json"},
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
                    offer_list = offers if isinstance(offers, list) else [offers]

                    for offer in offer_list:
                        if not isinstance(offer, dict):
                            continue

                        availability = str(
                            offer.get("availability", "")
                        ).lower()

                        if "outofstock" in availability or "soldout" in availability:
                            return "在庫なし"
                        if "instock" in availability:
                            return "在庫あり"

            except Exception:
                pass

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

        strong_active_words = [
            "入札する",
            "今すぐ落札",
            "購入手続きへ",
            "購入する",
        ]

        if any(word in page_text for word in strong_active_words):
            return "在庫あり"

        active_count = sum(
            1 for word in active_words if word in page_text
        )

        if active_count >= 2:
            return "在庫あり"

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

        return "確認エラー"

    except requests.exceptions.Timeout:
        return "確認エラー"
    except requests.exceptions.RequestException:
        return "確認エラー"
    except Exception:
        return "確認エラー"


# =========================================================
# ヤフオク登録データ
# =========================================================
def load_yahoo_items():
    if not DATA_FILE.exists():
        return []

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_yahoo_items(items):
    DATA_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# =========================================================
# Streamlit基本設定
# =========================================================
st.set_page_config(
    page_title="ケントセレクト Amazonリサーチ",
    page_icon="📊",
    layout="wide",
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
        key="rakuten_keyword",
    )

    if st.button("楽天で検索", key="rakuten_search"):
        if not keyword.strip():
            st.warning("商品名を入力してください。")
        else:
            try:
                app_id = st.secrets["RAKUTEN_APP_ID"]
                access_key = st.secrets.get("RAKUTEN_ACCESS_KEY", "")

                params = {
                    "applicationId": app_id,
                    "keyword": keyword.strip(),
                    "hits": 20,
                    "format": "json",
                }

                if access_key:
                    params["accessKey"] = access_key

                headers = {}
                if access_key:
                    headers["Authorization"] = f"Bearer {access_key}"

                r = requests.get(
                    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
                    params=params,
                    headers=headers,
                    timeout=15,
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

                        rows.append(
                            {
                                "商品名": name,
                                "楽天価格": item.get("itemPrice", ""),
                                "ショップ": item.get("shopName", ""),
                                "商品URL": item.get("itemUrl", ""),
                            }
                        )

                    if rows:
                        df = pd.DataFrame(rows)
                        st.success(f"{len(df)}件見つかりました。")
                        st.dataframe(
                            df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "商品URL": st.column_config.LinkColumn(
                                    "商品URL"
                                )
                            },
                        )
                    else:
                        st.info("商品が見つかりませんでした。")

            except KeyError:
                st.error(
                    "StreamlitのSecretsに RAKUTEN_APP_ID がありません。"
                )
            except requests.exceptions.RequestException as e:
                st.error(f"楽天への通信でエラーが発生しました: {e}")
            except Exception as e:
                st.error(f"楽天検索エラー: {e}")


# =========================================================
# ヤフオク × Amazon中古
# =========================================================
with yahoo_tab:
    st.header("ヤフオク × Amazon中古")
    st.caption(
        "ヤフオクの商品URLを登録して、出品中か終了済みかを確認します。"
    )

    yahoo_name = st.text_input(
        "商品名",
        placeholder="例：Panasonic ドライヤー EH-NA0J",
        key="yahoo_name",
    )

    yahoo_url = st.text_input(
        "ヤフオク商品URL",
        placeholder="https://page.auctions.yahoo.co.jp/...",
        key="yahoo_url",
    )

    if st.button("商品を登録して在庫確認", key="yahoo_add"):
        clean_url = yahoo_url.strip()
        clean_name = yahoo_name.strip()

        if not clean_name:
            st.warning("商品名を入力してください。")
        elif not clean_url:
            st.warning("ヤフオクの商品URLを入力してください。")
        elif "yahoo.co.jp" not in clean_url:
            st.warning("ヤフオクの商品URLを入力してください。")
        else:
            with st.spinner("ヤフオクの在庫状況を確認しています..."):
                stock = check_yahoo_stock(clean_url)

            items = load_yahoo_items()

            existing = next(
                (
                    item
                    for item in items
                    if item.get("url") == clean_url
                ),
                None,
            )

            if existing:
                existing["name"] = clean_name
                existing["stock"] = stock
            else:
                items.append(
                    {
                        "name": clean_name,
                        "url": clean_url,
                        "stock": stock,
                    }
                )

            save_yahoo_items(items)

            if stock == "在庫あり":
                st.success("在庫あり")
            elif stock == "在庫なし":
                st.error("在庫なし")
            else:
                st.warning(
                    "確認エラー：ヤフオク側のアクセス制限などで"
                    "自動判定できませんでした。"
                )

            st.rerun()

    st.divider()
    st.subheader("在庫管理")

    items = load_yahoo_items()

    if not items:
        st.info("まだ登録商品がありません。")
    else:
        if st.button(
            "全商品の在庫を再チェック",
            key="yahoo_refresh_all",
            type="primary",
        ):
            progress = st.progress(0)
            total = len(items)

            for index, item in enumerate(items):
                item["stock"] = check_yahoo_stock(
                    item.get("url", "")
                )
                progress.progress((index + 1) / total)

            save_yahoo_items(items)
            progress.empty()
            st.success("全商品の在庫状況を更新しました。")
            st.rerun()

        rows = []

        for i, item in enumerate(items):
            rows.append(
                {
                    "No.": i + 1,
                    "商品名": item.get("name", ""),
                    "在庫状況": item.get("stock", "確認エラー"),
                    "ヤフオクURL": item.get("url", ""),
                }
            )

        df = pd.DataFrame(rows)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ヤフオクURL": st.column_config.LinkColumn(
                    "ヤフオクURL"
                )
            },
        )

        st.subheader("登録商品の削除")

        delete_options = {
            f"{i + 1}. {item.get('name', '名称なし')}": i
            for i, item in enumerate(items)
        }

        selected = st.selectbox(
            "削除する商品",
            options=list(delete_options.keys()),
            key="yahoo_delete_select",
        )

        if st.button("選択した商品を削除", key="yahoo_delete"):
            delete_index = delete_options[selected]
            deleted_name = items[delete_index].get(
                "name",
                "商品",
            )
            del items[delete_index]
            save_yahoo_items(items)
            st.success(f"{deleted_name} を削除しました。")
            st.rerun()
