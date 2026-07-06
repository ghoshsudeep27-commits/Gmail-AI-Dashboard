import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64

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
        # Pull your credentials dictionary from secrets
        secret_data = dict(st.secrets["google_credentials"])
        try:
            # Reconstruct the authenticated credentials object directly
            creds = Credentials.from_authorized_user_info(secret_data, SCOPES)
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            st.error(f"Error parsing token credentials: {e}")
            st.stop()
    else:
        st.error("Missing [google_credentials] block in Streamlit Secrets!")
        st.stop()

# --- 3. APP LOGIC / INTERFACE ---
if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    with st.spinner("Connecting to Gmail securely..."):
        try:
            service = get_gmail_service()
            
            # Fetch unread messages
            results = service.users().messages().list(userId='me', q='is:unread', maxResults=5).execute()
            messages = results.get('messages', [])
            
            if not messages:
                st.success("🎉 Hooray! Your inbox is clean. No unread emails found.")
            else:
                st.subheader(f"Analyzing your last {len(messages)} unread messages:")
                
                for msg in messages:
                    # Fetch detailed message data
                    message = service.users().messages().get(userId='me', id=msg['id']).execute()
                    payload = message.get('payload', {})
                    headers = payload.get('headers', [])
                    
                    # Extract Sender and Subject
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender")
                    
                    # Extract Snippet / Body text
                    snippet = message.get('snippet', '')
                    
                    st.write(f"---")
                    st.markdown(f"**From:** {sender}  \n**Subject:** {subject}")
                    
                    # Send to Gemini for custom summary
                    with st.spinner("AI is reading..."):
                        model = genai.GenerativeModel('gemini-pro')
                        prompt = f"Provide a brief, 2-sentence actionable summary of this email snippet: '{snippet}'"
                        response = model.generate_content(prompt)
                        st.info(f"🤖 **AI Summary:** {response.text}")
                        
        except Exception as e:
            st.error(f"An unexpected connection error occurred: {e}")