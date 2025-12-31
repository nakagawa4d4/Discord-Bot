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

# --- 1. データ取得関数 ---
def get_market_data():
    # 日経平均とドル円を取得
    tickers = {"^N225": "日経平均", "JPY=X": "USD/JPY"}
    data_text = "【本日の数値データ】\n"
    
    for ticker, name in tickers.items():
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            close_price = hist["Close"].iloc[-1]
            data_text += f"{name}: {close_price:.2f}\n"
    
    # ニュースのヘッドラインを取得（例: Yahoo News Business RSSなど）
    # ※ここでは例としてReutersのRSSを使用（URLは適宜変更可能）
    rss_url = "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1133989/business-finance.xml" # 仮のURL、実際は有効なニュースRSSを指定
    # 安定稼働のため、今回は数値データのみでAIに語らせる構成にします（RSSは不安定な場合があるため）
    # 必要であれば feedparser.parse(rss_url) を追加してください。
    
    return data_text

# --- 2. AI要約関数 ---
def generate_summary(market_data):
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
    あなたはプロの金融アナリストです。以下の市場データを基に、今日の日本市場の動向を簡潔にまとめてください。
    
    {market_data}
    
    要件:
    - 300文字程度
    - ビジネスマン向けに簡潔に
    - トーンは「です・ます」調
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini", # コストパフォーマンスの良いモデル
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- 3. Notion投稿関数 ---
def create_notion_page(summary_text):
    notion = Client(auth=NOTION_TOKEN)
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    notion.pages.create(
        parent={"page_id": NOTION_PAGE_ID},
        properties={
            "title": {
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

# --- メイン処理 ---
if __name__ == "__main__":
    try:
        print("データ取得中...")
        data = get_market_data()
        
        print("AI要約生成中...")
        summary = generate_summary(data)
        
        print("Notion投稿中...")
        create_notion_page(summary)
        
        print("完了しました。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        exit(1)
