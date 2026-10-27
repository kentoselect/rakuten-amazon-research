import streamlit as st
import pandas as pd
import requests
from urllib.parse import quote
from pathlib import Path
# ↓ app.py の import が並んでいるところに追加
from bs4 import BeautifulSoup


def check_yahoo_stock(url):
    """ヤフオク商品ページを確認して在庫状況を判定"""
    if not url or "auctions.yahoo.co.jp" not in url:
        return "確認待ち"

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
            )
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10,
            allow_redirects=True
        )

        # 商品ページ自体が無くなっている
        if response.status_code == 404:
            return "在庫なし"

        if response.status_code != 200:
            return "確認待ち"

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # 終了・削除された商品
        sold_words = [
            "オークションは終了しました",
            "このオークションは終了しています",
            "終了したオークション",
            "商品が見つかりません",
            "指定された商品は存在しません",
        ]

        for word in sold_words:
            if word in text:
                return "在庫なし"

        # 出品中と判断できる表示
        active_words = [
            "入札する",
            "今すぐ落札",
            "残り時間",
            "現在価格",
        ]

        for word in active_words:
            if word in text:
                return "在庫あり"

        return "確認待ち"

    except requests.RequestException:
        return "確認待ち"
st.set_page_config(
    page_title="ケントセレクト Amazonリサーチ",
    page_icon="📊",
    layout="wide"
)

st.title("ケントセレクト Amazonリサーチ")
st.caption("楽天・ヤフオクからAmazon販売候補をリサーチ")

rakuten_tab, yahoo_tab = st.tabs([
    "楽天 × Amazon",
    "ヤフオク × Amazon中古"
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
        key="rakuten_keyword"
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
                        "Referer": "https://rakuten-amazon-research-tygw8zohahgg2gvwwnasdf.streamlit.app/",
                        "Origin": "https://rakuten-amazon-research-tygw8zohahgg2gvwwnasdf.streamlit.app",
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
                                    display_text="楽天を開く"
                                ),

                            "Amazon検索":
                                st.column_config.LinkColumn(
                                    "Amazonで検索",
                                    display_text="Amazonを開く"
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
            value=5000,
            step=100,
            key="rakuten_cost"
        )

        price = st.number_input(
            "Amazon販売価格（円）",
            min_value=0,
            value=7000,
            step=100,
            key="rakuten_price"
        )

    with right:

        fee_rate = st.number_input(
            "Amazon販売手数料率（％）",
            min_value=0.0,
            max_value=100.0,
            value=10.4,
            step=0.1,
            key="rakuten_fee"
        )

        shipping = st.number_input(
            "送料・その他費用（円）",
            min_value=0,
            value=500,
            step=100,
            key="rakuten_shipping"
        )

    fee = price * fee_rate / 100

    profit = price - cost - fee - shipping

    roi = profit / cost * 100 if cost > 0 else 0

    a, b, c = st.columns(3)

    a.metric(
        "予想利益",
        f"{profit:,.0f}円"
    )

    b.metric(
        "ROI",
        f"{roi:.1f}%"
    )

    c.metric(
        "販売手数料",
        f"{fee:,.0f}円"
    )

    st.caption(
        "概算です。FBA手数料や保管料などは"
        "送料・その他費用に含めてください。"
    )

    st.divider()

    st.subheader("CSV読み込み（任意）")

    uploaded = st.file_uploader(
        "商品CSVを選択",
        type=["csv"],
        key="rakuten_csv"
    )

    if uploaded is not None:

        try:

            st.dataframe(
                pd.read_csv(uploaded),
                use_container_width=True
            )

        except Exception as e:

            st.error(
                f"CSV読み込みエラー: {e}"
            )


# =========================================================
# ヤフオク × Amazon中古
# =========================================================

with yahoo_tab:

    st.header("ヤフオク × Amazon 中古リサーチ")

    st.caption(
        "ヤフオクの商品を登録し、Amazon販売時の"
        "利益・ROI・在庫状況を管理します。"
    )

    DATA_FILE = Path("yahoo_inventory.csv")

    COLUMNS = [
        "商品名",
        "ヤフオクURL",
        "仕入価格",
        "送料",
        "Amazon販売価格",
        "Amazon手数料率",
        "その他費用",
        "利益",
        "ROI",
        "在庫状況"
    ]

    def load_yahoo_data():

        if DATA_FILE.exists():

            try:

                df = pd.read_csv(DATA_FILE)

                for column in COLUMNS:

                    if column not in df.columns:
                        df[column] = ""

                return df[COLUMNS]

            except Exception:

                pass

        return pd.DataFrame(
            columns=COLUMNS
        )

    def save_yahoo_data(df):

        df.to_csv(
            DATA_FILE,
            index=False
        )

    yahoo_df = load_yahoo_data()

    research_tab, inventory_tab = st.tabs([
        "商品登録・利益計算",
        "在庫管理"
    ])

    # -----------------------------------------------------
    # 商品登録
    # -----------------------------------------------------

    with research_tab:

        st.subheader("商品登録")

        yahoo_name = st.text_input(
            "商品名",
            placeholder="例：SONY α7 III ボディ",
            key="yahoo_name"
        )

        yahoo_url = st.text_input(
            "ヤフオクの商品URL",
            placeholder="https://page.auctions.yahoo.co.jp/...",
            key="yahoo_url"
        )

        if yahoo_name.strip():

            amazon_search_url = (
                "https://www.amazon.co.jp/s?k="
                + quote(yahoo_name.strip())
            )

            st.link_button(
                "Amazonで同じ商品を検索",
                amazon_search_url,
                use_container_width=True
            )

        col1, col2 = st.columns(2)

        with col1:

            yahoo_cost = st.number_input(
                "ヤフオク仕入れ価格（円）",
                min_value=0,
                value=5000,
                step=100,
                key="yahoo_cost"
            )

            yahoo_shipping = st.number_input(
                "仕入れ送料（円）",
                min_value=0,
                value=0,
                step=100,
                key="yahoo_shipping"
            )

            yahoo_other = st.number_input(
                "その他費用（円）",
                min_value=0,
                value=0,
                step=100,
                key="yahoo_other"
            )

        with col2:

            yahoo_amazon_price = st.number_input(
                "Amazon販売予定価格（円）",
                min_value=0,
                value=7000,
                step=100,
                key="yahoo_amazon_price"
            )

            yahoo_fee_rate = st.number_input(
                "Amazon販売手数料率（％）",
                min_value=0.0,
                max_value=100.0,
                value=10.4,
                step=0.1,
                key="yahoo_fee_rate"
            )

        yahoo_fee = (
            yahoo_amazon_price
            * yahoo_fee_rate
            / 100
        )

        yahoo_total_cost = (
            yahoo_cost
            + yahoo_shipping
            + yahoo_other
        )

        yahoo_profit = (
            yahoo_amazon_price
            - yahoo_total_cost
            - yahoo_fee
        )

        yahoo_roi = (
            yahoo_profit
            / yahoo_total_cost
            * 100
            if yahoo_total_cost > 0
            else 0
        )

        m1, m2, m3 = st.columns(3)

        m1.metric(
            "予想利益",
            f"{yahoo_profit:,.0f}円"
        )

        m2.metric(
            "ROI",
            f"{yahoo_roi:.1f}%"
        )

        m3.metric(
            "Amazon手数料",
            f"{yahoo_fee:,.0f}円"
        )

        if yahoo_profit > 0:

            st.success(
                f"この条件なら約 {yahoo_profit:,.0f}円の利益です。"
            )

        else:

            st.warning(
                "この条件では利益が出ません。"
            )

        if st.button(
            "この商品を在庫監視リストに登録",
            type="primary",
            use_container_width=True,
            key="yahoo_register"
        ):

            if not yahoo_name.strip():

                st.warning(
                    "商品名を入力してください。"
                )

            elif not yahoo_url.strip():

                st.warning(
                    "ヤフオクの商品URLを入力してください。"
                )

            else:

                new_row = pd.DataFrame([{
                    "商品名":
                        yahoo_name.strip(),

                    "ヤフオクURL":
                        yahoo_url.strip(),

                    "仕入価格":
                        yahoo_cost,

                    "送料":
                        yahoo_shipping,

                    "Amazon販売価格":
                        yahoo_amazon_price,

                    "Amazon手数料率":
                        yahoo_fee_rate,

                    "その他費用":
                        yahoo_other,

                    "利益":
                        round(yahoo_profit),

                    "ROI":
                        round(yahoo_roi, 1),

                    "在庫状況":
                        "確認待ち"
                }])

                yahoo_df = pd.concat(
                    [yahoo_df, new_row],
                    ignore_index=True
                )

                save_yahoo_data(
                    yahoo_df
                )

                st.success(
                    "在庫監視リストに登録しました。"
                )

    # -----------------------------------------------------
    # 在庫管理
    # -----------------------------------------------------

    with inventory_tab:
        if st.button(
            "ヤフオク在庫を自動チェック",
            use_container_width=True,
            key="yahoo_auto_check"
        ):
            if yahoo_df.empty:
                st.warning("在庫監視リストに商品がありません。")
            else:
                for i in yahoo_df.index:
                    yahoo_df.at[i, "在庫状況"] = check_yahoo_stock(
                        yahoo_df.at[i, "ヤフオクURL"]
                    )

                save_yahoo_data(yahoo_df)
                st.success("ヤフオクの在庫状況を自動チェックしました。")
                st.rerun()
        st.subheader("ヤフオク在庫管理")

        if yahoo_df.empty:

            st.info(
                "登録されている商品はまだありません。"
            )

        else:

            edited_df = st.data_editor(
                yahoo_df,
                use_container_width=True,
                hide_index=True,

                column_config={

                    "ヤフオクURL":
                        st.column_config.LinkColumn(
                            "ヤフオク",
                            display_text="商品を見る"
                        ),

                    "在庫状況":
                        st.column_config.SelectboxColumn(
                            "在庫状況",
                            options=[
                                "確認待ち",
                                "在庫あり",
                                "在庫なし",
                                "仕入済み",
                                "Amazon出品中",
                                "販売済み"
                            ],
                            required=True
                        )
                },

                disabled=[
                    "利益",
                    "ROI"
                ],

                key="yahoo_editor"
            )

            if st.button(
                "在庫情報を保存",
                use_container_width=True,
                key="save_inventory"
            ):

                save_yahoo_data(
                    edited_df
                )

                st.success(
                    "在庫情報を保存しました。"
                )

            st.download_button(
                "在庫リストをCSVでダウンロード",
                data=edited_df.to_csv(
                    index=False
                ).encode("utf-8-sig"),
                file_name="yahoo_inventory.csv",
                mime="text/csv",
                use_container_width=True
            )

    st.divider()

    st.info(
        "現在は手動在庫管理です。"
        "次の段階でヤフオク在庫の自動監視と"
        "価格変動アラートを追加します。"
    )
   
