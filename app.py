import streamlit as st
import pandas as pd
import requests
from urllib.parse import quote

st.set_page_config(page_title="楽天 × Amazon 利益リサーチ", page_icon="📊", layout="wide")
st.title("楽天 × Amazon 利益リサーチ")
st.caption("楽天価格を自動検索・Amazon商品検索・利益計算。Amazon価格は手入力です。")

st.subheader("楽天市場の商品検索")
keyword = st.text_input("検索したい商品名", placeholder="例：Panasonic")

if st.button("楽天で検索"):
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
                st.error(f"楽天APIエラー HTTP {response.status_code}: {response.text[:300]}")
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
                        "Amazon検索": "https://www.amazon.co.jp/s?k=" + quote(name),
                    })
                st.dataframe(
                    pd.DataFrame(rows),
                    column_config={
                        "楽天URL": st.column_config.LinkColumn("楽天の商品ページ", display_text="楽天を開く"),
                        "Amazon検索": st.column_config.LinkColumn("Amazonで検索", display_text="Amazonを開く"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("該当する商品がありません。")
        except requests.RequestException as e:
            st.error(f"通信エラー: {e}")
        except KeyError:
            st.error("Streamlit Secretsの楽天API設定を確認してください。")
        except Exception as e:
            st.error(f"検索エラー: {type(e).__name__}: {e}")

st.divider()
st.subheader("利益シミュレーション")
left, right = st.columns(2)
with left:
    cost = st.number_input("楽天仕入れ価格（円）", min_value=0, value=5000, step=100)
    price = st.number_input("Amazon販売価格（円）", min_value=0, value=7000, step=100)
with right:
    fee_rate = st.number_input("Amazon販売手数料率（％）", min_value=0.0, max_value=100.0, value=10.4, step=0.1)
    shipping = st.number_input("送料・その他費用（円）", min_value=0, value=500, step=100)

fee = price * fee_rate / 100
profit = price - cost - fee - shipping
roi = profit / cost * 100 if cost > 0 else 0

a, b, c = st.columns(3)
a.metric("予想利益", f"{profit:,.0f}円")
b.metric("ROI", f"{roi:.1f}%")
c.metric("販売手数料", f"{fee:,.0f}円")
st.caption("概算です。FBA手数料や保管料などは送料・その他費用に含めてください。")

st.divider()
st.subheader("CSV読み込み（任意）")
uploaded = st.file_uploader("商品CSVを選択", type=["csv"])
if uploaded is not None:
    try:
        st.dataframe(pd.read_csv(uploaded), use_container_width=True)
    except Exception as e:
        st.error(f"CSV読み込みエラー: {e}")
