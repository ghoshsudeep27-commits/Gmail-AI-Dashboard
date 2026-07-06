import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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
            # static_discovery=True prevents downloading heavy API descriptions on startup
            return build('gmail', 'v1', credentials=creds, static_discovery=True)
        except Exception as e:
            st.error(f"Error parsing token credentials: {e}")
            st.stop()
    else:
        st.error("Missing [google_credentials] block in Streamlit Secrets!")
        st.stop()

# --- 3. BATCH APP LOGIC ---
if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    with st.spinner("Scanning inbox..."):
        try:
            service = get_gmail_service()
            results = service.users().messages().list(userId='me', q='is:unread', maxResults=5).execute()
            messages = results.get('messages', [])
            
            if not messages:
                st.success("🎉 Hooray! Your inbox is clean. No unread emails found.")
            else:
                st.subheader(f"Processing {len(messages)} unread messages...")
                
                email_contents = []

                # Callback function to handle responses from the batch request
                def batch_callback(request_id, response, exception):
                    if exception is None:
                        headers = response.get('payload', {}).get('headers', [])
                        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
                        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender")
                        snippet = response.get('snippet', '')
                        email_contents.append(f"FROM: {sender}\nSUBJECT: {subject}\nCONTENT SNIPPET: {snippet}\n")

                # ⚡ NATIVE BATCH: Combine all HTTP requests into a single network pipeline
                batch = service.new_batch_http_request(callback=batch_callback)
                
                for msg in messages:
                    batch.add(service.users().messages().get(
                        userId='me', id=msg['id'], format='metadata', metadataHeaders=['Subject', 'From']
                    ))
                
                # Execute the entire bundle at once
                batch.execute()

                email_bundle = "\n".join([f"--- EMAIL #{i} ---\n{text}" for i, text in enumerate(email_contents, 1)])

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
                        
        except Exception as e:
            st.error(f"An unexpected connection error occurred: {e}")