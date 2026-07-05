def get_gmail_service():
    """Handles OAuth2 using cloud vault strings or local credentials files."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # ☁️ CLOUD CHECK: Explicitly construct the format Google demands
            if "google_credentials" in st.secrets:
                secret_data = st.secrets["google_credentials"]
                
                # Manually build the exact 'installed' structure to avoid parsing bugs
                cred_dict = {
                    "installed": {
                        "client_id": secret_data["client_id"],
                        "project_id": secret_data["project_id"],
                        "auth_uri": secret_data["auth_uri"],
                        "token_uri": secret_data["token_uri"],
                        "auth_provider_x509_cert_url": secret_data["auth_provider_x509_cert_url"],
                        "client_secret": secret_data["client_secret"],
                        "redirect_uris": list(secret_data["redirect_uris"])
                    }
                }
                flow = InstalledAppFlow.from_client_config(cred_dict, SCOPES)
            # 💻 LOCAL CHECK: Fallback to local file if running on your machine
            elif os.path.exists('credentials.json'):
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            else:
                st.error("Missing Google Credentials structure!")
                st.stop()
                
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            
    return build('gmail', 'v1', credentials=creds)