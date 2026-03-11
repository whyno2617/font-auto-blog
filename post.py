import os
import json
import base64
import glob
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── 설정 ──────────────────────────────────────────
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
BLOG_ID        = os.environ['BLOG_ID']
TOKEN_JSON     = os.environ['TOKEN_JSON']
GH_PAT         = os.environ['GH_PAT']
GH_REPO        = os.environ['GH_REPO']

CDN_BASE = "https://cdn.jsdelivr.net/gh/whyno2617/whyno_freefont@main"

WEIGHT_MAP = {
    "Black": 900, "Bold": 700, "SemiBold": 600,
    "Medium": 500, "Regular": 400, "Light": 300,
    "ExtraLight": 200, "Thin": 100
}

client = genai.Client(api_key=GEMINI_API_KEY)

# ── 1. 새로 추가된 폰트 폴더 감지 ────────────────
def get_new_font_folder():
    # 디버그: git log 확인
    log = subprocess.run(
        ['git', 'log', '--oneline', '-3'],
        capture_output=True, text=True
    )
    print(f"[DEBUG] git log:\n{log.stdout}")

    # 디버그: diff 결과 확인
    result = subprocess.run(
        ['git', 'diff', '--name-only', '--diff-filter=ACMR', 'HEAD~1', 'HEAD'],
        capture_output=True, text=True
    )
    print(f"[DEBUG] git diff 결과:\n{result.stdout}")
    print(f"[DEBUG] git diff 오류:\n{result.stderr}")

    changed = result.stdout.strip().split('\n')
    folders = set()
    for f in changed:
        f = f.strip()
        if f.startswith('fonts/'):
            parts = Path(f).parts
            if len(parts) >= 3:
                folders.add(parts[1])

    print(f"[DEBUG] 감지된 폴더: {folders}")
    return list(folders)

# ── 2. woff2를 whyno_freefont에 복사 ─────────────
def copy_to_freefont(folder_name):
    src_dir  = f'fonts/{folder_name}'
    dest_dir = f'whyno_freefont/{folder_name}'
    os.makedirs(dest_dir, exist_ok=True)

    copied = []
    for woff2 in glob.glob(f'{src_dir}/*.woff2'):
        dest = os.path.join(dest_dir, os.path.basename(woff2))
        shutil.copy2(woff2, dest)
        copied.append(os.path.basename(woff2))
        print(f"📋 복사: {woff2} → {dest}")

    if not copied:
        print(f"⚠️ 복사할 woff2 파일 없음: {folder_name}")
        return False

    subprocess.run(['git', 'config', 'user.email', 'action@github.com'], cwd='whyno_freefont')
    subprocess.run(['git', 'config', 'user.name', 'GitHub Actions'], cwd='whyno_freefont')
    subprocess.run(['git', 'add', '.'], cwd='whyno_freefont')
    subprocess.run(['git', 'commit', '-m', f'Add {folder_name} font'], cwd='whyno_freefont')
    subprocess.run([
        'git', 'push',
        f'https://{GH_PAT}@github.com/{GH_REPO}.git',
        'main'
    ], cwd='whyno_freefont')

    print(f"✅ whyno_freefont 푸시 완료: {folder_name}")
    return True

# ── 3. 눈누 크롤링 ────────────────────────────────
def crawl_noonnu(font_name):
    try:
        search_url = f"https://noonnu.cc/font_page/pick?search_word={quote(font_name)}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')

        first = soup.select_one('a.font-card')
        if not first:
            print(f"⚠️ 눈누에서 '{font_name}' 검색 결과 없음")
            return None

        detail_url = 'https://noonnu.cc' + first['href']
        res2 = requests.get(detail_url, headers=headers, timeout=10)
        soup2 = BeautifulSoup(res2.text, 'html.parser')

        license_el  = soup2.select_one('.license-content')
        maker_el    = soup2.select_one('.font-maker')
        dl_el       = soup2.select_one('a.download-btn')

        license_text = license_el.get_text(strip=True) if license_el else ''
        maker        = maker_el.get_text(strip=True) if maker_el else ''
        download_url = dl_el['href'] if dl_el else detail_url

        print(f"✅ 눈누 크롤링 성공: {font_name}")
        return {
            'license': license_text,
            'maker': maker,
            'download_url': download_url
        }
    except Exception as e:
        print(f"⚠️ 눈누 크롤링 실패: {e}")
        return None

# ── 4. 굵기 목록 파싱 ────────────────────────────
def get_weights_from_folder(folder_name):
    woff2_files = sorted(glob.glob(f'fonts/{folder_name}/*.woff2'))
    weights = []
    for f in woff2_files:
        stem = Path(f).stem
        weight_name = 'Regular'
        for w in WEIGHT_MAP.keys():
            if w.lower() in stem.lower():
                weight_name = w
                break
        weights.append({'name': weight_name, 'file': stem})
    return weights

# ── 5. CDN URL 생성 ───────────────────────────────
def make_cdn_url(folder, filename, ext='woff2'):
    encoded_folder = quote(folder, safe='')
    encoded_file   = quote(filename, safe='')
    return f"{CDN_BASE}/{encoded_folder}/{encoded_file}.{ext}"

# ── 6. data-url div 블록 ─────────────────────────
def make_data_divs(folder, weights):
    divs = []
    for w in weights:
        url = make_cdn_url(folder, w['file'])
        divs.append(
            f'<div data-url="{url}" '
            f'data-family="{w["file"]}" '
            f'data-weight="{w["name"]}" '
            f'style="display:none"></div>'
        )
    return '\n'.join(divs)

# ── 7. CSS @font-face 코드 ────────────────────────
def make_css_code(folder, weights):
    lines = []
    for w in weights:
        url_woff2  = make_cdn_url(folder, w['file'], 'woff2')
        weight_num = WEIGHT_MAP.get(w['name'], 400)
        lines.append(
            f"@font-face {{\n"
            f"  font-family: '{w['file']}';\n"
            f"  src: url('{url_woff2}') format('woff2');\n"
            f"  font-weight: {weight_num};\n"
            f"  font-style: normal;\n"
            f"  font-display: swap;\n"
            f"}}"
        )
    return '\n\n'.join(lines)

# ── 8. Gemini로 섹션 생성 ─────────────────────────
def generate_sections(font_name, folder_name, font_info, weights):
    image_path = None
    for ext in ['png', 'jpg', 'jpeg']:
        matches = glob.glob(f'fonts/{folder_name}/*.{ext}')
        if matches:
            image_path = matches[0]
            break

    is_draft     = font_info is None
    license_text = font_info.get('license', '확인 필요') if font_info else '확인 필요'
    maker        = font_info.get('maker', '확인 필요') if font_info else '확인 필요'
    download_url = font_info.get('download_url', '') if font_info else ''

    prompt = f"""
당신은 NEFONT 블로그의 폰트 소개 글 전문 작성자입니다.
{"아래 폰트 이미지를 분석하여 " if image_path else ""}HTML 섹션을 작성하세요.

폰트명: {font_name}
제작사: {maker}
라이선스: {license_text}

[작성 규칙]
- 섹션 제목은 반드시 <h2 class="ff-section-title"> 사용
- HTML 코드만 출력, 설명·인사말 절대 포함 금지
- 텍스트만 작성, 불필요한 태그·라벨 나열 금지

=== 섹션1: 라이선스 ===
<div class="ff-section">
  <h2 class="ff-section-title">라이선스</h2>
  <div class="ff-license-box ff-section-body">
    {"라이선스 확인이 필요합니다. 배포처에서 직접 확인해 주세요." if is_draft else "(라이선스 원문 기반으로 핵심 허용/금지 항목 2~4문장)"}
  </div>
</div>

=== 섹션2: 제작사 ===
<div class="ff-section">
  <h2 class="ff-section-title">제작사</h2>
  <div class="ff-maker-body">
    <div class="ff-maker-name">{maker}</div>
    <div class="ff-maker-sub ff-section-body">
      (제작사 소개 1~2문장. 폰트 자체 설명 금지)
    </div>
  </div>
</div>

=== 섹션3: 특징과 추천분야 ===
{"이미지를 세밀하게 분석:" if image_path else "폰트명 기반으로 작성:"}
<div class="ff-section">
  <h2 class="ff-section-title">특징과 추천분야</h2>
  <div class="ff-feature-body ff-section-body">
    (형태적 특징 단락)<br/><br/>
    (추천 사용 분야 단락)
  </div>
</div>

[출력 형식 — 반드시 이 순서대로]
LABEL: (한글 또는 영문)
CATEGORIES: (최대 3개, 쉼표 구분)
한글: 고딕,귀여움,독특,둥근고딕,명조,바탕,붓글씨,손글씨,제목용
영문: 고딕,귀여움,독특,둥근고딕,명조,바탕,붓글씨,손글씨,제목용
SECTIONS:
(섹션1~3 HTML)
"""

    if image_path:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        ext  = Path(image_path).suffix.lstrip('.')
        mime = 'image/jpeg' if ext in ['jpg', 'jpeg'] else 'image/png'
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type=mime)
            ]
        )
    else:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )

    text = response.text.strip()

    label         = '한글'
    categories    = []
    sections_html = ''

    for line in text.split('\n'):
        if line.startswith('LABEL:'):
            label = line.replace('LABEL:', '').strip()
        elif line.startswith('CATEGORIES:'):
            cats = line.replace('CATEGORIES:', '').strip()
            categories = [c.strip() for c in cats.split(',') if c.strip()]

    if 'SECTIONS:' in text:
        sections_html = text.split('SECTIONS:', 1)[1].strip()

    return label, sections_html, categories, download_url, is_draft

# ── 9. 전체 HTML 조립 ─────────────────────────────
def build_full_html(font_name, folder_name, weights, sections_html, download_url):
    data_divs = make_data_divs(folder_name, weights)
    css_code  = make_css_code(folder_name, weights)
    family    = weights[0]['file'] if weights else font_name

    html_ex = (
        f'&lt;p style="font-family: \'{family}\', sans-serif;"&gt;'
        f'{font_name} — 이 폰트로 당신의 디자인을 완성해 보세요.'
        f'&lt;/p&gt;'
    )

    return f"""{data_divs}

<!-- 📝 폰트 미리보기 -->
<div class="detail-box">
  <div class="size-control">
    <span class="size-label">크기</span>
    <button class="size-btn" id="size-minus" type="button">−</button>
    <input class="size-slider" id="size-slider" max="120" min="12" step="4" type="range" value="32"/>
    <button class="size-btn" id="size-plus" type="button">+</button>
    <span class="size-val" id="size-val">32px</span>
  </div>
</div>

{sections_html}

<!-- 💻 웹폰트 사용 코드 -->
<div class="ff-section">
  <h2 class="ff-section-title">웹폰트 사용 코드</h2>
  <div class="ff-code-block">
    <div class="ff-code-head">
      <span class="ff-code-label">🎨 CSS @font-face</span>
      <button class="ff-copy-btn" data-target="ff-css-code">복사</button>
    </div>
    <div class="ff-code-body">
      <pre id="ff-css-code">{css_code}</pre>
    </div>
  </div>
  <div class="ff-code-block">
    <div class="ff-code-head">
      <span class="ff-code-label">💻 HTML 적용 예시</span>
      <button class="ff-copy-btn" data-target="ff-html-code">복사</button>
    </div>
    <div class="ff-code-body">
      <pre id="ff-html-code">{html_ex}</pre>
    </div>
  </div>
</div>

<!-- ⬇ 다운로드 버튼 -->
<div class="ff-dl-section">
  <a class="dl-btn" href="{download_url}" target="_blank" rel="noopener">
    ↓ 공식 사이트에서 무료 다운로드
  </a>
</div>""".strip()

# ── 10. Blogger 인증 ──────────────────────────────
def get_blogger_service():
    creds = Credentials.from_authorized_user_info(json.loads(TOKEN_JSON))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('blogger', 'v3', credentials=creds)

# ── 11. Blogger 포스팅 ────────────────────────────
def post_to_blogger(service, title, content, labels, is_draft=False):
    body = {
        'title': title,
        'content': content,
        'labels': labels
    }
    result = service.posts().insert(
        blogId=BLOG_ID, body=body, isDraft=is_draft
    ).execute()
    if is_draft:
        print(f"📝 초안 저장 완료: {title}")
    else:
        print(f"✅ 포스팅 완료: {result['url']}")

# ── 메인 ─────────────────────────────────────────
if __name__ == '__main__':
    folders = get_new_font_folder()
    if not folders:
        print("새로 추가된 폰트가 없습니다.")
        exit(0)

    service = get_blogger_service()

    for folder_name in folders:
        font_name = folder_name
        print(f"\n🔍 처리 중: {font_name}")

        copy_to_freefont(folder_name)

        font_info = crawl_noonnu(font_name)
        if not font_info:
            print(f"⚠️ {font_name} — 눈누 정보 없음. 초안으로 저장합니다.")

        weights = get_weights_from_folder(folder_name)
        if not weights:
            print(f"❌ {font_name} — woff2 파일 없음. 건너뜁니다.")
            continue

        label, sections_html, categories, download_url, is_draft = generate_sections(
            font_name, folder_name, font_info, weights
        )

        all_labels = [label] + categories
        print(f"📝 라벨: {all_labels}")

        full_html = build_full_html(
            font_name, folder_name, weights, sections_html, download_url
        )
        post_to_blogger(service, font_name, full_html, all_labels, is_draft)

    print("\n🎉 모든 처리 완료!")
