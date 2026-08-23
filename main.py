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
        request=request,
        name="index.html",
        context={
            "request": request,
            "title": "CodeNote"
        }
    )

# 포켓 블랙박스 상세 페이지
@app.get("/pocket-blackbox", response_class=HTMLResponse)
def pocket_blackbox(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pocket_blackbox.html",
        context={
            "request": request,
            "title": "포켓 블랙박스 | CodeNote"
        }
    )

@app.get("/appblock", response_class=HTMLResponse)
def appblock(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="appblock.html",
        context={"request": request, "title": "공신폰 앱(AppBlock) | CodeNote"}
    )


# 예약 서비스 시스템 사용 안내
@app.get("/recording", response_class=HTMLResponse)
def recording(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="recording.html",
        context={
            "request": request,
            "title": "예약 서비스 시스템 | CodeNote"
        }
    )


# 학원 출석 관리 시스템
@app.get("/attendance", response_class=HTMLResponse)
def attendance(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="attendance.html",
        context={
            "request": request,
            "title": "학원 출석 관리 시스템 | CodeNote"
        }
    )


# 기업용 대기표 키오스크 시스템
@app.get("/kiosk-system", response_class=HTMLResponse)
def kiosk_system(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="kiosk_system.html",
        context={
            "request": request,
            "title": "기업용 대기표 키오스크 시스템 | CodeNote"
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
