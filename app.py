import os
import pickle
import streamlit as st
import pandas as pd
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google import genai

# 🔑 Add your Gemini API Key here
GEMINI_API_KEY = "AQ.Ab8RN6I3R4E17UpDG3yqrSSgia-8i_qEkmm9Ft7PuE6gE9Nt0Q"

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """Handles OAuth2 authentication cleanly."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                st.error("Missing 'credentials.json'!")
                st.stop()
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            
    return build('gmail', 'v1', credentials=creds)

def get_email_body(service, msg_id):
    """Retrieves the plain text snippet or body of an email."""
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        return msg.get('snippet', '')
    except Exception:
        return ""

def summarize_with_gemini(text):
    """Uses Gemini to create a one-sentence summary of the email content."""
    if not text.strip() or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return "No content to summarize or API key missing."
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Summarize this email snippet concisely in one clear sentence: {text}"
        )
        return response.text
    except Exception as e:
        return f"Summary failed: {e}"

def fetch_unread_emails_with_summaries(service, max_results=20):
    """Fetches emails and generates AI summaries on the fly."""
    results = service.users().messages().list(userId='me', q='is:unread label:INBOX', maxResults=max_results).execute()
    messages = results.get('messages', [])
    
    email_data = []
    if not messages:
        return None

    for msg in messages:
        msg_detail = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
        headers = msg_detail.get('payload', {}).get('headers', [])
        
        subject, sender, date = "No Subject", "Unknown Sender", "Unknown Date"
        for header in headers:
            if header['name'] == 'Subject': subject = header['value']
            elif header['name'] == 'From': sender = header['value']
            elif header['name'] == 'Date': date = header['value']
        
        body_text = get_email_body(service, msg['id'])
        ai_summary = summarize_with_gemini(body_text)
                
        email_data.append({
            "Sender": sender,
            "Subject": subject,
            "AI Summary ✨": ai_summary,
            "Date": date
        })
        
    return pd.DataFrame(email_data)

# --- USER INTERFACE ---
st.set_page_config(page_title="AI Gmail Summarizer", layout="wide")
st.title("✉️ AI Gmail Dashboard")

if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    try:
        with st.spinner("Fetching emails and generating AI summaries..."):
            service = get_gmail_service()
            # Changed max_results to 20 for a better data sample size
            df = fetch_unread_emails_with_summaries(service, max_results=20)
            
            st.success("Successfully connected to your Gmail account!")
            
            if df is not None:
                # Layout split into two columns: Left for Data, Right for Charts
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("📥 Your Latest Unread Emails & AI Insights")
                    st.dataframe(df, use_container_width=True)
                
                with col2:
                    st.subheader("📊 Top Senders Breakdown")
                    # Count frequency of each unique sender
                    sender_counts = df["Sender"].value_counts()
                    # Generate the visual bar graph natively
                    st.bar_chart(sender_counts)
            else:
                st.info("Inbox clean! You have zero unread emails right now.")
                
    except Exception as e:
        st.error(f"Error connecting: {e}")
else:
    st.info("👋 Welcome! Click the button above to load your emails and generate AI summaries.")