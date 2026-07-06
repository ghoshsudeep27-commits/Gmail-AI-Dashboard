import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession
from collections import Counter
import pandas as pd
import json
import urllib.parse
from datetime import datetime
import time

# --- 1. CONFIGURATION & INITIALIZATION ---
st.set_page_config(
    page_title="AI Gmail Summarizer", 
    page_icon="icon.png", 
    layout="centered"
)

try:
    st.image("logo.png", width=160)
except Exception:
    st.warning("⚠️ Header image not found. Ensure 'logo.png' is uploaded to your GitHub repository.")

st.title("📧 Personal AI Email Summarizer")

# Initialize local session memory so we don't waste daily tokens on page re-runs
if "cached_analysis" not in st.session_state:
    st.session_state.cached_analysis = None
if "cached_chart" not in st.session_state:
    st.session_state.cached_chart = None

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Missing GEMINI_API_KEY in Streamlit Secrets!")
    st.stop()

# --- 2. SELF-REFRESHING REST FETCH ---
def fetch_unread_emails_fast(max_emails):
    if "google_credentials" not in st.secrets:
        st.error("Missing [google_credentials] block in Streamlit Secrets!")
        st.stop()
        
    secret_data = dict(st.secrets["google_credentials"])
    
    try:
        creds = Credentials.from_authorized_user_info(secret_data, SCOPES)
        authed_session = AuthorizedSession(creds)
        
        # Dynamically limits emails to protect your token usage
        list_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults={max_emails}"
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
    base_url = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    query_params = {"text": title, "details": details}
    if date_str and len(date_str) >= 8:
        query_params["dates"] = f"{date_str}/{date_str}"
    return f"{base_url}&{urllib.parse.urlencode(query_params)}"

# --- 3. CONTROL PANEL ---
st.sidebar.header("⚙️ Token Management")
# Let's you fetch fewer emails to respect free-tier token payloads
email_limit = st.sidebar.slider("Number of emails to fetch", min_value=1, max_value=5, value=3)

if st.button("🔄 Fetch & Analyze Unread Emails", type="primary"):
    with st.spinner("Instant Fetching via Gmail REST..."):
        result = fetch_unread_emails_fast(email_limit)
        
        if not result:
            st.success("🎉 Hooray! Your inbox is clean. No unread emails found.")
            st.session_state.cached_analysis = None
            st.session_state.cached_chart = None
        else:
            email_bundle, senders_list = result
            
            # Save breakdown charts
            sender_counts = Counter(senders_list)
            st.session_state.cached_chart = pd.DataFrame({
                'Sender': list(sender_counts.keys()),
                'Count': list(sender_counts.values())
            }).set_index('Sender')
            
            # --- AI FETCH WITH SMART RETRY ---
            max_retries = 3
            backoff_delay = 5
            response_text = None
            
            for attempt in range(max_retries):
                try:
                    with st.spinner("AI drafting replies..." if attempt == 0 else f"⏳ Free Quota cooldown... Waiting {backoff_delay}s..."):
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        bulk_prompt = f"""
                        You are an elite executive assistant. Read this batch of email snippets and output an analysis block.
                        You MUST respond strictly with a valid JSON array of objects. Do not include markdown formatting or wrappers outside the raw JSON code block.
                        Each object must have these exact keys: "sender", "summary", "has_event", "event_title", "event_date", "reply_positive", "reply_negative", "reply_info".
                        Assume current year is 2026.
                        
                        CRITICAL REQUIREMENT: Draft comprehensive formal replies (3-5 sentences) with headers and custom greetings.
                        
                        Here are the emails to analyze:
                        {email_bundle}
                        """
                        response = model.generate_content(bulk_prompt)
                        response_text = response.text
                        break
                except Exception as ai_err:
                    if "429" in str(ai_err):
                        if attempt < max_retries - 1:
                            time.sleep(backoff_delay)
                            backoff_delay *= 2
                        else:
                            st.error("❌ Google Daily Limit Hit (20/20 requests). Switch your Google AI Studio key to Pay-As-You-Go to run un-limited requests!")
                            st.stop()
                    else:
                        st.error(f"Error communicating with Gemini: {ai_err}")
                        st.stop()
            
            if response_text:
                try:
                    raw_text = response_text.strip().lstrip("```json").rstrip("```").strip()
                    st.session_state.cached_analysis = json.loads(raw_text)
                except Exception as parse_err:
                    st.error(f"Failed to parse AI structure: {parse_err}")

# --- 4. RENDER DASHBOARD FROM MEMORY CACHE ---
if st.session_state.cached_chart is not None:
    st.subheader("📈 Unread Inbox Breakdown")
    st.bar_chart(st.session_state.cached_chart, horizontal=True)
    st.write("---")

if st.session_state.cached_analysis is not None:
    st.subheader("🤖 AI Executive Summaries & Actions")
    for idx, item in enumerate(st.session_state.session_state.cached_analysis, 1):
        with st.expander(f"✉️ Email #{idx} from {item['sender']}", expanded=True):
            st.markdown(f"**Takeaway:** {item['summary']}")
            
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
            
            tab1, tab2, tab3 = st.tabs(["👍 Detailed Accept/Yes", "👎 Detailed Decline/No", "🤔 Detailed Ask for Info"])
            with tab1:
                st.text_area("Copy detailed reply:", value=item['reply_positive'], key=f"pos_{idx}", height=140)
            with tab2:
                st.text_area("Copy detailed reply:", value=item['reply_negative'], key=f"neg_{idx}", height=140)
            with tab3:
                st.text_area("Copy detailed reply:", value=item['reply_info'], key=f"info_{idx}", height=140)