import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def get_credentials():
    token_data = json.loads(os.environ['TOKEN_JSON'])
    creds = Credentials.from_authorized_user_info(token_data)
    
    # 토큰 만료 시 자동 갱신
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return creds
