import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageDraw, ImageFont
import datetime
import io
import json
import os
import urllib.request 
import re 
import time

# --- 設定頁面 ---
st.set_page_config(page_title="海鮮報價營運系統", page_icon="🦀", layout="wide")

# ====== 🔒 安全驗證區塊 ======
def check_password():
    if "app_password" in st.secrets:
        correct_password = str(st.secrets["app_password"])
    else:
        return True

    password_input = st.sidebar.text_input("🔒 管理員登入", type="password")
    if password_input == correct_password:
        return True
    
    st.sidebar.warning("請輸入密碼以解鎖")
    st.title("🔒 系統鎖定中")
    st.info("請在左側選單輸入管理員密碼以繼續。")
    return False

if not check_password():
    st.stop()

# --- 0. 自動下載中文字體 ---
def download_font():
    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Bold.otf"
    font_path = "NotoSansCJKtc-Bold.otf"
    if not os.path.exists(font_path):
        with st.spinner('正在下載中文字體...'):
            try:
                urllib.request.urlretrieve(font_url, font_path)
            except:
                pass
    return font_path

# --- 1. 連線設定 ---
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(st.secrets["service_account_json"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- 2. 繪圖函式 ---
def create_image(data_df, date_str, manual_upload=None):
    font_path = download_font()
    width = 1600 
    margin = 60
    col_gap = 100 
    col_width = (width - (margin * 2) - col_gap) / 2 
    
    c_bg_fallback = "#FDFCF5"
    c_header_bg = "#C19A6B" 
    c_header_text = "#FFFFFF"
    c_item_title = "#5C4033" 
    c_text = "#4A4A4A"       
    c_price = "#333333"      
    c_line = "#E0D6CC"       
    c_note_bg = "#F2EBE5"    
    c_note_text = "#8E7878"  

    try:
        font_header = ImageFont.truetype(font_path, 80)
        font_date = ImageFont.truetype(font_path, 40)
        font_title = ImageFont.truetype(font_path, 60)
        font_spec = ImageFont.truetype(font_path, 40)
        font_price = ImageFont.truetype(font_path, 50)
        font_note = ImageFont.truetype(font_path, 36)
        font_footer = ImageFont.truetype(font_path, 30)
    except:
        font_header = ImageFont.load_default()
    
    grouped = list(data_df.groupby('品項名稱', sort=False))
    y_col1 = 350 
    y_col2 = 350 
    for i, (name, group) in enumerate(grouped):
        item_h = 80 + len(group) * 60 + 80 + 60
        if y_col1 <= y_col2:
            y_col1 += item_h
        else:
            y_col2 += item_h
    total_height = max(y_col1, y_col2) + 100 

    bg_source = None
    if os.path.exists("bg_cny.png"): bg_source = "bg_cny.png"
    elif os.path.exists("bg_cny.jpg"): bg_source = "bg_cny.jpg"
    elif os.path.exists("bg_2026.png"): bg_source = "bg_2026.png"

    is_custom_bg = False
    if bg_source:
        try:
            bg_img = Image.open(bg_source).convert("RGB")
            bg_img = bg_img.resize((width, int(total_height)))
            img = bg_img
            is_custom_bg = True
        except Exception as e:
            img = Image.new("RGB", (width, int(total_height)), c_bg_fallback)
    else:
        img = Image.new("RGB", (width, int(total_height)), c_bg_fallback)

    watermark_source = None
    if os.path.exists("logo.png"): watermark_source = "logo.png"
    elif os.path.exists("logo.jpg"): watermark_source = "logo.jpg"
    elif manual_upload is not None: watermark_source = manual_upload

    if watermark_source:
        try:
            wm = Image.open(watermark_source).convert("RGBA")
            target_w = int(width * 0.5)
            ratio = target_w / float(wm.size[0])
            target_h = int(float(wm.size[1]) * float(ratio))
            wm = wm.resize((target_w, target_h))
            r, g, b, a = wm.split()
            a = a.point(lambda p: p * 0.10) 
            wm.putalpha(a)
            x_pos = (width - target_w) // 2
            y_pos = (int(total_height) - target_h) // 2
            img.paste(wm, (x_pos, y_pos), wm)
        except:
            pass

    draw = ImageDraw.Draw(img, "RGBA") 
    header_h = 280
    
    if is_custom_bg:
        draw.rectangle([(0, 0), (width, header_h)], fill=(193, 154, 107, 200)) 
    else:
        draw.rectangle([(0, 0), (width, header_h)], fill=c_header_bg)

    draw.text((margin, 50), "本週最新時價", fill=c_header_text, font=font_header)
    draw.text((margin, 170), f"報價日期：{date_str}", fill="#FFF8DC", font=font_date) 
    draw.text((width - margin - 500, 180), "※ 價格波動，以現場為主", fill="#F0E68C", font=font_date)

    cursor_l = 330
    cursor_r = 330
    for i, (name, group) in enumerate(grouped):
        if cursor_l <= cursor_r:
            current_x = margin
            is_left = True
        else:
            current_x = margin + col_width + col_gap
            is_left = False
        current_y = cursor_l if is_left else cursor_r
        
        draw.text((current_x, current_y), f"● {name}", fill=c_item_title, font=font_title)
        current_y += 80
        
        for idx, row in group.iterrows():
            spec = str(row['規格'])
            price = str(row['本週價格']) 
            draw.text((current_x + 20, current_y), spec, fill=c_text, font=font_spec)
            
            if price.strip() and "$" not in price and "售完" not in price:
                price_display = f"${price}"
            else:
                price_display = price
            
            col_right_edge = current_x + col_width
            w_price = draw.textlength(price_display, font=font_price)
            draw.text((col_right_edge - w_price, current_y), price_display, fill=c_price, font=font_price)
            
            w_spec = draw.textlength(spec, font=font_spec)
            line_start = current_x + 20 + w_spec + 20
            line_end = col_right_edge - w_price - 20
            if line_end > line_start:
                draw.line([(line_start, current_y + 25), (line_end, current_y + 25)], fill=c_line, width=1)
            current_y += 60

        service_val = group.iloc[0]['代工資訊']
        service_info = str(service_val) if pd.notna(service_val) else ""
        if service_info and service_info.strip() != "":
            box_h = 50
            draw.rectangle([(current_x, current_y + 5), (current_x + col_width, current_y + 5 + box_h)], fill="#F2EBE5")
            draw.text((current_x + 20, current_y + 10), f"▶ {service_info}", fill=c_note_text, font=font_note)
            current_y += 80
        current_y += 50
        if is_left:
            cursor_l = current_y
        else:
            cursor_r = current_y
    footer_y = max(cursor_l, cursor_r) + 20
    draw.line([(margin, footer_y), (width - margin, footer_y)], fill=c_line, width=2)
    draw.text((margin, footer_y + 30), "Generated by SmallOrange seafood bot", fill="#CCCCCC", font=font_footer)
    return img

def clean_price(price_str):
    if not isinstance(price_str, str): return 0
    price_str = price_str.replace(",", "").strip()
    
    money_pattern = re.search(r'\$(\d+\.?\d*)', price_str)
    if money_pattern: return float(money_pattern.group(1))
    
    yuan_pattern = re.search(r'(\d+\.?\d*)元', price_str)
    if yuan_pattern: return float(yuan_pattern.group(1))

    nums = re.findall(r"[-+]?\d*\.\d+|\d+", price_str.replace("$", ""))
    if nums:
        float_nums = [float(n) for n in nums]
        return max(float_nums)
        
    return 0

# --- 3. Streamlit 主程式 ---
st.title("🦀 海鮮報價營運系統")

try:
    client = get_google_sheet_client()
    sheet_url = st.secrets["sheet_url"]
    sheet = client.open_by_url(sheet_url).sheet1
    data = sheet.get_all_values()
    
    raw_headers = [h.strip() for h in data[0]]
    headers = []
    seen_count = {}
    for h in raw_headers:
        if h in seen_count:
            seen_count[h] += 1
            headers.append(f"{h}_{seen_count[h]}")
        else:
            seen_count[h] = 0
            headers.append(h)
    df = pd.DataFrame(data[1:], columns=headers)
    
    # 紀錄每一筆資料對應的真實 Google Sheet 列數 (因為有標題，所以 index + 2)
    df['sheet_row'] = df.index + 2 
    
    st.success("✅ 成功連線資料庫")

    bg_exists = False
    if os.path.exists("bg_cny.png") or os.path.exists("bg_cny.jpg"):
        bg_exists = True
        st.caption("✅ 已啟用新年背景 (bg_cny)")
    elif os.path.exists("bg_2026.png") or os.path.exists("bg_2026.jpg"):
         st.caption("✅ 已啟用新年背景 (bg_2026)")
    else:
        st.caption("使用預設背景")

    if os.path.exists("logo.png") or os.path.exists("logo.jpg"):
        st.caption("✅ 已啟用固定浮水印")

    uploaded_watermark = None
    if not (os.path.exists("logo.png") or os.path.exists("logo.jpg")):
        with st.expander("🎨 上傳臨時浮水印", expanded=False):
            uploaded_watermark = st.file_uploader("上傳圖片", type=["png", "jpg"])

    tab1, tab2 = st.tabs(["📝 報價與成本管理", "📊 營運數據分析"])

    with tab1:
        col_date, col_info = st.columns([1, 2])
        with col_date:
            selected_date = st.date_input("選擇報價日期", datetime.date.today())
            date_str = selected_date.strftime("%Y/%m/%d")
        
        fixed_cols = ['品項名稱', '規格', '代工資訊', 'sheet_row']
        all_cols = [c for c in df.columns if c not in fixed_cols and "Unnamed" not in c and c != ""]
        cost_cols = [c for c in all_cols if "_成本" in c]
        price_cols = [c for c in all_cols if "_成本" not in c]
        
        last_price_col = price_cols[-1] if price_cols else None
        last_cost_col = cost_cols[-1] if cost_cols else None
        
        with st.form("price_update_form"):
            st.subheader(f"📝 輸入價格與成本 ({date_str})")
            st.caption("💡 提示：若本週暫停供應，請將「售價」留白，即可在報價圖片中自動隱藏。若要長期下架，請在 Sheet 上的名稱加入 [停售]。")
            
            updates = [] # 用來收集此次要寫入的資料
            grouped = df.groupby('品項名稱', sort=False)
            
            for name, group in grouped:
                # [V7.5 長期下架過濾]：名稱有 [停售] 或 [隱藏]，就不顯示在更新表單中
                if "[停售]" in name or "[隱藏]" in name:
                    continue

                st.markdown(f"#### 🐟 {name}")
                for idx, row in group.iterrows():
                    spec = row['規格']
                    last_p_val = str(row[last_price_col]) if last_price_col and pd.notna(row[last_price_col]) else ""
                    if isinstance(row.get(last_price_col), pd.Series): last_p_val = str(row[last_price_col].iloc[0])
                    
                    last_c_val = str(row[last_cost_col]) if last_cost_col and pd.notna(row[last_cost_col]) else ""
                    if isinstance(row.get(last_cost_col), pd.Series): last_c_val = str(row[last_cost_col].iloc[0])

                    c1, c2, c3 = st.columns([2, 2, 2])
                    with c1:
                        val_p = st.text_input(f"{spec} 售價", value=last_p_val, key=f"p_{idx}", placeholder="售價留空即隱藏")
                    with c2:
                        val_c = st.text_input(f"成本", value=last_c_val, key=f"c_{idx}", placeholder="成本")
                    with c3:
                        st.markdown(f"<small style='color:gray'>上週售價: {last_p_val}<br>上週成本: {last_c_val}</small>", unsafe_allow_html=True)
                    
                    # 將表單數據綁定到真實的 Sheet 列數
                    updates.append({
                        'sheet_row': row['sheet_row'],
                        'name': name,
                        'spec': spec,
                        'service': row['代工資訊'],
                        'price': val_p,
                        'cost': val_c
                    })
                st.divider()
            
            submitted = st.form_submit_button("🚀 確認發布", type="primary")
            
        if submitted:
            try:
                p_idx = raw_headers.index(date_str)
                target_price_col = p_idx + 1
                st.info(f"ℹ️ {date_str} 資料已存在，執行覆蓋更新。")
                
                cost_col_name = f"{date_str}_成本"
                if cost_col_name in raw_headers:
                    target_cost_col = raw_headers.index(cost_col_name) + 1
                else:
                    target_cost_col = target_price_col + 1
            except ValueError:
                current_cols = len(data[0])
                target_price_col = current_cols + 1
                target_cost_col = current_cols + 2
                
                required_cols = target_cost_col 
                current_sheet_cols = sheet.col_count
                if required_cols > current_sheet_cols:
                    sheet.add_cols(required_cols - current_sheet_cols)

                sheet.update_cell(1, target_price_col, date_str)
                sheet.update_cell(1, target_cost_col, f"{date_str}_成本")
                st.success(f"📅 建立新日期：{date_str}")

            # 精準批次寫入：利用前面記下的 sheet_row，就不怕隱藏商品導致錯位
            cells_to_update = []
            for u in updates:
                cells_to_update.append(gspread.Cell(u['sheet_row'], target_price_col, u['price']))
                if target_cost_col:
                    cells_to_update.append(gspread.Cell(u['sheet_row'], target_cost_col, u['cost']))

            try:
                sheet.update_cells(cells_to_update)
                st.success(f"✅ 已成功更新 {date_str} 的資料！")
            except Exception as e:
                st.error(f"寫入失敗：{e}")

            # [V7.5 報價單自動去白機制]
            # 只挑出「有輸入售價」的項目去產圖，完全過濾掉缺貨/空白項目
            plot_data = [u for u in updates if u['price'].strip() != ""]
            
            if not plot_data:
                st.warning("⚠️ 提示：您尚未填寫任何售價，無法生成報價圖片。")
            else:
                plot_df = pd.DataFrame(plot_data)
                plot_df.rename(columns={'name':'品項名稱', 'spec':'規格', 'service':'代工資訊', 'price':'本週價格'}, inplace=True)
                
                st.subheader("🖼️ 您的報價單")
                image = create_image(plot_df, date_str, manual_upload=uploaded_watermark)
                st.image(image, caption="長按可下載", use_column_width=True)
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                byte_im = buf.getvalue()
                st.download_button(label="📥 下載圖片", data=byte_im, file_name=f"menu_{date_str.replace('/','')}.png", mime="image/png")

    with tab2:
        st.subheader("📈 營運主管看板")
        
        # 即使名稱有 [停售]，仍然允許在下拉選單被選取，供主管查閱歷史
        all_items = df['品項名稱'].unique()
        c_sel1, c_sel2 = st.columns(2)
        with c_sel1: selected_item = st.selectbox("品項 (包含歷史停售)", all_items)
        with c_sel2: selected_spec = st.selectbox("規格", df[df['品項名稱'] == selected_item]['規格'].unique()) if selected_item else None
        
        if selected_item and selected_spec:
            target_row = df[(df['品項名稱'] == selected_item) & (df['規格'] == selected_spec)]
            if not target_row.empty:
                only_cost_mode = st.checkbox("☐ 僅顯示成本趨勢 (排除售價干擾)")

                date_cols = [c for c in df.columns if c not in fixed_cols and "_成本" not in c and "Unnamed" not in c and c != ""]
                chart_data = []
                for d in date_cols:
                    p_str = str(target_row.iloc[0][d])
                    c_col = f"{d}_成本"
                    c_str = str(target_row.iloc[0][c_col]) if c_col in target_row.columns else "0"
                    
                    p_val = clean_price(p_str)
                    c_val = clean_price(c_str)
                    
                    if p_val > 0 or c_val > 0:
                        chart_data.append({
                            "日期": d,
                            "原始售價(Text)": p_str,
                            "售價": p_val,
                            "原始成本(Text)": c_str,
                            "成本": c_val
                        })
                
                if chart_data:
                    chart_df = pd.DataFrame(chart_data)
                    chart_df['temp_sort_date'] = pd.to_datetime(chart_df['日期'], errors='coerce')
                    chart_df = chart_df.sort_values(by='temp_sort_date')
                    
                    chart_df["毛利$"] = chart_df["售價"] - chart_df["成本"]
                    chart_df["毛利率%"] = chart_df.apply(lambda x: round((x["毛利$"]/x["售價"]*100), 1) if x["售價"]>0 else 0, axis=1)

                    valid_prices = chart_df[chart_df['售價'] > 0]
                    last_valid_price = int(valid_prices.iloc[-1]['售價']) if not valid_prices.empty else 0

                    valid_costs = chart_df[chart_df['成本'] > 0]
                    if not valid_costs.empty:
                        last_valid_cost = int(valid_costs.iloc[-1]['成本'])
                        last_cost_date = valid_costs.iloc[-1]['日期']
                    else:
                        last_valid_cost = 0
                        last_cost_date = "無"

                    if last_valid_price > 0 and last_valid_cost > 0:
                        est_profit = last_valid_price - last_valid_cost
                        est_margin = round((est_profit / last_valid_price * 100), 1)
                    else:
                        est_profit = 0
                        est_margin = 0
                    
                    kpi1, kpi2, kpi3 = st.columns(3)
                    if only_cost_mode:
                        kpi1.metric("最新售價", "---") 
                        kpi2.metric("最新成本", f"${last_valid_cost}", help=f"資料來源日期: {last_cost_date}")
                        kpi3.metric("最新毛利率", "---") 
                    else:
                        kpi1.metric("最新售價", f"${last_valid_price}")
                        kpi2.metric("最新成本", f"${last_valid_cost}", help=f"資料來源日期: {last_cost_date}")
                        kpi3.metric("最新毛利率 (估)", f"{est_margin}%", 
                                    delta=f"{est_profit}元" if est_profit > 0 else "無利潤")
                    
                    st.markdown("---")
                    st.markdown("#### 📊 價格波動趨勢圖")
                    
                    if only_cost_mode:
                        plot_df = chart_df[chart_df['成本'] > 0].set_index("日期")[["成本"]]
                        st.line_chart(plot_df, color=["#8E7878"])
                        st.caption("ℹ️ 目前為「僅看成本」模式，售價線已隱藏。")
                    else:
                        line_chart_data = chart_df.set_index("日期")[["售價", "成本"]]
                        st.line_chart(line_chart_data, color=["#A55B5B", "#8E7878"])

                    with st.expander("查看詳細數據表"):
                         display_cols = ["日期", "原始售價(Text)", "原始成本(Text)", "售價", "成本", "毛利$", "毛利率%"]
                         st.dataframe(chart_df[display_cols].set_index("日期"))
                else:
                    st.warning("無數據")

except Exception as e:
    st.error(f"錯誤：{e}")
