import os
import json
import time
import re
import feedparser
from google import genai
from datetime import datetime

# Setup Gemini API using the modern SDK
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Premium sources for US iGaming & Sports Betting Legislation
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=US+online+casino+sports+betting+legislation+regulation+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://www.legalsportsreport.com/feed/",
    "https://www.playusa.com/feed/",
    "https://www.cdcgamingreports.com/feed/"
]

def fetch_and_process():
    if os.path.exists('live_data.json'):
        with open('live_data.json', 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    existing_links = {item['link'] for item in data}
    new_items = []

    # Fetch the raw feeds
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        
        articles_added = 0
        for entry in feed.entries:
            if articles_added >= 3:
                break
                
            # --- STRICT LEGAL/REGULATORY FILTER ---
            text_to_check = entry.title + " " + entry.get('summary', '')
            
            # We only want news if it mentions legislative or regulatory keywords
            legal_keywords = r'\b(bill|law|legislation|regulation|regulator|senate|house|tax|legal|court|ballot|compliance)\b'
            if not re.search(legal_keywords, text_to_check, re.IGNORECASE):
                continue
            # --------------------------------------

            if entry.link not in existing_links:
                source_name = feed.feed.get('title', 'Industry Source')
                if "news.google.com" in url:
                    if hasattr(entry, 'source') and hasattr(entry.source, 'title'):
                        source_name = entry.source.title
                    elif " - " in entry.title:
                        source_name = entry.title.rsplit(" - ", 1)[-1]

                new_items.append({
                    'link': entry.link,
                    'raw_title': entry.title,
                    'raw_summary': entry.get('summary', ''),
                    'source': source_name,
                    'timestamp': datetime.utcnow().strftime('%I:%M %p UTC')
                })
                articles_added += 1

    if not new_items:
        print("No new regulatory articles found. Exiting.")
        return

    # Process new items through Gemini
    for item in new_items:
        prompt = f"""
        You are a Senior Regulatory Analyst for a premium iGaming intelligence platform. 
        Review this raw RSS feed item about US gambling, sports betting, or online casino laws:
        Title: {item['raw_title']}
        Summary: {item['raw_summary']}

        Your task is to write a comprehensive, detailed live-feed update summarizing this legal/regulatory development.
        
        Follow this strict 3-paragraph structure:
        - Paragraph 1: The core legislative update (e.g., a bill passing, a new tax rate proposed, a court ruling).
        - Paragraph 2: The specific state context, key lawmakers involved, or the specific regulatory body.
        - Paragraph 3: The potential impact on operators (like DraftKings/FanDuel), market projections, or the timeline for implementation.

        CRITICAL INSTRUCTION: You must format the output using HTML paragraph tags inside the JSON content string to create visual spacing. Example: "<p>First paragraph text.</p><p>Second paragraph text.</p>"
        
        Determine if the content is 'News' or 'Opinion'.
        
        Return ONLY a valid JSON object in exactly this format, nothing else (no markdown formatting blocks):
        {{"type": "News" or "Opinion", "headline": "A highly descriptive, professional legal headline", "content": "<p>First paragraph here.</p><p>Second paragraph here.</p><p>Third paragraph here.</p>"}}
        """
        
        try:
            print(f"Asking Gemini to analyze: {item['raw_title']}")
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            res_text = response.text.replace('```json', '').replace('```', '').strip()
            ai_data = json.loads(res_text)
            
            item['type'] = ai_data.get('type', 'News')
            item['headline'] = ai_data.get('headline', item['raw_title'])
            item['content'] = ai_data.get('content', '<p>Detailed analysis available at the source link.</p>')
            
            data.insert(0, item)
            time.sleep(30)
            
        except Exception as e:
            print(f"Error processing {item['link']} with Gemini: {e}")
            
    data = data[:30]
    
    with open('live_data.json', 'w') as f:
        json.dump(data, f, indent=2)
        print("Successfully updated live_data.json")

if __name__ == "__main__":
    fetch_and_process()
