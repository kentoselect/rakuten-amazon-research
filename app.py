import streamlit as st
import pandas as pd
import requests
import json
import re
from urllib.parse import quote
from pathlib import Path
from bs4 import BeautifulSoup


st.set_page_config(page_title="ケントセレクト Amazonリサーチ", page_icon="📊", layout="wide")
st.title("ケントセレクト Amazonリサーチ")
st.caption("楽天・ヤフオクからAmazon販売候補をリサーチ")
rakuten_tab, yahoo_tab = st.tabs(["楽天 × Amazon", "ヤフオク × Amazon中古"])

with rakuten_tab:
    st.header("楽天 × Amazon 利益リサーチ")
    st.subheader("楽天市場の商品検索")
    keyword = st.text_input("検索したい商品名", placeholder="例：Panasonic", key="rakuten_keyword")
    if st.button("楽天で検索", key="rakuten_search"):
        if not keyword.strip():
            st.warning("商品名を入力してください。")
        else:
            try:
                access_key = st.secrets["RAKUTEN_ACCESS_KEY"]
                r = requests.get(
                    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
                    params={"applicationId": st.secrets["RAKUTEN_APP_ID"], "accessKey": access_key, "keyword": keyword.strip(), "hits": 20, "format": "json"},
                    headers={"Authorization": f"Bearer {access_key}"}, timeout=15,
                )
                if not r.ok:
                    st.error(f"楽天APIエラー HTTP {r.status_code}: {r.text[:300]}")
                else:
                    rows = []
                    for entry in r.json().get("Items", []):
                        item = entry.get("Item", entry)
                        name = item.get("itemName", "")
                        rows.append({"商品名": name, "楽天価格": item.get("itemPrice", 0), "楽天URL": item.get("itemUrl", ""), "Amazon検索": "https://www.amazon.co.jp/s?k=" + quote(name)})
                    if rows:
                        st.dataframe(pd.DataFrame(rows), column_config={
                            "楽天URL": st.column_config.LinkColumn("楽天の商品ページ", display_text="楽天を開く"),
                            "Amazon検索": st.column_config.LinkColumn("Amazonで検索", display_text="Amazonを開く"),
                        }, hide_index=True, use_container_width=True)
                    else:
                        st.info("該当する商品がありません。")
            except KeyError:
                st.error("Streamlit Secretsの楽天API設定を確認してください。")
            except Exception as e:
                st.error(f"検索エラー: {type(e).__name__}: {e}")

    st.divider()
    st.subheader("利益シミュレーション")
    c1, c2 = st.columns(2)
    with c1:
        cost = st.number_input("楽天仕入れ価格（円）", min_value=0, value=5000, step=100)
        price = st.number_input("Amazon販売価格（円）", min_value=0, value=7000, step=100)
    with c2:
        fee_rate = st.number_input("Amazon販売手数料率（％）", min_value=0.0, max_value=100.0, value=10.4, step=0.1)
        shipping = st.number_input("送料・その他費用（円）", min_value=0, value=500, step=100)
    fee = price * fee_rate / 100
    profit = price - cost - fee - shipping
    roi = profit / cost * 100 if cost else 0
    a, b, c = st.columns(3)
    a.metric("予想利益", f"{profit:,.0f}円")
    b.metric("ROI", f"{roi:.1f}%")
    c.metric("販売手数料", f"{fee:,.0f}円")

with yahoo_tab:
    st.header("ヤフオク × Amazon 中古リサーチ")
    DATA_FILE = Path("yahoo_inventory.csv")
    COLUMNS = ["商品名", "ヤフオクURL", "仕入価格", "送料", "Amazon販売価格", "Amazon手数料率", "その他費用", "利益", "ROI", "在庫状況"]

    def load_data():
        if DATA_FILE.exists():
            try:
                df = pd.read_csv(DATA_FILE)
                for col in COLUMNS:
                    if col not in df.columns:
                        df[col] = ""
                return df[COLUMNS]
            except Exception:
                pass
        return pd.DataFrame(columns=COLUMNS)

    def save_data(df):
        df.to_csv(DATA_FILE, index=False)

    df = load_data()
    research_tab, inventory_tab = st.tabs(["商品登録・利益計算", "在庫管理"])

    with research_tab:
        name = st.text_input("商品名", placeholder="例：COACH バッグ", key="yahoo_name")
        url = st.text_input("ヤフオクの商品URL", placeholder="https://page.auctions.yahoo.co.jp/...", key="yahoo_url")
        if name.strip():
            st.link_button("Amazonで同じ商品を検索", "https://www.amazon.co.jp/s?k=" + quote(name.strip()), use_container_width=True)
        l, r = st.columns(2)
        with l:
            y_cost = st.number_input("ヤフオク仕入れ価格（円）", min_value=0, value=5000, step=100)
            y_ship = st.number_input("仕入れ送料（円）", min_value=0, value=0, step=100)
            y_other = st.number_input("その他費用（円）", min_value=0, value=0, step=100)
        with r:
            y_price = st.number_input("Amazon販売予定価格（円）", min_value=0, value=7000, step=100)
            y_fee_rate = st.number_input("Amazon販売手数料率（％）", min_value=0.0, max_value=100.0, value=10.4, step=0.1)
        y_fee = y_price * y_fee_rate / 100
        total = y_cost + y_ship + y_other
        y_profit = y_price - total - y_fee
        y_roi = y_profit / total * 100 if total else 0
        m1, m2, m3 = st.columns(3)
        m1.metric("予想利益", f"{y_profit:,.0f}円")
        m2.metric("ROI", f"{y_roi:.1f}%")
        m3.metric("Amazon手数料", f"{y_fee:,.0f}円")
        if st.button("この商品を在庫監視リストに登録", type="primary", use_container_width=True):
            if not name.strip() or not url.strip():
                st.warning("商品名とヤフオクURLを入力してください。")
            else:
                row = pd.DataFrame([{"商品名": name.strip(), "ヤフオクURL": url.strip(), "仕入価格": y_cost, "送料": y_ship, "Amazon販売価格": y_price, "Amazon手数料率": y_fee_rate, "その他費用": y_other, "利益": round(y_profit), "ROI": round(y_roi, 1), "在庫状況": check_yahoo_stock(url.strip())}])
                df = pd.concat([df, row], ignore_index=True)
                save_data(df)
                st.success("在庫監視リストに登録しました。")

    with inventory_tab:
        st.subheader("ヤフオク在庫管理")
        if st.button("ヤフオク在庫を自動チェック", use_container_width=True):
            if df.empty:
                st.warning("在庫監視リストに商品がありません。")
            else:
                with st.spinner("ヤフオクの在庫を確認しています..."):
                    for i in df.index:
                        df.at[i, "在庫状況"] = check_yahoo_stock(df.at[i, "ヤフオクURL"])
                    save_data(df)
                st.success("ヤフオクの在庫状況を自動チェックしました。")
                st.rerun()
        if df.empty:
            st.info("登録されている商品はまだありません。")
        else:
            edited = st.data_editor(df, use_container_width=True, hide_index=True, column_config={
                "ヤフオクURL": st.column_config.LinkColumn("ヤフオク", display_text="商品を見る"),
                "在庫状況": st.column_config.SelectboxColumn("在庫状況", options=["確認エラー", "在庫あり", "在庫なし", "仕入済み", "Amazon出品中", "販売済み"], required=True),
            }, disabled=["利益", "ROI"])
            if st.button("在庫情報を保存", use_container_width=True):
                save_data(edited)
                st.success("在庫情報を保存しました。")
            st.download_button("在庫リストをCSVでダウンロード", edited.to_csv(index=False).encode("utf-8-sig"), "yahoo_inventory.csv", "text/csv", use_container_width=True)

    st.divider()
    st.info("登録したヤフオク商品URLを使って、在庫状況を自動チェックできます。")
