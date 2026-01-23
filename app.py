import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageDraw, ImageFont
import datetime
import io
import json
import os
import urllib.request # 用來下載字體

# --- 設定頁面 ---
st.set_page_config(page_title="海鮮報價生成器", page_icon="🦀")

# --- 0. 自動下載中文字體 (解決亂碼核心) ---
def download_font():
    # 使用 Google 的思源黑體 (Noto Sans TC)
    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Bold.otf"
    font_path = "NotoSansCJKtc-Bold.otf"
    
    if not os.path.exists(font_path):
        with st.spinner('正在下載中文字體，第一次執行會比較久，請稍等...'):
            try:
                # 為了避免檔案過大，我們改用較輕量的字體連結，或者直接嘗試下載
                # 這裡使用一個穩定的開源字體連結
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

# --- 2. 繪圖函式 (橫向排版 V2) ---
def create_image(data_df, date_str):
    # 確保有字體
    font_path = download_font()
    
    # 版面設定：改為橫向寬版，或適合手機閱讀的雙欄位
    width = 1600 # 加寬畫布
    margin = 60
    col_gap = 100 # 兩欄中間的間距
    col_width = (width - (margin * 2) - col_gap) / 2 # 計算單欄寬度
    
    # 顏色定義 (茶色系 & 酒紅色)
    c_bg = "#FDFCF5"         # 極淡米色/茶白底 (更柔和)
    c_header_bg = "#C19A6B"  # 淡茶色/駝色 (標題底)
    c_header_text = "#FFFFFF"# 標題白字
    c_item_title = "#5C4033" # 深褐色 (品項名)
    c_text = "#4A4A4A"       # 深灰 (規格文字)
    c_price = "#A55B5B"      # 淡酒紅色 (價格)
    c_line = "#E0D6CC"       # 淺茶灰 (分隔線)
    c_note_bg = "#F2EBE5"    # 淺灰藕色 (代工底)
    c_note_text = "#8E7878"  # 灰紫色 (代工字)

    # 載入字體
    try:
        font_header = ImageFont.truetype(font_path, 80)
        font_date = ImageFont.truetype(font_path, 40)
        font_title = ImageFont.truetype(font_path, 60) # 品項加大
        font_spec = ImageFont.truetype(font_path, 40)
        font_price = ImageFont.truetype(font_path, 50)
        font_note = ImageFont.truetype(font_path, 36)
        font_footer = ImageFont.truetype(font_path, 30)
    except:
        font_header = ImageFont.load_default()
        # ... fallback 省略，因為上面有下載機制通常不會失敗
    
    # 計算高度邏輯 (雙欄位複雜計算)
    # 我們先模擬排版一次來算高度
    grouped = list(data_df.groupby('品項名稱', sort=False))
    
    # 左欄與右欄目前的 Y 座標
    y_col1 = 350 # Header 高度
    y_col2 = 350 
    
    # 為了排版整齊，我們依序放入左右欄
    for i, (name, group) in enumerate(grouped):
        # 計算這一格(品項)需要多高
        item_h = 80 # 標題
        item_h += len(group) * 60 # 規格行數
        item_h += 80 # 代工資訊
        item_h += 60 # 間距
        
        # 決定放哪一欄 (簡單邏輯：左邊短就放左邊，右邊短就放右邊，達到平衡)
        if y_col1 <= y_col2:
            y_col1 += item_h
        else:
            y_col2 += item_h

    total_height = max(y_col1, y_col2) + 100 # 取最高的 + Footer

    # --- 開始繪圖 ---
    img = Image.new("RGB", (width, int(total_height)), c_bg)
    draw = ImageDraw.Draw(img)

    # A. Header
    header_h = 280
    draw.rectangle([(0, 0), (width, header_h)], fill=c_header_bg)
    draw.text((margin, 50), "本週最新時價", fill=c_header_text, font=font_header)
    draw.text((margin, 170), f"📅 報價日期：{date_str}", fill="#FFF8DC", font=font_date) # 玉米絲色
    draw.text((width - margin - 500, 180), "⚠️ 價格波動，以現場為主", fill="#F0E68C", font=font_date)

    # B. 雙欄迴圈繪製
    cursor_l = 330
    cursor_r = 330
    
    for i, (name, group) in enumerate(grouped):
        # 決定這一組要畫在左邊還是右邊
        if cursor_l <= cursor_r:
            current_x = margin
            is_left = True
        else:
            current_x = margin + col_width + col_gap
            is_left = False
            
        current_y = cursor_l if is_left else cursor_r
        
        # 1. 品項標題
        draw.text((current_x, current_y), f"● {name}", fill=c_item_title, font=font_title)
        current_y += 80
        
        # 2. 規格與價格
        for idx, row in group.iterrows():
            spec = str(row['規格'])
            price = str(row['本週價格'])
            
            # 規格
            draw.text((current_x + 20, current_y), spec, fill=c_text, font=font_spec)
            
            # 價格處理
            if price.strip() and "$" not in price and "售完" not in price:
                price_display = f"${price}"
            else:
                price_display = price
            
            # 價格靠該欄右側
            # 計算這一欄的右邊界 X 座標
            col_right_edge = current_x + col_width
            
            # 價格寬度
            w_price = draw.textlength(price_display, font=font_price)
            draw.text((col_right_edge - w_price, current_y), price_display, fill=c_price, font=font_price)
            
            # 引導線
            w_spec = draw.textlength(spec, font=font_spec)
            line_start = current_x + 20 + w_spec + 20
            line_end = col_right_edge - w_price - 20
            
            if line_end > line_start:
                draw.line([(line_start, current_y + 25), (line_end, current_y + 25)], fill=c_line, width=1)
                
            current_y += 60

        # 3. 代工資訊
        service_val = group.iloc[0]['代工資訊']
        service_info = str(service_val) if pd.notna(service_val) else ""
        
        if service_info and service_info.strip() != "":
            # 畫色塊
            box_h = 50
            draw.rectangle([(current_x, current_y + 5), (current_x + col_width, current_y + 5 + box_h)], fill=c_note_bg)
            draw.text((current_x + 20, current_y + 10), f"🛠️ {service_info}", fill=c_note_text, font=font_note)
            current_y += 80
        
        # 該組結束，加一點留白
        current_y += 50
        
        # 更新游標
        if is_left:
            cursor_l = current_y
        else:
            cursor_r = current_y

    # Footer
    footer_y = max(cursor_l, cursor_r) + 20
    draw.line([(margin, footer_y), (width - margin, footer_y)], fill=c_line, width=2)
    draw.text((margin, footer_y + 30), "Generated by Seafood Menu Bot", fill="#CCCCCC", font=font_footer)

    return img

# --- 3. Streamlit 主程式 ---
st.title("🦀 海鮮報價管理後台")

try:
    client = get_google_sheet_client()
    sheet_url = st.secrets["sheet_url"]
    sheet = client.open_by_url(sheet_url).sheet1
    
    data = sheet.get_all_values()
    
    # 欄位防呆
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
    
    # 歷史價格欄位
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
        # 呼叫新的繪圖函式
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
    st.info("請稍候重試，或檢查網路連線。")
