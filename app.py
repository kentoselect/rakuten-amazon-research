import streamlit as st
import pandas as pd
import requests
from urllib.parse import quote
from pathlib import Path

st.set_page_config(
    page_title="ケントセレクト Amazonリサーチ",
    page_icon="📊",
    layout="wide",
)

st.title("ケントセレクト Amazonリサーチ")
st.caption("楽天・ヤフオクからAmazon販売候補をリサーチ")

rakuten_tab, yahoo_tab = st.tabs(["楽天 × Amazon", "ヤフオク × Amazon中古"])


def check_yahoo_stock(url):
    """ヤフオクの商品ページを確認し、終了表示の有無を簡易判定する。"""
    if not url:
        return "確認エラー"

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if response.status_code != 200:
            return "確認エラー"

        page_text = response.text
        sold_words = [
            "このオークションは終了しています",
            "オークションは終了しました",
            "落札されました",
        ]
        if any(word in page_text for word in sold_words):
            return "在庫なし"
        return "在庫あり"
    except Exception:
        return "確認エラー"


with rakuten_tab:
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
                params = {
                    "applicationId": app_id,
                    "keyword": keyword.strip(),
                    "hits": 20,
                    "format": "json",
                }

                # access key is optional for some Rakuten API configurations.
                # If configured, send it as a query parameter and Bearer token.
                access_key = st.secrets.get("RAKUTEN_ACCESS_KEY", "")
                if access_key:
                    params["accessKey"] = access_key

                headers = {}
                if access_key:
                    headers["Authorization"] = f"Bearer {access_key}"

                response = requests.get(
                    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601",
                    params=params,
                    headers=headers,
                    timeout=15,
                )

                if not response.ok:
                    st.error(
                        f"楽天APIエラー HTTP {response.status_code}: "
                        f"{response.text[:300]}"
                    )
                else:
                    payload = response.json()
                    items = payload.get("Items", [])
                    rows = []
                    for entry in items:
                        item = entry.get("Item", entry) if isinstance(entry, dict) else {}
                        name = item.get("itemName", "")
                        rows.append(
                            {
                                "商品名": name,
                                "楽天価格": item.get("itemPrice", 0),
                                "楽天URL": item.get("itemUrl", ""),
                                "Amazon検索": "https://www.amazon.co.jp/s?k=" + quote(name),
                            }
                        )

                    if rows:
                        st.dataframe(
                            pd.DataFrame(rows),
                            column_config={
                                "楽天URL": st.column_config.LinkColumn(
                                    "楽天の商品ページ", display_text="楽天を開く"
                                ),
                                "Amazon検索": st.column_config.LinkColumn(
                                    "Amazonで検索", display_text="Amazonを開く"
                                ),
                            },
                            hide_index=True,
                            use_container_width=True,
                        )
                    else:
                        st.info("該当する商品がありません。検索語を変えて試してください。")
            except KeyError:
                st.error(
                    "Streamlit Secretsに RAKUTEN_APP_ID が設定されていません。"
                    "アプリのSecrets設定を確認してください。"
                )
            except Exception as exc:
                st.error(f"検索エラー: {type(exc).__name__}: {exc}")

    st.divider()
    st.subheader("利益シミュレーション")
    col1, col2 = st.columns(2)
    with col1:
        cost = st.number_input("楽天仕入れ価格（円）", min_value=0, value=5000, step=100)
        price = st.number_input("Amazon販売価格（円）", min_value=0, value=7000, step=100)
    with col2:
        fee_rate = st.number_input(
            "Amazon販売手数料率（％）",
            min_value=0.0,
            max_value=100.0,
            value=10.4,
            step=0.1,
        )
        shipping = st.number_input("送料・その他費用（円）", min_value=0, value=500, step=100)

    fee = price * fee_rate / 100
    profit = price - cost - fee - shipping
    roi = profit / cost * 100 if cost else 0
    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("予想利益", f"{profit:,.0f}円")
    metric2.metric("ROI", f"{roi:.1f}%")
    metric3.metric("販売手数料", f"{fee:,.0f}円")


with yahoo_tab:
    st.header("ヤフオク × Amazon 中古リサーチ")
    data_file = Path("yahoo_inventory.csv")
    columns = [
        "商品名", "ヤフオクURL", "仕入価格", "送料", "Amazon販売価格",
        "Amazon手数料率", "その他費用", "利益", "ROI", "在庫状況",
    ]

    def load_data():
        if data_file.exists():
            try:
                data = pd.read_csv(data_file)
                for column in columns:
                    if column not in data.columns:
                        data[column] = ""
                return data[columns]
            except Exception:
                pass
        return pd.DataFrame(columns=columns)

    def save_data(data):
        data.to_csv(data_file, index=False)

    df = load_data()
    research_tab, inventory_tab = st.tabs(["商品登録・利益計算", "在庫管理"])

    with research_tab:
        name = st.text_input("商品名", placeholder="例：COACH バッグ", key="yahoo_name")
        url = st.text_input(
            "ヤフオクの商品URL",
            placeholder="https://page.auctions.yahoo.co.jp/...",
            key="yahoo_url",
        )
        if name.strip():
            st.link_button(
                "Amazonで同じ商品を検索",
                "https://www.amazon.co.jp/s?k=" + quote(name.strip()),
                use_container_width=True,
            )

        left, right = st.columns(2)
        with left:
            y_cost = st.number_input("ヤフオク仕入れ価格（円）", min_value=0, value=5000, step=100)
            y_ship = st.number_input("仕入れ送料（円）", min_value=0, value=0, step=100)
            y_other = st.number_input("その他費用（円）", min_value=0, value=0, step=100)
        with right:
            y_price = st.number_input("Amazon販売予定価格（円）", min_value=0, value=7000, step=100)
            y_fee_rate = st.number_input(
                "Amazon販売手数料率（%）",
                min_value=0.0,
                max_value=100.0,
                value=10.4,
                step=0.1,
                key="yahoo_fee_rate",
            )

        y_fee = y_price * y_fee_rate / 100
        total_cost = y_cost + y_ship + y_other
        y_profit = y_price - total_cost - y_fee
        y_roi = y_profit / total_cost * 100 if total_cost else 0
        m1, m2, m3 = st.columns(3)
        m1.metric("予想利益", f"{y_profit:,.0f}円")
        m2.metric("ROI", f"{y_roi:.1f}%")
        m3.metric("Amazon手数料", f"{y_fee:,.0f}円")

        if st.button("この商品を在庫監視リストに登録", type="primary", use_container_width=True):
            if not name.strip() or not url.strip():
                st.warning("商品名とヤフオクURLを入力してください。")
            else:
                new_row = pd.DataFrame(
                    [{
                        "商品名": name.strip(),
                        "ヤフオクURL": url.strip(),
                        "仕入価格": y_cost,
                        "送料": y_ship,
                        "Amazon販売価格": y_price,
                        "Amazon手数料率": y_fee_rate,
                        "その他費用": y_other,
                        "利益": round(y_profit),
                        "ROI": round(y_roi, 1),
                        "在庫状況": check_yahoo_stock(url.strip()),
                    }]
                )
                df = pd.concat([df, new_row], ignore_index=True)
                save_data(df)
                st.success("在庫監視リストに登録しました。")

    with inventory_tab:
        st.subheader("ヤフオク在庫管理")
        if st.button("ヤフオク在庫を自動チェック", use_container_width=True):
            if df.empty:
                st.warning("在庫監視リストに商品がありません。")
            else:
                with st.spinner("ヤフオクの在庫を確認しています..."):
                    for index in df.index:
                        df.at[index, "在庫状況"] = check_yahoo_stock(df.at[index, "ヤフオクURL"])
                    save_data(df)
                st.success("ヤフオクの在庫状況を自動チェックしました。")

        if df.empty:
            st.info("登録されている商品はまだありません。")
        else:
            edited = st.data_editor(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ヤフオクURL": st.column_config.LinkColumn("ヤフオク", display_text="商品を見る"),
                    "在庫状況": st.column_config.SelectboxColumn(
                        "在庫状況",
                        options=["確認エラー", "在庫あり", "在庫なし", "仕入済み", "Amazon出品中", "販売済み"],
                        required=True,
                    ),
                },
                disabled=["利益", "ROI"],
            )
            if st.button("在庫情報を保存", use_container_width=True):
                save_data(edited)
                st.success("在庫情報を保存しました。")
            st.download_button(
                "在庫リストをCSVでダウンロード",
                edited.to_csv(index=False).encode("utf-8-sig"),
                "yahoo_inventory.csv",
                "text/csv",
                use_container_width=True,
            )

    st.divider()
    st.info("登録したヤフオク商品URLを使って、在庫状況を簡易チェックできます。")
