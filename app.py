import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession

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
    """Hits Gmail REST API endpoints using an AuthorizedSession that auto-refreshes expired tokens."""
    if "google_credentials" not in st.secrets:
        st.error("Missing [google_credentials] block in Streamlit Secrets!")
        st.stop()
        
    secret_data = dict(st.secrets["google_credentials"])
    
    try:
        # Load credentials and bind them to an auto-refreshing HTTP session
        creds = Credentials.from_authorized_user_info(secret_data, SCOPES)
        authed_session = AuthorizedSession(creds)
        
        # 1. Fetch message list (Fast index query)
        list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults=5"
        list_resp = authed_session.get(list_url).json()
        
        # Check if Google returned an actual API error (like an invalid/expired token configuration)
        if "error" in list_resp:
            st.error(f"Gmail API Error: {list_resp['error'].get('message')}")
            st.stop()
            
        messages = list_resp.get("messages", [])
        
        if not messages:
            return None

        email_bundle = ""
        # 2. Fetch minimal metadata for each message
        for i, msg in enumerate(messages, 1):
            msg_id = msg["id"]
            detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=minimal"
            detail_resp = authed_session.get(detail_url).json()
            
            snippet = detail_resp.get("snippet", "")
            email_bundle += f"\n--- EMAIL #{i} ---\nCONTENT SNIPPET: {snippet}\n"
            
        return email_bundle
        
    except Exception as e:
        st.error(f"Authentication or Connection error: {e}")
        st.stop()

# --- 3. DASHBOARD LOGIC ---
if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    with st.spinner("Instant Fetching via Gmail REST..."):
        email_bundle = fetch_unread_emails_fast()
        
        if not email_bundle:
            st.success("🎉 Hooray! Your inbox is clean. No unread emails found.")
        else:
            st.subheader("Processing email snippets...")
            
            # 🤖 SINGLE AI CALL
            with st.spinner("AI is compiling your summary..."):
                try:
                    model = genai.GenerativeModel('gemini-flash-latest')
                    
                    bulk_prompt = f"""
                    You are an elite executive assistant. Read through this batch of recent email snippets and provide a clean, scannable overview. 
                    For each individual email, write a 1-sentence, bold actionable takeaway.
                    
                    Here are the emails:
                    {email_bundle}
                    """
                    
                    response = model.generate_content(bulk_prompt)
                    st.write("---")
                    st.markdown(response.text)
                    
                except Exception as ai_err:
                    if "429" in str(ai_err):
                        st.warning("⚠️ **Google Free Tier Cooldown:** We hit the 5 requests-per-minute limit. Please wait 15-20 seconds and tap refresh again!")
                    else:
                        st.error(f"AI Generation Error: {ai_err}")