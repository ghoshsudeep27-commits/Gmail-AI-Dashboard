# --- 3. APP LOGIC / INTERFACE ---
if st.button("🔄 Refresh / Fetch Unread Emails", type="primary"):
    with st.spinner("Connecting to Gmail..."):
        try:
            service = get_gmail_service()
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
                    model = genai.GenerativeModel('gemini-3.5-flash')
                    
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