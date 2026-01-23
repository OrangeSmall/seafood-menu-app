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

# --- 設定頁面 ---
st.set_page_config(page_title="海鮮報價生成器", page_icon="🦀")

# --- 0. 自動下載中文字體 ---
def download_font():
    # 使用 Google 的思源黑體 (Noto Sans TC)
    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Bold.otf"
    font_path = "NotoSansCJKtc-Bold.otf"
    
    if not os.path.exists(font_path):
        with st.spinner('正在下載中文字體，第一次執行會比較久，請稍等...'):
            try:
                urllib.request.urlretrieve(font_url, font_path)
                st.success("字體下載完成！")
            except:
                st.error("字體下載失敗，將使用預設字體（可能會亂碼）")
    return font_path

# --- 1. 連線設定 ---
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(st.secrets["service_account_json"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- 2. 繪圖函式 (修正符號版) ---
def create_image(data_df, date_str):
    font_path = download_font()
    
    # 版面設定
    width = 1600 
    margin = 60
    col_gap = 100 
    col_width = (width - (margin * 2) - col_gap) / 2 
    
    # 顏色定義 (維持淡茶色系)
    c_bg = "#FDFCF5"         
    c_header_bg = "#C19A6B"  
    c_header_text = "#FFFFFF"
    c_item_title = "#5C4033" 
    c_text = "#4A4A4A"       
    c_price = "#A55B5B"      
    c_line = "#E0D6CC"       
    c_note_bg = "#F2EBE5"    
    c_note_text = "#8E7878"  

    # 載入字體
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
    
    # 計算高度邏輯
    grouped = list(data_df.groupby('品項名稱', sort=False))
    y_col1 = 350 
    y_col2 = 350 
    
    for i, (name, group) in enumerate(grouped):
        item_h = 80 
        item_h += len(group) * 60 
        item_h += 80 
        item_h += 60 
        
        if y_col1 <= y_col2:
            y_col1 += item_h
        else:
            y_col2 += item_h

    total_height = max(y_col1, y_col2) + 100 

    # --- 開始繪圖 ---
    img = Image.new("RGB", (width, int(total_height)), c_bg)
    draw = ImageDraw.Draw(img)

    # A. Header
    header_h = 280
    draw.rectangle([(0, 0), (width, header_h)], fill=c_header_bg)
    draw.text((margin, 50), "本週活體海鮮價格", fill=c_header_text, font=font_header)
    
    # [修正 1] 去除亂碼方框，改用純文字或簡單符號
    # 📅 -> 移除，直接顯示文字
    draw.text((margin, 170), f"報價日期：{date_str}", fill="#FFF8DC", font=font_date) 
    # ⚠️ -> 改成 ※ (標準符號)
    draw.text((width - margin - 500, 180), "※ 價格若有特殊情況請詢問現場主管", fill="#F0E68C", font=font_date)

    # B. 雙欄迴圈繪製
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
        
        # 品項標題 (● 圓點通常支援良好，保留)
        draw.text((current_x, current_y), f"● {name}", fill=c_item_title, font=font_title)
        current_y += 80
        
        # 規格與價格
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

        # [修正 2] 代工資訊的亂碼
        service_val = group.iloc[0]['代工資訊']
        service_info = str(service_val) if pd.notna(service_val) else ""
        
        if service_info and service_info.strip() != "":
            box_h = 50
            draw.rectangle([(current_x, current_y + 5), (current_x + col_width, current_y + 5 + box_h)], fill=c_note_bg)
            
            # 🛠️ -> 改成 ▶ (標準播放鍵符號，通常支援) 或是改用純文字 "代工："
            draw.text((current_x + 20, current_y + 10), f"▶ {service_info}", fill=c_note_text, font=font_note)
            current_y += 80
        
        current_y += 50
        
        if is_left:
            cursor_l = current_y
        else:
            cursor_r = current_y

    # Footer
    footer_y = max(cursor_l, cursor_r) + 20
    draw.line([(margin, footer_y), (width - margin, footer_y)], fill=c_line, width=2)
    
    # [修正 3] 更新浮水印文字
    draw.text((margin, footer_y + 30), "Generated by SmallOrange seafood bot v3.1", fill="#CCCCCC", font=font_footer)

    return img

# --- 3. Streamlit 主程式 ---
st.title("🦀 海鮮報價管理後台")

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
    
    st.success("✅ 成功連線資料庫")
    
    col_date, col_info = st.columns([1, 2])
    with col_date:
        selected_date = st.date_input("選擇報價日期", datetime.date.today())
        date_str = selected_date.strftime("%Y/%m/%d")
    
    fixed_cols = ['品項名稱', '規格', '代工資訊']
    history_cols = [c for c in df.columns if c not in fixed_cols and "Unnamed" not in c and c != ""]
    last_week_col = history_cols[-1] if history_cols else None
    
    with st.form("price_update_form"):
        st.subheader(f"📝 輸入價格 ({date_str})")
        new_prices = []
        grouped = df.groupby('品項名稱', sort=False)
        
        for name, group in grouped:
            st.markdown(f"#### 🐟 {name}")
            
            for idx, row in group.iterrows():
                spec = row['規格']
                last_price_val = ""
                if last_week_col:
                    val = row[last_week_col]
                    if isinstance(val, pd.Series):
                        val = val.iloc[0]
                    last_price_val = str(val) if pd.notna(val) else ""
                
                c1, c2 = st.columns([3, 2])
                with c1:
                    val = st.text_input(f"{spec}", value=last_price_val, key=f"input_{idx}")
                    new_prices.append(val)
                with c2:
                    if last_price_val:
                        st.caption(f"上週: {last_price_val}")
                    else:
                        st.caption("無紀錄")
            st.divider()
            
        submitted = st.form_submit_button("🚀 確認發布並產生圖片", type="primary")
        
    if submitted:
        current_cols = len(data[0])
        sheet.update_cell(1, current_cols + 1, date_str)
        
        progress_bar = st.progress(0)
        total_items = len(new_prices)
        for i, price in enumerate(new_prices):
            sheet.update_cell(i + 2, current_cols + 1, price)
            progress_bar.progress((i + 1) / total_items)
            
        st.success(f"已新增 {date_str} 的報價紀錄！")
        
        plot_df = df[['品項名稱', '規格', '代工資訊']].copy()
        plot_df['本週價格'] = new_prices
        
        st.subheader("🖼️ 您的報價單")
        image = create_image(plot_df, date_str)
        st.image(image, caption="長按可下載", use_column_width=True)
        
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        byte_im = buf.getvalue()
        st.download_button(
            label="📥 下載圖片",
            data=byte_im,
            file_name=f"menu_{date_str.replace('/','')}.png",
            mime="image/png"
        )

except Exception as e:
    st.error(f"系統發生錯誤：{e}")
