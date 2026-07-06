import streamlit as st
import google.generativeai as genai
import requests

# --- 1. CONFIGURATION & INITIALIZATION ---
st.set_page_config(page_title="AI Gmail Summarizer", page_icon="📧", layout="centered")
st.title("📧 Personal AI Email Summarizer")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Missing GEMINI_API_KEY in Streamlit Secrets!")
    st.stop()

# --- 2. RAW HIGH-SPEED ENDPOINTS ---
def fetch_unread_emails_fast():
    """Hits Gmail REST API endpoints directly without using the heavy build() discovery client."""
    if "google_credentials" not in st.secrets:
        st.error("Missing [google_credentials] block in Streamlit Secrets!")
        st.stop()
        
    secret_data = dict(st.secrets["google_credentials"])
    access_token = secret_data.get("token")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 1. Fetch message list (Fast index query)
    list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults=5"
    list_resp = requests.get(list_url, headers=headers).json()
    messages = list_resp.get("messages", [])
    
    if not messages:
        return None

    email_bundle = ""
    # 2. Fetch minimal metadata for each message
    for i, msg in enumerate(messages, 1):
        msg_id = msg["id"]
        # format=minimal drops the huge HTML body payloads entirely, downloading only the raw snippet string
        detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=minimal"
        detail_resp = requests.get(detail_url, headers=headers).json()
        
        snippet = detail_resp.get("snippet", "")
        email_bundle += f"\n--- EMAIL #{i} ---\nCONTENT SNIPPET: {snippet}\n"
        
    return email_bundle

# --- 3. DASHBOARD LOGIC ---
if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    with st.spinner("Instant Fetching via Gmail REST..."):
        try:
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
                        
        except Exception as e:
            st.error(f"An unexpected connection error occurred: {e}")