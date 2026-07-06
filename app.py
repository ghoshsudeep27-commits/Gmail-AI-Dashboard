import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import concurrent.futures
import time

# --- 1. CONFIGURATION & INITIALIZATION ---
st.set_page_config(page_title="AI Gmail Summarizer", page_icon="📧", layout="centered")
st.title("📧 Personal AI Email Summarizer")

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Missing GEMINI_API_KEY in Streamlit Secrets!")
    st.stop()

# --- 2. PRE-AUTHORIZED GMAIL CONNECT ---
def get_gmail_service():
    """Builds the Gmail client directly using the pre-authorized cloud token."""
    if "google_credentials" in st.secrets:
        secret_data = dict(st.secrets["google_credentials"])
        try:
            creds = Credentials.from_authorized_user_info(secret_data, SCOPES)
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            st.error(f"Error parsing token credentials: {e}")
            st.stop()
    else:
        st.error("Missing [google_credentials] block in Streamlit Secrets!")
        st.stop()

def fetch_single_email_details(msg_id, secret_data):
    """Helper function to fetch an individual email. Runs inside a background thread."""
    try:
        creds = Credentials.from_authorized_user_info(secret_data, SCOPES)
        thread_service = build('gmail', 'v1', credentials=creds)
        
        message = thread_service.users().messages().get(
            userId='me', id=msg_id, format='metadata', metadataHeaders=['Subject', 'From']
        ).execute()
        
        headers = message.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender")
        snippet = message.get('snippet', '')
        
        return f"FROM: {sender}\nSUBJECT: {subject}\nCONTENT SNIPPET: {snippet}\n"
    except Exception:
        return ""

# --- 3. HIGH-SPEED PARALLEL APP LOGIC ---
if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    with st.spinner("Scanning inbox metadata..."):
        try:
            service = get_gmail_service()
            results = service.users().messages().list(userId='me', q='is:unread', maxResults=5).execute()
            messages = results.get('messages', [])
            
            if not messages:
                st.success("🎉 Hooray! Your inbox is clean. No unread emails found.")
            else:
                st.subheader(f"Analyzing {len(messages)} unread messages simultaneously...")
                
                secret_data = dict(st.secrets["google_credentials"])
                email_contents = []
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(fetch_single_email_details, msg['id'], secret_data) for msg in messages]
                    for idx, future in enumerate(concurrent.futures.as_completed(futures), 1):
                        result_text = future.result()
                        if result_text:
                            email_contents.append(f"\n--- EMAIL #{idx} ---\n{result_text}")

                email_bundle = "".join(email_contents)

                # 🤖 SINGLE AI CALL WITH GRACEFUL LIMIT CATCHER
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
                        
        except Exception as e:
            st.error(f"An unexpected connection error occurred: {e}")