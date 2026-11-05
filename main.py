import os
import socket
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

ALLOWED_DOMAINS = {
    d.strip().lower()
    for d in os.getenv("ALLOWED_DOMAINS", "zongheng.com,www.zongheng.com").split(",")
    if d.strip()
}
app = FastAPI(title="Doc Truyen Viet")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

class ExtractRequest(BaseModel):
    url: HttpUrl

def allowed_host(host):
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)

def public_host(host):
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip = info[4][0]
            if not ipaddress.ip_address(ip).is_global:
                return False
        return bool(infos)
    except Exception:
        return False

import ipaddress

def robots_allows(url):
    p = urlparse(url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        response = requests.get(robots_url, timeout=8, headers={"User-Agent": "DocTruyenViet/1.0"})
        if response.status_code >= 400:
            return True
        rp.parse(response.text.splitlines())
        return rp.can_fetch("DocTruyenViet", url)
    except requests.RequestException:
        return False

@app.get("/")
def home():
    return FileResponse("index.html")

@app.get("/health")
def health():
    return {"ok": True, "allowed_domains": sorted(ALLOWED_DOMAINS)}

@app.post("/api/extract")
def extract(body: ExtractRequest):
    url = str(body.url)
    p = urlparse(url)
    if p.scheme != "https" or not allowed_host(p.hostname):
        raise HTTPException(400, "Trang web chưa nằm trong danh sách được hỗ trợ.")
    if not public_host(p.hostname):
        raise HTTPException(400, "Tên miền không hợp lệ.")
    if not robots_allows(url):
        raise HTTPException(403, "Không thể xác nhận quyền truy cập theo robots.txt của website.")
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (compatible; DocTruyenViet/1.0)"})
        r.raise_for_status()
    except requests.RequestException:
        raise HTTPException(502, "Không tải được trang truyện.")
    if len(r.content) > 3_000_000:
        raise HTTPException(413, "Trang quá lớn.")
    soup = BeautifulSoup(r.text, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header", "form"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else "Chương truyện"
    candidates = soup.find_all(["article", "main"])
    content_node = max(candidates, key=lambda x: len(x.get_text(" ", strip=True)), default=soup.body or soup)
    content = content_node.get_text("\n", strip=True)
    if len(content) < 100:
        raise HTTPException(422, "Không tìm thấy nội dung văn bản. Website có thể cần JavaScript hoặc cách trích xuất riêng.")
    return {"title": title, "content": content[:100000], "source_url": url}
