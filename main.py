import os
import datetime
import yfinance as yf
import feedparser
from openai import OpenAI
from notion_client import Client

# --- 設定 ---
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_PAGE_ID = os.environ.get("NOTION_PAGE_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# 【修正箇所】スクリーンショットに合わせて "Name" に設定しました
DATABASE_TITLE_COLUMN = "Name"

# --- 1. ニュースとデータの収集 ---
def get_market_info():
    info_text = ""

    # (A) 株価データの取得（取れなくても止まらないようにする）
    info_text += "【株価データ】\n"
    tickers = {"^N225": "日経平均", "JPY=X": "USD/JPY"}
    try:
        for ticker, name in tickers.items():
            stock = yf.Ticker(ticker)
            # 期間を短くしてエラー率を下げる
            hist = stock.history(period="1d")
            if not hist.empty:
                close = hist["Close"].iloc[-1]
                info_text += f"{name}: {close:.2f}\n"
            else:
                info_text += f"{name}: 取得不可\n"
    except Exception:
        info_text += "株価データの取得に失敗しました（アクセス制限など）\n"

    # (B) ニュース記事の取得（これがAIの知識源になります）
    # ロイター(日本語)のビジネスニュースRSSを使用
    rss_url = "http://feeds.reuters.com/reuters/JPBusinessNews"
    
    info_text += "\n【主要ニュース見出し】\n"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            for entry in feed.entries[:5]: # 最新5件を取得
                info_text += f"- {entry.title}\n"
        else:
            info_text += "ニュースが見つかりませんでした。\n"
    except Exception as e:
        info_text += f"ニュース取得エラー: {e}\n"
        
    return info_text

# --- 2. AIによるサマリー生成 ---
def generate_summary(input_text):
    if not OPENAI_API_KEY:
        return "エラー: OpenAI API Keyが設定されていません。"

    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # AIへの指示書
    prompt = f"""
    あなたは優秀な経済アナリストです。
    以下の「株価データ」と「ニュース見出し」を元に、今日の日本市場のサマリーを作成してください。
    
    【収集された情報】
    {input_text}
    
    【指示】
    - 株価が取得できていない場合は、ニュースの内容を中心に市場の雰囲気を伝えてください。
    - ビジネスマン向けに、300文字程度で簡潔にまとめてください。
    - 重要なニュースがあれば、その背景にも少し触れてください。
    - 文体は「です・ます」調で。
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI生成エラー: {e}"

# --- 3. Notionへの投稿 ---
def create_notion_page(summary_text):
    if not NOTION_TOKEN or not NOTION_PAGE_ID:
        print("エラー: Notion設定不足")
        return

    notion = Client(auth=NOTION_TOKEN)
    today = datetime.date.today().strftime("%Y-%m-%d")

    print(f"Notionへ投稿中... (Target Column: {DATABASE_TITLE_COLUMN})")
    
    try:
        notion.pages.create(
            parent={"database_id": NOTION_PAGE_ID},
            properties={
                DATABASE_TITLE_COLUMN: { 
                    "title": [{"text": {"content": f"{today} 市場サマリー"}}]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"text": {"content": "本日の市況概況"}}]}
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": summary_text}}]}
                }
            ]
        )
        print("投稿成功！")

    except Exception as e:
        print(f"Notion投稿エラー: {e}")
        # まだエラーが出る場合のヒント
        if "Could not find page" in str(e):
             print("ヒント: Notion側で「コネクト（接続）」がされていません。データベースのメニューからインテグレーションを招待してください。")
        raise e

# --- メイン実行 ---
if __name__ == "__main__":
    print("--- 処理開始 ---")
    
    # 情報を集める
    print("情報収集中...")
    market_info = get_market_info()
    print(market_info) # ログで確認用
    
    # AIが考える
    print("AIが執筆中...")
    summary = generate_summary(market_info)
    
    # Notionに書く
    create_notion_page(summary)
    
    print("--- 完了 ---")
