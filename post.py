name: Auto Font Post
on:
  workflow_dispatch:
    inputs:
      font_name:
        description: '폰트명 (예: 나눔고딕)'
        required: true
      folder:
        description: '깃허브 폴더명 (예: NanumGothic)'
        required: true
      weights:
        description: '굵기 목록 (예: Bold=NanumGothicBold, Regular=NanumGothic)'
        required: true
      has_woff:
        description: 'woff 파일도 있으면 true'
        required: false
        default: 'false'
      license:
        description: '라이선스 (눈누에서 확인한 내용 붙여넣기)'
        required: true
      maker:
        description: '제작사명 (예: 네이버)'
        required: true
      download_url:
        description: '다운로드 URL'
        required: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install google-generativeai google-api-python-client google-auth-oauthlib google-auth
      - name: Run Script
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          BLOG_ID: ${{ secrets.BLOG_ID }}
          TOKEN_JSON: ${{ secrets.TOKEN_JSON }}
          FONT_NAME: ${{ inputs.font_name }}
          FOLDER: ${{ inputs.folder }}
          WEIGHTS: ${{ inputs.weights }}
          HAS_WOFF: ${{ inputs.has_woff }}
          LICENSE: ${{ inputs.license }}
          MAKER: ${{ inputs.maker }}
          DOWNLOAD_URL: ${{ inputs.download_url }}
        run: python post.py
