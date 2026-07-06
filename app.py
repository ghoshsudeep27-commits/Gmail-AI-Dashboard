import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- 1. CONFIGURATION & INITIALIZATION ---
st.set_page_config(page_title="AI Gmail Summarizer", page_icon="📧", layout="centered")
st.title("📧 Personal AI Email Summarizer")

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Initialize Gemini
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

# --- 3. HIGH-SPEED BULK APP LOGIC ---
if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    with st.spinner("Connecting to Gmail..."):
        try:
            service = get_gmail_service()
            # Fetch up to 5 unread messages
            results = service.users().messages().list(userId='me', q='is:unread', maxResults=5).execute()
            messages = results.get('messages', [])
            
            if not messages:
                st.success("🎉 Hooray! Your inbox is clean. No unread emails found.")
            else:
                st.subheader(f"Fetched {len(messages)} unread messages. Analyzing in bulk...")
                
                # 📦 BUNDLE STEP: Gather all snippets locally first (Fast)
                email_bundle = ""
                for index, msg in enumerate(messages, 1):
                    message = service.users().messages().get(userId='me', id=msg['id']).execute()
                    payload = message.get('payload', {})
                    headers = payload.get('headers', [])
                    
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender")
                    snippet = message.get('snippet', '')
                    
                    # Construct a clear payload block for Gemini
                    email_bundle += f"\n--- EMAIL #{index} ---\nFROM: {sender}\nSUBJECT: {subject}\nCONTENT SNIPPET: {snippet}\n"

                # ⚡ SINGLE AI CALL: Send everything to Gemini at once
                with st.spinner("AI is analyzing your entire inbox overview..."):
                    model = genai.GenerativeModel('gemini-flash-latest')
                    
                    bulk_prompt = f"""
                    You are an elite executive assistant. Read through this batch of recent email snippets and provide a clean, scannable overview. 
                    For each individual email, write a 1-sentence, bold actionable takeaway.
                    
                    Here are the emails:
                    {email_bundle}
                    """
                    
                    response = model.generate_content(bulk_prompt)
                    
                    # Display the final beautiful compilation instantly
                    st.write("---")
                    st.markdown(response.text)
                        
        except Exception as e:
            st.error(f"An unexpected connection error occurred: {e}")