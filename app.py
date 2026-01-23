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

# --- 設定頁面 ---
st.set_page_config(page_title="海鮮報價營運系統", page_icon="🦀", layout="wide")

# ====== 🔒 安全驗證區塊 ======
def check_password():
    if "app_password" in st.secrets:
        correct_password = str(st.secrets["app_password"])
    else:
        # 如果沒設定密碼，預設不鎖，或者提示錯誤
        # 為了方便您直接測試，這裡如果沒設 secrets 就不鎖
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

# --- 2. 繪圖函式 (只顯示售價，不顯示成本) ---
def create_image(data_df, date_str, manual_upload=None):
    font_path = download_font()
    width = 1600 
    margin = 60
    col_gap = 100 
    col_width = (width - (margin * 2) - col_gap) / 2 
    
    c_bg = "#FDFCF5"         
    c_header_bg = "#C19A6B"  
    c_header_text = "#FFFFFF"
    c_item_title = "#5C4033" 
    c_text = "#4A4A4A"       
    c_price = "#A55B5B"      
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

    img = Image.new("RGB", (width, int(total_height)), c_bg)
    
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
        except Exception as e:
            pass

    draw = ImageDraw.Draw(img)
    header_h = 280
    draw.rectangle([(0, 0), (width, header_h)], fill=c_header_bg)
    draw.text((margin, 50), "本週活體報價", fill=c_header_text, font=font_header)
    draw.text((margin, 170), f"報價日期：{date_str}", fill="#FFF8DC", font=font_date) 
    draw.text((width - margin - 500, 180), "※特殊狀況請示現場主管", fill="#F0E68C", font=font_date)

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
            price = str(row['本週價格']) # 只取售價
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
            draw.rectangle([(current_x, current_y + 5), (current_x + col_width, current_y + 5 + box_h)], fill=c_note_bg)
            draw.text((current_x + 20, current_y + 10), f"▶ {service_info}", fill=c_note_text, font=font_note)
            current_y += 80
        current_y += 50
        if is_left:
            cursor_l = current_y
        else:
            cursor_r = current_y
    footer_y = max(cursor_l, cursor_r) + 20
    draw.line([(margin, footer_y), (width - margin, footer_y)], fill=c_line, width=2)
    draw.text((margin, footer_y + 30), "Generated by SmallOrange seafood bot V6.1", fill="#CCCCCC", font=font_footer)
    return img

def clean_price(price_str):
    if not isinstance(price_str, str): return 0
    # 移除 $ 和 , 以及空白
    price_str = price_str.replace(",", "").replace("$", "").strip()
    # 抓取數字
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", price_str)
    if nums: return float(nums[0])
    return 0

# --- 3. Streamlit 主程式 ---
st.title("🦀 海鮮報價營運系統")

try:
    client = get_google_sheet_client()
    sheet_url = st.secrets["sheet_url"]
    sheet = client.open_by_url(sheet_url).sheet1
    data = sheet.get_all_values()
    
    # --- 處理標題與欄位識別 ---
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
    
    st.success("✅ 成功連線資料庫")

    # 浮水印
    uploaded_watermark = None
    if os.path.exists("logo.png") or os.path.exists("logo.jpg"):
        st.info("✅ 已套用固定浮水印")
    else:
        with st.expander("🎨 上傳臨時浮水印", expanded=False):
            uploaded_watermark = st.file_uploader("上傳圖片", type=["png", "jpg"])

    tab1, tab2 = st.tabs(["📝 報價與成本管理", "📊 營運數據分析"])

    # ====== 分頁 1: 更新報價 ======
    with tab1:
        col_date, col_info = st.columns([1, 2])
        with col_date:
            selected_date = st.date_input("選擇報價日期", datetime.date.today())
            date_str = selected_date.strftime("%Y/%m/%d")
        
        fixed_cols = ['品項名稱', '規格', '代工資訊']
        
        # 區分「售價欄位」與「成本欄位」
        # 邏輯：有 "_成本" 結尾的是成本，其他非固定欄位就是售價
        all_cols = [c for c in df.columns if c not in fixed_cols and "Unnamed" not in c and c != ""]
        cost_cols = [c for c in all_cols if "_成本" in c]
        price_cols = [c for c in all_cols if "_成本" not in c]
        
        last_price_col = price_cols[-1] if price_cols else None
        last_cost_col = cost_cols[-1] if cost_cols else None
        
        with st.form("price_update_form"):
            st.subheader(f"📝 輸入價格與成本 ({date_str})")
            st.caption("說明：請輸入本週的售價與成本。系統會自動隱藏成本，不顯示在客戶菜單上。")
            
            new_prices = []
            new_costs = []
            
            grouped = df.groupby('品項名稱', sort=False)
            for name, group in grouped:
                st.markdown(f"#### 🐟 {name}")
                for idx, row in group.iterrows():
                    spec = row['規格']
                    
                    # 取得上週數據
                    last_p_val = ""
                    last_c_val = ""
                    if last_price_col:
                        val = row[last_price_col]
                        if isinstance(val, pd.Series): val = val.iloc[0]
                        last_p_val = str(val) if pd.notna(val) else ""
                    
                    if last_cost_col:
                        val = row[last_cost_col]
                        if isinstance(val, pd.Series): val = val.iloc[0]
                        last_c_val = str(val) if pd.notna(val) else ""
                    
                    # 計算上週毛利參考
                    margin_txt = "無紀錄"
                    try:
                        p = clean_price(last_p_val)
                        c = clean_price(last_c_val)
                        if p > 0 and c > 0:
                            margin = (p - c) / p * 100
                            margin_txt = f"{margin:.1f}% (${int(p-c)})"
                        elif p > 0:
                            margin_txt = "缺成本"
                    except:
                        pass

                    # 介面佈局：左售價、中成本、右參考
                    c1, c2, c3 = st.columns([2, 2, 2])
                    
                    with c1:
                        val_p = st.text_input(f"{spec} 售價", value=last_p_val, key=f"p_{idx}", placeholder="客戶看到的價格")
                        new_prices.append(val_p)
                    with c2:
                        val_c = st.text_input(f"成本 (隱藏)", value=last_c_val, key=f"c_{idx}", placeholder="進貨成本")
                        new_costs.append(val_c)
                    with c3:
                        st.markdown(f"<small style='color:gray'>上週售價: {last_p_val}<br>上週成本: {last_c_val}<br>毛利: <b style='color:#A55B5B'>{margin_txt}</b></small>", unsafe_allow_html=True)
                
                st.divider()
            
            submitted = st.form_submit_button("🚀 確認發布 (存檔並產圖)", type="primary")
            
        if submitted:
            # 寫入邏輯：新增兩欄
            # 1. Date (售價)
            # 2. Date_成本 (成本)
            current_cols = len(data[0])
            
            # 更新 Header
            sheet.update_cell(1, current_cols + 1, date_str)
            sheet.update_cell(1, current_cols + 2, f"{date_str}_成本")
            
            progress_bar = st.progress(0)
            total_items = len(new_prices)
            
            # 批次寫入有點複雜，維持逐行寫入確保穩定
            for i in range(total_items):
                # 寫入售價
                sheet.update_cell(i + 2, current_cols + 1, new_prices[i])
                # 寫入成本
                sheet.update_cell(i + 2, current_cols + 2, new_costs[i])
                progress_bar.progress((i + 1) / total_items)
            
            st.success(f"已儲存！本週資料位於第 {current_cols+1} 與 {current_cols+2} 欄。")
            
            # 產圖 (只用售價)
            plot_df = df[['品項名稱', '規格', '代工資訊']].copy()
            plot_df['本週價格'] = new_prices
            
            st.subheader("🖼️ 您的報價單 (僅含售價)")
            image = create_image(plot_df, date_str, manual_upload=uploaded_watermark)
            st.image(image, caption="長按可下載", use_column_width=True)
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            byte_im = buf.getvalue()
            st.download_button(label="📥 下載圖片", data=byte_im, file_name=f"menu_{date_str.replace('/','')}.png", mime="image/png")

    # ====== 分頁 2: 數據分析 ======
    with tab2:
        st.subheader("📈 成本與售價走勢分析")
        
        all_items = df['品項名稱'].unique()
        c_sel1, c_sel2 = st.columns(2)
        with c_sel1:
            selected_item = st.selectbox("請選擇品項", all_items)
        with c_sel2:
            item_specs = df[df['品項名稱'] == selected_item]['規格'].unique()
            selected_spec = st.selectbox("請選擇規格", item_specs)
        
        if selected_item and selected_spec:
            target_row = df[(df['品項名稱'] == selected_item) & (df['規格'] == selected_spec)]
            
            if not target_row.empty:
                # 重新整理所有欄位，分辨日期
                # 我們的欄位格式： "YYYY/MM/DD" (售價) 和 "YYYY/MM/DD_成本" (成本)
                # 先找出所有的「基礎日期」
                all_cols = df.columns
                date_cols = [c for c in all_cols if c not in fixed_cols and "_成本" not in c and "Unnamed" not in c and c != ""]
                
                chart_data = []
                
                for d in date_cols:
                    # 售價
                    p_str = str(target_row.iloc[0][d]) if d in target_row.columns else "0"
                    p_val = clean_price(p_str)
                    
                    # 成本 (找對應的成本欄位)
                    c_col = f"{d}_成本"
                    # 有可能因為是舊資料，所以沒有成本欄位，要防呆
                    c_val = 0
                    if c_col in target_row.columns:
                        c_str = str(target_row.iloc[0][c_col])
                        c_val = clean_price(c_str)
                    
                    if p_val > 0: # 只有當有售價時才顯示
                        # 計算毛利
                        margin = p_val - c_val if c_val > 0 else 0
                        
                        chart_data.append({
                            "日期": d,
                            "售價": p_val,
                            "成本": c_val,
                            "毛利": margin
                        })
                
                if chart_data:
                    chart_df = pd.DataFrame(chart_data).set_index("日期")
                    
                    st.markdown("#### 📊 售價 vs 成本 比較圖")
                    # 雙色長條圖：顯示售價與成本
                    st.bar_chart(chart_df[["售價", "成本"]], color=["#A55B5B", "#C19A6B"]) 
                    
                    with st.expander("查看詳細數據"):
                         st.dataframe(chart_df)
                else:
                    st.warning("尚無足夠數據可供繪圖。")

except Exception as e:
    st.error(f"系統發生錯誤：{e}")
