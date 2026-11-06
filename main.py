import os, re, socket, ipaddress, urllib.parse, urllib.robotparser
from functools import lru_cache
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title='Doc Truyen Viet 2')
UA='DocTruyenVietReader/2.0 (+personal reading; respects robots.txt)'
ALLOWED_DEFAULT='zongheng.com,qidian.com,17k.com,fanqienovel.com,shuqi.com'
ALLOWED=[x.strip().lower() for x in os.getenv('ALLOWED_DOMAINS',ALLOWED_DEFAULT).split(',') if x.strip()]
MAX_HTML=3_000_000

class URLRequest(BaseModel):
    url: str = Field(min_length=10,max_length=2000)
class TranslateRequest(BaseModel):
    text: str = Field(min_length=1,max_length=60000)
    style: str = 'cv'

def valid_url(url):
    try:
        p = urllib.parse.urlsplit(url)
        host = (p.hostname or '').lower().rstrip('.')
        port = p.port
    except ValueError:
        raise HTTPException(400, 'Địa chỉ URL không hợp lệ.')
    if (p.scheme != 'https' or not host or p.username or p.password
            or port not in (None, 443) or '\\' in url):
        raise HTTPException(400, 'Chỉ hỗ trợ URL HTTPS hợp lệ.')
    # Domains are administrator-controlled. Reject IP literals and local hostnames.
    try:
        ipaddress.ip_address(host)
        raise HTTPException(400, 'Không hỗ trợ URL dùng địa chỉ IP.')
    except ValueError:
        pass
    if host == 'localhost' or host.endswith(('.local', '.internal')):
        raise HTTPException(400, 'Không hỗ trợ địa chỉ nội bộ.')
    if not any(host == d or host.endswith('.' + d) for d in ALLOWED):
        raise HTTPException(400, 'Website chưa nằm trong ALLOWED_DOMAINS.')
    # DNS resolution is delegated to the HTTPS transport. Explicit getaddrinfo()
    # may fail on serverless hosts that use managed outbound proxies.
    return host


def fetch(url):
    session = requests.Session()  # Respect managed HTTPS proxy settings on Vercel.
    for _ in range(4):
        host = valid_url(url)
        try:
            rr = session.get('https://' + host + '/robots.txt',
                             headers={'User-Agent': UA}, timeout=10,
                             allow_redirects=False)
        except requests.RequestException:
            raise HTTPException(502, 'Không kết nối được robots.txt. Không thể xác nhận quyền thu thập tự động của website.')
        if rr.status_code == 200:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(rr.text.splitlines())
            if not rp.can_fetch(UA, url):
                raise HTTPException(403, 'robots.txt không cho phép tự động lấy chương này.')
        elif rr.status_code in (401, 403, 429) or rr.status_code >= 500:
            raise HTTPException(403, 'Website không cho phép hoặc chưa thể xác nhận quyền lấy nội dung qua robots.txt.')
        elif rr.status_code in (301, 302, 303, 307, 308):
            raise HTTPException(502, 'robots.txt chuyển hướng; chưa thể xác nhận quyền truy cập.')
        elif rr.status_code not in (404, 410):
            raise HTTPException(502, 'Không xác nhận được quy tắc robots.txt (HTTP %s).' % rr.status_code)
        try:
            with session.get(url, headers={'User-Agent': UA, 'Accept': 'text/html'},
                             timeout=20, allow_redirects=False, stream=True) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    location = r.headers.get('Location')
                    if not location:
                        raise HTTPException(502, 'Website chuyển hướng nhưng không có địa chỉ mới.')
                    url = urllib.parse.urljoin(url, location)
                    valid_url(url)
                    continue
                if r.status_code in (401, 403, 429):
                    raise HTTPException(403, 'Website từ chối truy cập tự động, yêu cầu đăng nhập hoặc giới hạn lượt truy cập.')
                r.raise_for_status()
                if 'html' not in r.headers.get('Content-Type', 'text/html').lower():
                    raise HTTPException(415, 'Đường dẫn không trả về HTML.')
                data = bytearray()
                for chunk in r.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > MAX_HTML:
                        raise HTTPException(413, 'Trang quá lớn.')
                r.encoding = 'utf-8'
                return r.url, bytes(data).decode(r.encoding, errors='replace')
        except requests.RequestException:
            raise HTTPException(502, 'Không tải được chương. Website có thể chặn truy cập tự động.')
    raise HTTPException(400, 'Trang chuyển hướng quá nhiều lần.')


def extract_page(url, html):
    soup = BeautifulSoup(html, 'html.parser')
    title_tag = soup.select_one('h1') or soup.select_one('title')
    title = title_tag.get_text(' ', strip=True) if title_tag else 'Chương truyện'
    selectors = ('#chapterContent, #chapter-content, #content, .chapter-content, '
                 '.read-content, .reading-content, .chapter-body, article, main')
    candidates = soup.select(selectors)
    if not candidates and soup.body:
        candidates = [soup.body]
    best = ''
    for node in candidates:
        # Work on a copy: removing links from a parent must not destroy other candidates.
        c = BeautifulSoup(str(node), 'html.parser')
        for tag in c.select('script,style,nav,footer,header,aside,noscript,form,a,button'):
            tag.decompose()
        text = re.sub(r'\n{3,}', '\n\n', c.get_text('\n', strip=True))
        if len(text) > len(best):
            best = text
    if len(best) < 120:
        raise HTTPException(422, 'Không tìm được nội dung chương; trang có thể dùng JavaScript hoặc hạn chế truy cập.')
    next_url = None
    for a in soup.select('a[href],link[href]'):
        label = a.get_text(' ', strip=True)
        rel = ' '.join(a.get('rel', [])).lower()
        cls = ' '.join(a.get('class', [])).lower()
        if ('next' in rel.split() or
            re.search(r'下一章|下一节|下章|下篇|next chapter|chương tiếp|chương sau', label, re.I) or
            ('next' in cls and len(label) < 45)):
            candidate = urllib.parse.urljoin(url, a.get('href', ''))
            try:
                valid_url(candidate)
            except HTTPException:
                continue
            if candidate != url:
                next_url = candidate
                break
    return {'title': title[:180], 'text': best[:60000],
            'next_url': next_url, 'url': url, 'chars': len(best)}

@app.get('/',response_class=HTMLResponse)
def home():
    return Path(__file__).with_name('index.html').read_text(encoding='utf-8')
@app.get('/health')
def health(): return {'ok':True,'gemini_configured':bool(os.getenv('GEMINI_API_KEY'))}
@app.post('/api/extract')
def extract(req:URLRequest):
    url,html=fetch(req.url)
    return extract_page(url,html)

@app.post('/api/translate')
def translate(req:TranslateRequest):
    key=os.getenv('GEMINI_API_KEY','').strip()
    if not key: raise HTTPException(503,'Chưa cấu hình GEMINI_API_KEY trong Vercel.')
    if len(req.text)>18000: raise HTTPException(413,'Chương quá dài. Hãy chia thành đoạn ngắn hơn để dịch.')
    model=os.getenv('GEMINI_MODEL','gemini-2.5-flash')
    prompt=('Dịch đoạn tiểu thuyết tiếng Trung sau sang tiếng Việt theo văn phong truyện mạng Convert (CV). '
            'Giữ nhất quán tên riêng, địa danh, xưng hô cổ trang (nương tử, tướng công, vi phu nếu phù hợp). '
            'Câu văn rõ nghĩa, tự nhiên, không tự ý thêm tình tiết. Giữ nguyên xuống dòng. '
            'Chỉ trả lại bản dịch, không giải thích.\n\n'+req.text)
    endpoint=f'https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model,safe="")}:generateContent'
    try:
        r=requests.post(endpoint,headers={'x-goog-api-key':key,'Content-Type':'application/json'},json={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'temperature':0.3}},timeout=55)
        if r.status_code==429: raise HTTPException(429,'Gemini đã hết hạn mức tạm thời. Hãy thử lại sau.')
        if r.status_code in (401,403): raise HTTPException(502,'Gemini từ chối API key hoặc dự án chưa có quyền sử dụng mô hình.')
        if r.status_code>=400: raise HTTPException(502,'Gemini không xử lý được yêu cầu. Kiểm tra mô hình và hạn mức API.')
        parts=r.json().get('candidates',[{}])[0].get('content',{}).get('parts',[])
        result=''.join(x.get('text','') for x in parts)
        if not result: raise HTTPException(502,'Gemini không trả về bản dịch.')
        return {'translation':result}
    except requests.RequestException: raise HTTPException(504,'Gemini phản hồi quá chậm hoặc lỗi kết nối.')
