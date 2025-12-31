import os
import datetime
import yfinance as yf
from openai import OpenAI
from notion_client import Client
import requests

# --- 設定 ---
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_PAGE_ID = os.environ.get("NOTION_PAGE_ID") # これがデータベースIDになります
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# データベースの「タイトル列」の名前（重要）
# あなたのNotionデータベースの一番左の列名が「名前」ならこのままでOK。
# もし「Name」や「タイトル」などに変えている場合は、ここを書き換えてください。
DATABASE_TITLE_COLUMN = "名前" 

# --- 1. データ取得関数 (ブロック回避対策付き) ---
def get_market_data():
    tickers = {"^N225": "日経平均", "JPY=X": "USD/JPY"}
    data_text = "【本日の数値データ】\n"

    # ブラウザのふりをするためのヘッダー
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # セッションを作成してヘッダーを適用
    session = requests.Session()
    session.headers.update(headers)

    for ticker, name in tickers.items():
        try:
            # sessionを渡してデータを取得
            stock = yf.Ticker(ticker, session=session)
            # 直近5日分取得して、最新の終値を探す（1dだと休日の場合空になるため）
            hist = stock.history(period="5d")
            
            if not hist.empty:
                close_price = hist["Close"].iloc[-1]
                data_text += f"{name}: {close_price:.2f}\n"
            else:
                data_text += f"{name}: データ取得不可（データなし）\n"
        except Exception as e:
            # エラーが出ても止まらずに記録する
            data_text += f"{name}: 取得エラー ({e})\n"
            
    return data_text

# --- 2. AI要約関数 ---
def generate_summary(market_data):
    if not OPENAI_API_KEY:
        return "エラー: OpenAI API Keyが設定されていません。"

    client = OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
    あなたはプロの金融アナリストです。以下の市場データを基に、今日の日本市場の動向を簡潔にまとめてください。
    もしデータが「取得エラー」となっている場合は、「本日はデータの取得に失敗しました」と正直に書いてください。
    
    {market_data}
    
    要件:
    - 300文字程度
    - ビジネスマン向けに簡潔に
    - トーンは「です・ます」調
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI要約生成エラー: {e}"

# --- 3. Notion投稿関数 (データベース対応版) ---
def create_notion_page(summary_text):
    if not NOTION_TOKEN or not NOTION_PAGE_ID:
        print("エラー: Notionの設定（トークンまたはID）が不足しています。")
        return

    notion = Client(auth=NOTION_TOKEN)
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    print(f"Notionデータベース(ID: {NOTION_PAGE_ID}) に投稿を試みます...")

    try:
        notion.pages.create(
            parent={"database_id": NOTION_PAGE_ID}, # データベースIDを指定
            properties={
                DATABASE_TITLE_COLUMN: { # 列名「名前」を指定
                    "title": [{"text": {"content": f"{today} 市場サマリー"}}]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "本日の概況"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": summary_text}}]
                    }
                }
            ]
        )
        print("成功: Notionへの投稿が完了しました。")
    except Exception as e:
        print(f"Notion投稿エラー: {e}")
        # エラーヒントを表示
        if "Could not find property" in str(e):
            print(f"ヒント: データベースの列名が「{DATABASE_TITLE_COLUMN}」ではない可能性があります。Notionの列名を確認して、コード内の 'DATABASE_TITLE_COLUMN' を書き換えてください。")
        elif "Could not find page" in str(e):
             print("ヒント: Notion側で「コネクト（接続）」がされていません。データベースのメニューからインテグレーションを招待してください。")
        raise e

# --- メイン処理 ---
if __name__ == "__main__":
    print("--- 処理開始 ---")
    
    # 1. データ取得
    print("データ取得中...")
    data = get_market_data()
    print(data)
    
    # 2. AI要約
    print("AI要約生成中...")
    summary = generate_summary(data)
    print("【要約結果】")
    print(summary)
    
    # 3. Notion投稿
    print("Notion投稿中...")
    create_notion_page(summary)
    
    print("--- 処理完了 ---")
