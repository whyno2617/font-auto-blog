import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# 1. 시크릿 설정 가져오기
client_config = json.loads(os.environ['CLIENT_SECRETS_JSON'])

# 2. 블로그 글쓰기 권한 요청
scopes = ['https://www.googleapis.com/auth/blogger']

# 3. 인증 흐름 시작
flow = InstalledAppFlow.from_client_config(client_config, scopes)
# 로컬에서 실행하는 것이 아니므로 링크를 출력하도록 설정
auth_url, _ = flow.authorization_url(prompt='consent')

print(f"\n--- 아래 링크를 클릭해서 구글 로그인을 완료하세요! ---\n")
print(auth_url)
print(f"\n--- 로그인을 마치면 주소창의 'code=' 뒤에 있는 내용을 알려주세요 ---\n")
