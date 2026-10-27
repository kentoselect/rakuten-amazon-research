if name.strip():
            st.link_button(
                "Amazonで同じ商品を検索",
                "https://www.amazon.co.jp/s?k=" + quote(name.strip()),
                use_container_width=True,
            )

        left, right = st.columns(2)
        with left:
            y_cost = st.number_input(
                "ヤフオク仕入れ価格（円）",
                min_value=0,
                value=5000,
                step=100,
                key="yahoo_cost",
            )
            y_ship = st.number_input(
                "仕入れ送料（円）", min_value=0, value=0, step=100
            )
            y_other = st.number_input(
                "その他費用（円）", min_value=0, value=0, step=100
            )

        with right:
            y_price = st.number_input(
                "Amazon販売予定価格（円）",
                min_value=0,
                value=7000,
                step=100,
            )
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

        if st.button(
            "この商品を在庫監視リストに登録",
            type="primary",
            use_container_width=True,
        ):
            if not name.strip() or not url.strip():
                st.warning("商品名とヤフオクURLを入力してください。")
            else:
                row = pd.DataFrame(
                    [
                        {
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
                        }
                    ]
                )
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
                    for index in df.index:
                        df.at[index, "在庫状況"] = check_yahoo_stock(
                            df.at[index, "ヤフオクURL"]
                        )
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
                    "ヤフオクURL": st.column_config.LinkColumn(
                        "ヤフオク", display_text="商品を見る"
                    ),
                    "在庫状況": st.column_config.SelectboxColumn(
                        "在庫状況",
                        options=[
                            "確認エラー",
                            "在庫あり",
                            "在庫なし",
                            "仕入済み",
                            "Amazon出品中",
                            "販売済み",
                        ],
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
    st.info("登録したヤフオク商品URLを使って、在庫状況を自動チェックできます。")
