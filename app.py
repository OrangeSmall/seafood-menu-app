import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageDraw, ImageFont
import datetime
import io

# --- 設定頁面 ---
st.set_page_config(page_title="海鮮報價生成器", page_icon="🦀")

# --- 1. 連線設定 ---
# 我們從 Streamlit Secrets 讀取金鑰，而不是直接把密碼寫在程式碼裡
# 記得確認最上面這行有沒有寫，沒有的話補上去
import json 
def get_google_sheet_client():
   # [修改] 移除 try/except，直接讀取，這樣出錯時我們才能看到真正的修復提示
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # 這裡直接讀取，不設防護網
    creds_dict = json.loads(st.secrets["service_account_json"])
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- 2. 繪圖函式 (你的客製化版型) ---
def create_image(data_df, date_str):
    # 安裝字體 (雲端環境通常沒有中文字體，這裡使用預設或需額外處理)
    # 在 Streamlit Cloud 上，我們可以使用開源字體
    # 這裡為了簡化，我們先嘗試用預設，若需漂亮字體需在同目錄放 .ttc 檔
    # 為了確保能跑，這裡先用簡易字體路徑，若失敗則回退
    
    width = 1080
    # 預估高度
    estimated_height = 300 + (len(data_df) * 80) + 200
    img = Image.new("RGB", (width, estimated_height), "#FAFAFA")
    draw = ImageDraw.Draw(img)
    
    # 嘗試載入字體 (若你有上傳字體檔到 github，路徑要改)
    # 這裡用簡單的邏輯：若沒字體就用預設
    try:
        # 假設我們將字體檔放在同目錄下，命名為 font.ttc
        font_header = ImageFont.truetype("font.ttc", 80)
        font_title = ImageFont.truetype("font.ttc", 50)
        font_price = ImageFont.truetype("font.ttc", 50)
        font_note = ImageFont.truetype("font.ttc", 30)
    except:
        # 如果沒字體，用預設 (會醜一點但能跑)
        font_header = ImageFont.load_default()
        font_title = ImageFont.load_default()
        font_price = ImageFont.load_default()
        font_note = ImageFont.load_default()

    # 繪製 Header
    draw.rectangle([(0,0), (width, 250)], fill="#003366")
    draw.text((50, 80), "本週最新時價", fill="white", font=font_header)
    draw.text((50, 180), f"日期：{date_str}", fill="#DDDDDD", font=font_title)

    cursor_y = 300
    
    # 資料分組邏輯
    current_product = ""
    
    for index, row in data_df.iterrows():
        product_name = str(row['品項名稱'])
        spec = str(row['規格'])
        price = str(row['本週價格'])
        note = str(row['代工資訊'])
        
        # 如果是新品項，畫大標題
        if product_name != current_product:
            cursor_y += 40
            draw.text((50, cursor_y), f"● {product_name}", fill="#003366", font=font_title)
            current_product = product_name
            cursor_y += 80
            
        # 畫規格與價格
        draw.text((80, cursor_y), spec, fill="#333333", font=font_note)
        
        # 價格靠右 (簡單計算)
        price_text = f"${price}" if "$" not in price and price.strip() != "" else price
        draw.text((800, cursor_y), price_text, fill="#D32F2F", font=font_price)
        
        # 畫代工 (只在該品項最後一個或第一格顯示? 這裡簡化為有寫就顯示)
        if note and note != "nan" and note.strip() != "":
             cursor_y += 50
             draw.text((80, cursor_y), f"💡 {note}", fill="#888888", font=font_note)
        
        cursor_y += 70
        draw.line([(50, cursor_y), (1030, cursor_y)], fill="#EEEEEE")
        cursor_y += 30

    # 裁切圖片到實際高度
    final_img = img.crop((0, 0, width, cursor_y + 50))
    return final_img

# --- 3. Streamlit 網頁介面 ---
st.title("🦀 報價單管理後台")

# 輸入你的 Google Sheet 網址
SHEET_URL = st.secrets["sheet_url"]

try:
    client = get_google_sheet_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    
    # 讀取所有資料
    data = sheet.get_all_values()
    headers = data[0]
    df = pd.DataFrame(data[1:], columns=headers)
    
    st.success("✅ 成功連線資料庫")
    
    with st.form("price_update_form"):
        st.subheader("📝 本週價格輸入")
        
        # 動態生成輸入框
        new_prices = []
        
        # 為了介面好看，我們用分組顯示
        grouped = df.groupby('品項名稱', sort=False)
        
        for name, group in grouped:
            st.markdown(f"**{name}**")
            for idx, row in group.iterrows():
                spec = row['規格']
                # 取得最後一欄作為參考價格 (假設最後一欄是最近一次)
                last_price = row.iloc[-1] 
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.text(f"規格: {spec}")
                with col2:
                    # 這裡用 text_input 因為價格可能有文字 (e.g. 售完)
                    val = st.text_input(f"價格 ({spec})", value=last_price, key=f"input_{idx}")
                    new_prices.append(val)
            st.divider()
            
        submitted = st.form_submit_button("🚀 確認發布並產生圖片", type="primary")
        
    if submitted:
        # 1. 更新 Google Sheet
        today_str = datetime.date.today().strftime("%Y/%m/%d")
        
        # 檢查今天是否已經有欄位，如果沒有就新增，如果有就覆寫 (這裡簡化為直接新增一欄)
        # 為了安全，我們先讀取目前的欄數
        current_cols = len(headers)
        
        # 準備要寫入的一整列資料 (標題 + 價格)
        # 注意：這裡邏輯是新增一欄 (Column) 還是更新？
        # 根據你的需求是「保留歷史」，所以我們要新增一個 Column 叫「今日日期」
        
        # 但 Gspread 新增 Column 比較複雜，我們換個簡單邏輯：
        # 我們把新價格寫入 Sheet 的「最右邊」
        
        # 更新 Header
        sheet.update_cell(1, current_cols + 1, today_str)
        
        # 更新每一列的價格
        # API 限制，這裡用迴圈寫會慢，但為了簡單易懂先這樣
        progress_bar = st.progress(0)
        for i, price in enumerate(new_prices):
            # Row 是 i + 2 (因為 header 是 1, list index 從 0 開始)
            sheet.update_cell(i + 2, current_cols + 1, price)
            progress_bar.progress((i + 1) / len(new_prices))
            
        st.success(f"已新增 {today_str} 的報價紀錄！")
        
        # 2. 產出圖片
        # 重新整理資料結構給繪圖用
        plot_df = df[['品項名稱', '規格', '代工資訊']].copy()
        plot_df['本週價格'] = new_prices
        
        st.subheader("🖼️ 您的報價單")
        image = create_image(plot_df, today_str)
        
        # 顯示圖片
        st.image(image, caption="長按可下載", use_column_width=True)
        
        # 提供下載按鈕
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        byte_im = buf.getvalue()
        st.download_button(
            label="📥 下載圖片",
            data=byte_im,
            file_name=f"menu_{today_str.replace('/','')}.png",
            mime="image/png"
        )

except Exception as e:
    st.error(f"發生錯誤：{e}")
    st.info("請檢查 Secrets 設定是否正確")
