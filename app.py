import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession
from collections import Counter
import pandas as pd
import json
import urllib.parse
from datetime import datetime

# --- 1. CONFIGURATION & INITIALIZATION ---
# Fixed to point to your icon.png file
st.set_page_config(
    page_title="AI Gmail Summarizer", 
    page_icon="icon.png", 
    layout="centered"
)

# Fixed to point to your logo.png file
try:
    st.image("logo.png", width=160)
except Exception:
    st.warning("⚠️ Header image not found. Ensure 'logo.png' is uploaded to your GitHub repository.")

st.title("📧 Personal AI Email Summarizer")

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Missing GEMINI_API_KEY in Streamlit Secrets!")
    st.stop()

# --- 2. SELF-REFRESHING REST FETCH ---
def fetch_unread_emails_fast():
    """Hits Gmail REST API endpoints using an AuthorizedSession."""
    if "google_credentials" not in st.secrets:
        st.error("Missing [google_credentials] block in Streamlit Secrets!")
        st.stop()
        
    secret_data = dict(st.secrets["google_credentials"])
    
    try:
        creds = Credentials.from_authorized_user_info(secret_data, SCOPES)
        authed_session = AuthorizedSession(creds)
        
        list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults=5"
        list_resp = authed_session.get(list_url).json()
        
        if "error" in list_resp:
            st.error(f"Gmail API Error: {list_resp['error'].get('message')}")
            st.stop()
            
        messages = list_resp.get("messages", [])
        
        if not messages:
            return None, None

        email_bundle = ""
        senders_list = []
        
        for i, msg in enumerate(messages, 1):
            msg_id = msg["id"]
            detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=metadata&metadataHeaders=From"
            detail_resp = authed_session.get(detail_url).json()
            
            headers = detail_resp.get('payload', {}).get('headers', [])
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender")
            snippet = detail_resp.get("snippet", "")
            
            clean_sender = sender.split("<")[0].strip() if "<" in sender else sender
            senders_list.append(clean_sender)
            
            email_bundle += f"\n--- EMAIL #{i} ---\nFROM: {clean_sender}\nCONTENT SNIPPET: {snippet}\n"
            
        return email_bundle, senders_list
        
    except Exception as e:
        st.error(f"Authentication or Connection error: {e}")
        st.stop()

def generate_google_calendar_url(title, date_str, details=""):
    """Creates a raw template link to generate calendar items on click."""
    base_url = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    
    query_params = {
        "text": title,
        "details": details,
    }
    
    if date_str and len(date_str) >= 8:
        query_params["dates"] = f"{date_str}/{date_str}"
        
    return f"{base_url}&{urllib.parse.urlencode(query_params)}"

# --- 3. DASHBOARD LOGIC ---
if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    output_container = st.container()
    
    with st.spinner("Instant Fetching via Gmail REST..."):
        result = fetch_unread_emails_fast()
        
        if not result:
            output_container.success("🎉 Hooray! Your inbox is clean. No unread emails found.")
        else:
            email_bundle, senders_list = result
            
            # 📊 CHART SECTION
            output_container.subheader("📈 Unread Inbox Breakdown")
            sender_counts = Counter(senders_list)
            chart_data = pd.DataFrame({
                'Sender': list(sender_counts.keys()),
                'Count': list(sender_counts.values())
            }).set_index('Sender')
            output_container.bar_chart(chart_data, horizontal=True)
            
            output_container.write("---")
            output_container.subheader("🤖 AI Executive Summaries & Actions")
            
            with st.spinner("AI is analyzing timeline events and drafting comprehensive replies..."):
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    bulk_prompt = f"""
                    You are an elite executive assistant. Read this batch of email snippets and output an analysis block.
                    You MUST respond strictly with a valid JSON array of objects. Do not include markdown formatting or wrappers outside the raw JSON code block.
                    
                    Each object must have these exact keys: "sender", "summary", "has_event", "event_title", "event_date", "reply_positive", "reply_negative", "reply_info".
                    Assume the current year is 2026.
                    
                    CRITICAL REQUIREMENT FOR REPLIES:
                    The templates "reply_positive", "reply_negative", and "reply_info" must be fully detailed, formal, multi-paragraph email drafts (approx 3-5 sentences each). 
                    They should include:
                    1. A proper professional greeting targeting the sender's name if discernable.
                    2. An explicit acknowledgment of the specific details present in their email snippet.
                    3. A clear action step, decision, or follow-up path.
                    4. A professional sign-off placeholder (e.g., "Best regards,\\n[Your Name]").

                    Here are the emails to analyze:
                    {email_bundle}
                    """
                    
                    response = model.generate_content(bulk_prompt)
                    
                    # Clean out markdown code fences if wrapped by the LLM response
                    raw_text = response.text.strip().lstrip("```json").rstrip("```").strip()
                    emails_data = json.loads(raw_text)
                    
                    # 🚀 RENDER EACH EMAIL BLOCK
                    for idx, item in enumerate(emails_data, 1):
                        with output_container.expander(f"✉️ Email #{idx} from {item['sender']}", expanded=True):
                            st.markdown(f"**Takeaway:** {item['summary']}")
                            
                            # 📅 EVENT HANDLING
                            if item.get("has_event") and item.get("event_date"):
                                try:
                                    parsed_date = datetime.strptime(item["event_date"], "%Y%m%d").strftime("%b %d, %Y")
                                    cal_url = generate_google_calendar_url(
                                        title=item.get("event_title", "Inbox Follow-Up"),
                                        date_str=item["event_date"],
                                        details=f"Generated from email via AI Dashboard. Summary: {item['summary']}"
                                    )
                                    st.info(f"📆 **Event Detected:** *{item['event_title']}* set for **{parsed_date}**")
                                    st.link_button("📅 Add to Google Calendar", cal_url)
                                except Exception:
                                    pass
                            
                            # Interactive Tab System for Detailed Draft Responses
                            tab1, tab2, tab3 = st.tabs(["👍 Detailed Accept/Yes", "👎 Detailed Decline/No", "🤔 Detailed Ask for Info"])
                            
                            with tab1:
                                st.text_area("Copy detailed reply:", value=item['reply_positive'], key=f"pos_{idx}", height=160)
                            with tab2:
                                st.text_area("Copy detailed reply:", value=item['reply_negative'], key=f"neg_{idx}", height=160)
                            with tab3:
                                st.text_area("Copy detailed reply:", value=item['reply_info'], key=f"info_{idx}", height=160)
                                
                except Exception as ai_err:
                    if "429" in str(ai_err):
                        output_container.warning("⚠️ **Google Free Tier Cooldown:** We hit the speed limit. Please wait 15 seconds and tap refresh again!")
                    else:
                        output_container.error(f"Error parsing AI responses: {ai_err}")