import os
import requests
import feedparser
import google.generativeai as genai
from datetime import datetime

# --- 設定 ---
# RSSのURL（ScienceDirect）
RSS_URL = "https://rss.sciencedirect.com/publication/science/0304405X"
# 過去何時間以内の記事を対象にするか（定期実行の間隔に合わせる）
CHECK_HOURS = 24 

# --- APIキーの準備 ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

def summarize_with_gemini(title, abstract):
    """Geminiを使って論文を要約する"""
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash') # コスパの良いモデルを指定

    prompt = f"""
    あなたは金融データサイエンスの専門家です。
    以下の論文データを元に、Discord投稿用の日本語要約を作成してください。
    
    【入力データ】
    Title: {title}
    Abstract: {abstract}
    
    【指示】
    1. **論文名**: 「###」を使って小見出しサイズにしてください。
    2. **要約**: 引用記号（>）は使わずにプレーンテキストで3行程度で要約してください。
    3. 出力にはタイトルと要約のみを含めてください（リンクは別途付与するため不要）。
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "要約の作成に失敗しました。"

def send_discord(content):
    """Discordにメッセージを送信する"""
    if not DISCORD_WEBHOOK_URL:
        print("Discord Webhook URLが設定されていません")
        return

    data = {"content": content}
    requests.post(DISCORD_WEBHOOK_URL, json=data)

def main():
    print("RSSを取得中...")
    feed = feedparser.parse(RSS_URL)
    
    # 記事を新しい順に処理（ここでは最新3件に制限するなど調整可能）
    for entry in feed.entries[:3]:
        # 簡易的な重複防止ロジック（発行日などで判断も可能だが今回は簡易化）
        # 本来はデータベース等で「送信済みID」を管理するのがベスト
        
        title = entry.title
        link = entry.link
        abstract = getattr(entry, 'summary', 'No abstract available.')
        
        print(f"処理中: {title}")
        
        # Geminiで要約
        summary_text = summarize_with_gemini(title, abstract)
        
        # メッセージの構築
        message = f"{summary_text}\n\n**Link:** {link}"
        
        # Discordへ送信
        send_discord(message)

if __name__ == "__main__":
    main()
