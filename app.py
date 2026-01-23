import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageDraw, ImageFont
import datetime
import io
import json

# --- 設定頁面 ---
st.set_page_config(page_title="海鮮報價生成器", page_icon="🦀")

# --- 1. 連線設定 ---
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # 使用 json.loads 讀取 Secrets，解決格式問題
    creds_dict = json.loads(st.secrets["service_account_json"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- 2. 繪圖函式 ---
def create_image(data_df, date_str):
    # 設定畫布大小
    width = 1080
    
    # 預估高度：Header + (每行規格 * 高度) + (每個品項標題 * 高度) + (代工資訊 * 高度) + Footer
    # 這裡做一個動態估算
    estimated_height = 400  # Header + Footer
    
    # 依品項分組計算高度
    grouped = data_df.groupby('品項名稱', sort=False)
    for name, group in grouped:
        estimated_height += 100 # 品項大標題
        estimated_height += len(group) * 80 # 每個規格
        estimated_height += 100 # 代工資訊預留
        estimated_height += 60 # 分隔線間距

    img = Image.new("RGB", (width, estimated_height), "#FAFAFA")
    draw = ImageDraw.Draw(img)
    
    # 嘗試載入字體 (若無則使用預設)
    try:
        # 為了美觀，建議之後可以上傳字體檔到 GitHub，目前先用預設確保能跑
        font_header = ImageFont.truetype("font.ttc", 90)
        font_date = ImageFont.truetype("font.ttc", 40)
        font_title = ImageFont.truetype("font.ttc", 60)
        font_spec = ImageFont.truetype("font.ttc", 45)
        font_price = ImageFont.truetype("font.ttc", 50)
        font_note = ImageFont.truetype("font.ttc", 35)
    except:
        font_header = ImageFont.load_default()
        font_date = ImageFont.load_default()
        font_title = ImageFont.load_default()
        font_spec = ImageFont.load_default()
        font_price = ImageFont.load_default()
        font_note = ImageFont.load_default()

    # --- A. 繪製 Header (標題區) ---
    header_height = 280
    draw.rectangle([(0, 0), (width, header_height)], fill="#003366") # 深藍底色
    
    # 主標題
    title_text = "本週最新時價"
    draw.text((60, 60), title_text, fill="white", font=font_header)
    
    # 日期 (顯示在標題下方)
    draw.text((60, 180), f"📅 報價日期：{date_str}", fill="#FFD700", font=font_date) # 金黃色日期
    draw.text((550, 180), "⚠️ 價格波動，以現場為主", fill="#DDDDDD", font=font_date)

    # --- B. 繪製內容 Loop ---
    cursor_y = header_height + 50
    
    # 顏色定義
    c_title = "#003366"  # 深藍
    c_text = "#333333"   # 黑灰
    c_price = "#D32F2F"  # 紅色
    c_note = "#666666"   # 淺灰 (代工)

    for name, group in grouped:
        # 1. 畫品項大標題
        draw.text((50, cursor_y), f"● {name}", fill=c_title, font=font_title)
        cursor_y += 90
        
        # 取得該品項的代工資訊 (取第一筆即可，因為同品項代工費通常一樣)
        service_info = str(group.iloc[0]['代工資訊'])

        # 2. 畫規格與價格
        for idx, row in group.iterrows():
            spec = str(row['規格'])
            price = str(row['本週價格'])
            
            # 規格
            draw.text((80, cursor_y), spec, fill=c_text, font=font_spec)
            
            # 價格 (加上 $ 符號)
            if price.strip() and "$" not in price and "售完" not in price:
                price_display = f"${price}"
            else:
                price_display = price
                
            # 價格靠右對齊計算
            # 簡單估算字寬：每個字大概 25-30px
            # 這裡直接設定在固定位置 x=800
            draw.text((750, cursor_y), price_display, fill=c_price, font=font_price)
            
            # 畫一條淡淡的虛線引導視線
            draw.line([(80 + len(spec)*40 + 20, cursor_y + 30), (730, cursor_y + 30)], fill="#EEEEEE", width=2)
            
            cursor_y += 70

        # 3. 畫代工資訊 (顯示在該組的最下方)
        if service_info and service_info != "nan" and service_info.strip() != "":
            # 畫一個淺灰底色塊
            note_bg_h = 60
            draw.rectangle([(80, cursor_y + 10), (1000, cursor_y + 10 + note_bg_h)], fill="#F5F5F5")
            draw.text((100, cursor_y + 20), f"🛠️ {service_info}", fill=c_note, font=font_note)
            cursor_y += 90
        
        # 分隔線
        cursor_y += 20
        draw.line([(50, cursor_y), (1030, cursor_y)], fill="#DDDDDD", width=2)
        cursor_y += 60

    # 裁切圖片 (去除底部多餘空白)
    final_img = img.crop((0, 0, width, cursor_y + 50))
    return final_img

# --- 3. Streamlit 主程式 ---
st.title("🦀 海鮮報價管理後台")

try:
    # 連線 Google Sheet
    client = get_google_sheet_client()
    sheet_url = st.secrets["sheet_url"]
    sheet = client.open_by_url(sheet_url).sheet1
    
    # 讀取資料並整理 Header
    data = sheet.get_all_values()
    # 去除標題空白
    headers = [h.strip() for h in data[0]] 
    df = pd.DataFrame(data[1:], columns=headers)
    
    st.success("✅ 成功連線資料庫")
    
    # --- 新增：日期選擇器 ---
    col_date, col_info = st.columns([1, 2])
    with col_date:
        # 預設為今天
        selected_date = st.date_input("選擇報價日期", datetime.date.today())
        date_str = selected_date.strftime("%Y/%m/%d")
    
    # --- 找出「上週價格」是哪一欄 ---
    # 邏輯：排除掉固定的欄位，剩下的最後一欄就是最近一次的紀錄
    fixed_cols = ['品項名稱', '規格', '代工資訊']
    history_cols = [c for c in df.columns if c not in fixed_cols]
    
    last_week_col = history_cols[-1] if history_cols else None
    
    # --- 表單區域 ---
    with st.form("price_update_form"):
        st.subheader(f"📝 輸入價格 ({date_str})")
        
        new_prices = []
        
        # 依照品項分組顯示
        grouped = df.groupby('品項名稱', sort=False)
        
        for name, group in grouped:
            st.markdown(f"#### 🐟 {name}") # 品項標題
            
            for idx, row in group.iterrows():
                spec = row['規格']
                
                # 取得上週價格 (如果有)
                last_price_val = ""
                if last_week_col:
                    last_price_val = row[last_week_col]
                
                # 版面配置：左邊輸入，右邊顯示上週參考
                c1, c2 = st.columns([3, 2])
                
                with c1:
                    # 預設帶入上週價格，方便修改
                    val = st.text_input(
                        f"{spec}", 
                        value=last_price_val, 
                        key=f"input_{idx}",
                        placeholder="請輸入價格"
                    )
                    new_prices.append(val)
                
                with c2:
                    # 顯示上週價格參考
                    if last_price_val:
                        st.caption(f"上週: {last_price_val}")
                    else:
                        st.caption("無歷史紀錄")
            
            st.divider() # 分隔線
            
        submitted = st.form_submit_button("🚀 確認發布並產生圖片", type="primary")
        
    if submitted:
        # 1. 更新 Google Sheet
        # 找出目前有多少欄位
        current_cols = len(headers)
        
        # 在第一列 (Header) 新增日期
        sheet.update_cell(1, current_cols + 1, date_str)
        
        # 寫入價格 (批次寫入比較快，但在這裡為了穩定我們先用簡單的 loop)
        progress_bar = st.progress(0)
        total_items = len(new_prices)
        
        # 準備寫入資料
        # 注意：row index 要從 2 開始 (因為 1 是 header)
        for i, price in enumerate(new_prices):
            sheet.update_cell(i + 2, current_cols + 1, price)
            progress_bar.progress((i + 1) / total_items)
            
        st.success(f"已新增 {date_str} 的報價紀錄！")
        
        # 2. 產出圖片
        # 組合資料給繪圖函式
        plot_df = df[['品項名稱', '規格', '代工資訊']].copy()
        plot_df['本週價格'] = new_prices
        
        st.subheader("🖼️ 您的報價單")
        image = create_image(plot_df, date_str)
        
        # 顯示圖片
        st.image(image, caption="長按可下載", use_column_width=True)
        
        # 下載按鈕
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
    st.info("請確認 Google Sheet 欄位名稱是否為：[品項名稱, 規格, 代工資訊]")
