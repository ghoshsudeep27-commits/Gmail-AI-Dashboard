import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession
from collections import Counter
import pandas as pd

# --- 1. CONFIGURATION & INITIALIZATION ---
st.set_page_config(page_title="AI Gmail Summarizer", page_icon="📧", layout="centered")
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
        
        # 2. Fetch minimal metadata for each message
        for i, msg in enumerate(messages, 1):
            msg_id = msg["id"]
            # We use format=metadata here instead of minimal so we can pull the clean 'From' header for our chart
            detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=metadata&metadataHeaders=From"
            detail_resp = authed_session.get(detail_url).json()
            
            headers = detail_resp.get('payload', {}).get('headers', [])
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender")
            snippet = detail_resp.get("snippet", "")
            
            # Clean up sender string for the chart (extract name if it looks like "Name <email@com>")
            clean_sender = sender.split("<")[0].strip() if "<" in sender else sender
            senders_list.append(clean_sender)
            
            email_bundle += f"\n--- EMAIL #{i} ---\nFROM: {clean_sender}\nCONTENT SNIPPET: {snippet}\n"
            
        return email_bundle, senders_list
        
    except Exception as e:
        st.error(f"Authentication or Connection error: {e}")
        st.stop()

# --- 3. DASHBOARD LOGIC ---
if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    output_container = st.container()
    
    with st.spinner("Instant Fetching via Gmail REST..."):
        email_bundle, senders_list = fetch_unread_emails_fast()
        
        if not email_bundle:
            output_container.success("🎉 Hooray! Your inbox is clean. No unread emails found.")
        else:
            # 📊 CHART CREATION SECTION
            output_container.subheader("📈 Unread Inbox Breakdown")
            
            # Count frequencies and convert to a Pandas DataFrame for Streamlit charts
            sender_counts = Counter(senders_list)
            chart_data = pd.DataFrame({
                'Sender': list(sender_counts.keys()),
                'Count': list(sender_counts.values())
            }).set_index('Sender')
            
            # Display a clean, native horizontal bar chart
            output_container.bar_chart(chart_data, horizontal=True)
            
            output_container.write("---")
            output_container.subheader("🤖 AI Executive Summaries")
            
            with st.spinner("AI is compiling your summary..."):
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    bulk_prompt = f"""
                    You are an elite executive assistant. Read through this batch of recent email snippets and provide a clean, scannable overview. 
                    For each individual email, write a 1-sentence, bold actionable takeaway.
                    
                    Here are the emails:
                    {email_bundle}
                    """
                    
                    response = model.generate_content(bulk_prompt)
                    output_container.markdown(response.text)
                    
                except Exception as ai_err:
                    if "429" in str(ai_err):
                        output_container.warning("⚠️ **Google Free Tier Cooldown:** We hit the speed limit. Please wait 15 seconds and tap refresh again!")
                    else:
                        output_container.error(f"AI Generation Error: {ai_err}")