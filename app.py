import streamlit as st
import pandas as pd

st.set_page_config(page_title='楽天 × Amazon 利益リサーチ', page_icon='📊', layout='wide')
st.title('楽天 × Amazon 利益リサーチ')
st.caption('試作版：価格は手入力またはCSVで読み込みます。リアルタイム価格取得・自動商品照合は未接続です。')
import requests

st.subheader("楽天市場の商品検索")

keyword = st.text_input("検索したい商品名", placeholder="例：パナソニック ドライヤー")

if st.button("楽天で検索"):
    if not keyword.strip():
        st.warning("商品名を入力してください")

    else:
        try:
            response = requests.get(
                "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
                params={
                    "applicationId": st.secrets["RAKUTEN_APP_ID"],
                                        "accessKey": st.secrets["RAKUTEN_ACCESS_KEY"],
                    "keyword": keyword,
                    "hits": 20,
                   "format": "json",
            },
            headers={
    "Referer": "https://rakuten-amazon-research-tygw8zohahgg2gvwwnasdf.streamlit.app/",
    "Origin": "https://rakuten-amazon-research-tygw8zohahgg2gvwwnasdf.streamlit.app",
    "Authorization": f'Bearer {st.secrets["RAKUTEN_ACCESS_KEY"]}',
},
            
            timeout=15,
            )
            if not response.ok:
                st.error(f"楽天APIエラー（HTTP {response.status_code}）")
                st.code(response.text[:1500])
                st.stop()
            items = response.json().get("Items", [])

            if items:
                rows = []
                for entry in items:
                    item = entry.get("Item", entry)
                    
                        
rows.append({
    "商品名": item.get("itemName", ""),
    "楽天価格": item.get("itemPrice", 0),
    "商品URL": item.get("itemUrl", ""),
    "Amazon検索": "https://www.amazon.co.jp/s?k=" + requests.utils.quote(item.get("itemName", "")),
})

                    
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            else:
                st.info("該当する商品がありません")

        except Exception as e:
            st.error(f"検索に失敗しました: {e}")

with st.sidebar:
    st.header('計算条件')
    fee_pct = st.number_input('Amazon販売手数料（%）', 0.0, 50.0, 10.4, 0.1)
    fulfill = st.number_input('FBAまたは自己発送の費用（円/点）', 0, 10000, 450, 10)
    inbound = st.number_input('Amazon倉庫への納品費・梱包費（円/点）', 0, 10000, 100, 10)
    small = st.checkbox('小口出品（100円/点、税抜）', value=True)
    min_profit = st.number_input('最低利益（円）', 0, 100000, 1000, 100)
    min_roi = st.number_input('最低ROI（%）', 0, 1000, 20, 5)
    st.caption('費用は税込・税抜の前提を統一して入力してください。ポイントは現金利益とは分けて表示します。')

cols = ['JAN','商品名','楽天価格','楽天送料','楽天ポイント','Amazon価格','楽天URL','AmazonURL']
example = pd.DataFrame([
    ['4900000000001','サンプル商品A（架空）',1980,0,100,3980,'',''],
    ['4900000000002','サンプル商品B（架空）',3200,0,160,5980,'',''],
    ['4900000000003','サンプル商品C（架空）',4500,0,200,7980,'',''],
], columns=cols)
uploaded = st.file_uploader('商品CSVを読み込む（任意）', type=['csv'])
if uploaded is not None:
    try:
        data = pd.read_csv(uploaded, dtype={'JAN':str}, encoding='utf-8-sig')
    except UnicodeDecodeError:
        data = pd.read_csv(uploaded, dtype={'JAN':str}, encoding='cp932')
    for col in cols:
        if col not in data.columns: data[col] = '' if col in ['JAN','商品名','楽天URL','AmazonURL'] else 0
    data = data[cols]
else:
    data = example

st.subheader('商品データ')
edited = st.data_editor(data, num_rows='dynamic', hide_index=True, use_container_width=True)
for col in ['楽天価格','楽天送料','楽天ポイント','Amazon価格']:
    edited[col] = pd.to_numeric(edited[col], errors='coerce').fillna(0)
result = edited.copy()
result['仕入れ原価'] = result['楽天価格'] + result['楽天送料']
result['販売手数料'] = (result['Amazon価格'] * fee_pct / 100).round(0)
result['小口基本成約料'] = 100 if small else 0
result['発送関連費'] = fulfill + inbound
result['現金ベース利益'] = result['Amazon価格'] - result['仕入れ原価'] - result['販売手数料'] - result['小口基本成約料'] - result['発送関連費']
result['ポイント考慮利益'] = result['現金ベース利益'] + result['楽天ポイント']
result['ROI(%)'] = (result['現金ベース利益'] / result['仕入れ原価'].replace(0, float('nan')) * 100).round(1)
result['利益率(%)'] = (result['現金ベース利益'] / result['Amazon価格'].replace(0, float('nan')) * 100).round(1)
filtered = result[(result['現金ベース利益'] >= min_profit) & (result['ROI(%)'] >= min_roi)].sort_values('現金ベース利益', ascending=False)
st.subheader(f'仕入れ候補：{len(filtered)}件')
st.dataframe(filtered, use_container_width=True, hide_index=True)
st.download_button('候補をCSVでダウンロード', filtered.to_csv(index=False).encode('utf-8-sig'), 'profit_candidates.csv', 'text/csv')
st.info('重要：Amazonの出品可否、価格競争、返品、消費税、ポイント利用条件、FBAの保管・長期在庫費用は別途確認が必要です。')
