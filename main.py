from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# 정적 파일
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# 홈 (메인 페이지)
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "CodeNote"
        }
    )

# 포켓 블랙박스 상세 페이지
@app.get("/pocket-blackbox", response_class=HTMLResponse)
def pocket_blackbox(request: Request):
    return templates.TemplateResponse(
        "pocket_blackbox.html",
        {
            "request": request,
            "title": "포켓 블랙박스 | CodeNote"
        }
    )

# Google Search Console 인증 파일
@app.get("/googleb2d5fb5c086ced8d.html")
def google_verify():
    return FileResponse("googleb2d5fb5c086ced8d.html")

# 헬스체크
@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"
