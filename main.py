from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import json
import os
import secrets
import threading
import time
import unicodedata
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import quote

app = FastAPI()

# 인재채용 공개 상태 및 관리자 인증 설정
POKET_AUTH_CHECK_URL = os.environ.get("POKET_AUTH_CHECK_URL", "https://poketserver.onrender.com/app/check")
RECRUIT_STATE_FILE = os.environ.get("RECRUIT_STATE_FILE", "recruit_state.json")
RECRUIT_ADMIN_COOKIE = "codenote_recruit_admin"
RECRUIT_ONCE_COOKIE = "codenote_recruit_once"
STAFF_SESSION_COOKIE = "codenote_staff_session"
RECRUIT_ADMIN_SESSION_SECONDS = 30 * 60
RECRUIT_ONCE_SECONDS = 10 * 60
STAFF_SESSION_SECONDS = 30 * 60

STAFF_FORM_URLS = {
    "talent": "https://naver.me/IgMaJQsX",
    "idea": "https://naver.me/5eDbUc7O",
}
STAFF_RESOURCE_FILES = {
    "company": "CodeNote 회사소개서.pdf",
    "forensics" : "디지털포렌식 영업자료.pdf",
    "attendance": "오늘의 출석 영업자료.pdf",
    "musync": "뮤싱크 영업자료.pdf",
    "studyphone": "학습용스마트폰전환앱 영업자료.pdf",
    "pocketblackbox": "포켓블랙박스 영업자료.pdf",
}
STAFF_RAW_BASE_URL = "https://raw.githubusercontent.com/coocu/CodeNote/main/download/"

_recruit_lock = threading.RLock()
_recruit_admin_sessions = {}
_recruit_once_tokens = {}
_staff_sessions = {}


def _load_site_state():
    try:
        with open(RECRUIT_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}
    return {
        "enabled": bool(data.get("enabled", False)),
        "notice_enabled": bool(data.get("notice_enabled", False)),
        "notice_content": str(data.get("notice_content", "") or ""),
    }


def _save_site_state():
    target = RECRUIT_STATE_FILE
    parent = os.path.dirname(os.path.abspath(target))
    os.makedirs(parent, exist_ok=True)
    temp = target + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump({
            "enabled": bool(_recruit_enabled),
            "notice_enabled": bool(_notice_enabled),
            "notice_content": _notice_content,
        }, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, target)


_site_state = _load_site_state()
_recruit_enabled = _site_state["enabled"]
_notice_enabled = _site_state["notice_enabled"]
_notice_content = _site_state["notice_content"]


def _cleanup_recruit_tokens():
    now = time.time()
    for store in (_recruit_admin_sessions, _recruit_once_tokens, _staff_sessions):
        expired = [token for token, expires_at in store.items() if expires_at <= now]
        for token in expired:
            store.pop(token, None)


def _issue_admin_session():
    with _recruit_lock:
        _cleanup_recruit_tokens()
        token = secrets.token_urlsafe(32)
        _recruit_admin_sessions[token] = time.time() + RECRUIT_ADMIN_SESSION_SECONDS
        return token


def _require_admin_session(request: Request):
    token = request.cookies.get(RECRUIT_ADMIN_COOKIE, "")
    with _recruit_lock:
        _cleanup_recruit_tokens()
        if not token or token not in _recruit_admin_sessions:
            raise HTTPException(status_code=401, detail="admin_auth_required")


def _issue_staff_session():
    with _recruit_lock:
        _cleanup_recruit_tokens()
        token = secrets.token_urlsafe(32)
        _staff_sessions[token] = time.time() + STAFF_SESSION_SECONDS
        return token


def _has_staff_session(request: Request):
    token = request.cookies.get(STAFF_SESSION_COOKIE, "")
    with _recruit_lock:
        _cleanup_recruit_tokens()
        return bool(token and token in _staff_sessions)


def _require_staff_session(request: Request):
    if not _has_staff_session(request):
        raise HTTPException(status_code=401, detail="staff_auth_required")


def _issue_once_token():
    with _recruit_lock:
        _cleanup_recruit_tokens()
        token = secrets.token_urlsafe(32)
        _recruit_once_tokens[token] = time.time() + RECRUIT_ONCE_SECONDS
        return token


def _consume_once_token(request: Request):
    token = request.cookies.get(RECRUIT_ONCE_COOKIE, "")
    if not token:
        return False
    with _recruit_lock:
        _cleanup_recruit_tokens()
        expires_at = _recruit_once_tokens.pop(token, None)
        return bool(expires_at and expires_at > time.time())


def _current_recruit_enabled():
    with _recruit_lock:
        return bool(_recruit_enabled)


def _set_recruit_enabled(enabled: bool):
    global _recruit_enabled
    with _recruit_lock:
        _recruit_enabled = bool(enabled)
        _save_site_state()
        return _recruit_enabled


def _current_notice():
    with _recruit_lock:
        return {"enabled": bool(_notice_enabled), "content": _notice_content}


def _set_notice(enabled: bool, content: str):
    global _notice_enabled, _notice_content
    with _recruit_lock:
        _notice_enabled = bool(enabled)
        _notice_content = str(content or "")
        _save_site_state()
        return {"enabled": _notice_enabled, "content": _notice_content}


def _check_poket_auth(code: str):
    payload = json.dumps({"code": code}).encode("utf-8")
    req = urllib_request.Request(
        POKET_AUTH_CHECK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        if body:
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                pass
        raise HTTPException(status_code=502, detail="auth_server_error") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=502, detail="auth_server_unavailable") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="invalid_auth_server_response") from exc
    return data if isinstance(data, dict) else {}


class RecruitAdminAuthRequest(BaseModel):
    code: str


class RecruitStateRequest(BaseModel):
    enabled: bool


class NoticeStateRequest(BaseModel):
    enabled: bool
    content: str = ""

# 정적 파일
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# 검색엔진 수집용 기본 URL
SITE_URL = "https://codenote-5gc4.onrender.com"

# 홈 (메인 페이지)
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "title": "코드노트 | 앱 개발 · 서버 개발 · 디지털 포렌식"
        }
    )


# 검색엔진 수집 정책
@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots_txt():
    return f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n"


# 검색엔진 사이트맵
@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml():
    public_paths = (
        "/",
        "/pocket-blackbox",
        "/appblock",
        "/recording",
        "/attendance",
        "/kiosk-system",
        "/memo-print",
        "/ble-call-system",
    )
    urls = "".join(
        f"  <url><loc>{SITE_URL}{path}</loc></url>\n"
        for path in public_paths
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}"
        '</urlset>\n'
    )
    return Response(content=xml, media_type="application/xml")


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

# 메모프린트
@app.get("/memo-print", response_class=HTMLResponse)
def memo_print(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="memo_print.html",
        context={
            "request": request,
            "title": "메모프린트 | CodeNote"
        }
    )


# BLE 송수신 대기 시스템
@app.get("/ble-call-system", response_class=HTMLResponse)
def ble_call_system(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ble_call_system.html",
        context={
            "request": request,
            "title": "BLE 송수신 대기 시스템 | CodeNote"
        }
    )


# 직원전용 인증 상태 확인
@app.get("/api/staff/status")
def staff_status(request: Request):
    return {"authenticated": _has_staff_session(request)}


# 직원전용 인증 - kyh 조건 없이 PoketServer /app/check 정상 인증키 검증
@app.post("/api/staff/auth")
def staff_auth(req: RecruitAdminAuthRequest):
    code = (req.code or "").strip()
    if not code:
        raise HTTPException(status_code=401, detail="invalid_auth_key")

    result = _check_poket_auth(code)
    if result.get("status") != "approved" or not result.get("token"):
        raise HTTPException(status_code=401, detail="invalid_auth_key")

    staff_token = _issue_staff_session()
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        STAFF_SESSION_COOKIE,
        staff_token,
        max_age=STAFF_SESSION_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


# 직원 포렌식 자료 인증 - 직원 세션 + kyh 포함 정상 인증키 검증
@app.post("/api/staff/forensics-auth")
def staff_forensics_auth(req: RecruitAdminAuthRequest, request: Request):
    if not _has_staff_session(request):
        raise HTTPException(status_code=401, detail="staff_auth_required")

    code = (req.code or "").strip()
    if not code or "kyh" not in code.lower():
        raise HTTPException(status_code=401, detail="invalid_auth_key")

    result = _check_poket_auth(code)
    if result.get("status") != "approved" or not result.get("token"):
        raise HTTPException(status_code=401, detail="invalid_auth_key")

    return {"status": "ok"}


# 직원전용 외부 폼 연결
@app.get("/staff/form/{form_key}")
def staff_form(form_key: str, request: Request):
    if not _has_staff_session(request):
        return RedirectResponse(url="/?staff=auth", status_code=303)
    target = STAFF_FORM_URLS.get(form_key)
    if not target:
        raise HTTPException(status_code=404, detail="staff_form_not_found")
    return RedirectResponse(url=target, status_code=302)


# 직원 자료실 - 인증된 직원에게만 GitHub Raw PDF를 다운로드로 전달
@app.get("/staff/download/{resource_key}")
def staff_download(resource_key: str, request: Request):
    if not _has_staff_session(request):
        return RedirectResponse(url="/?staff=auth", status_code=303)
    filename = STAFF_RESOURCE_FILES.get(resource_key)
    if not filename:
        raise HTTPException(status_code=404, detail="staff_resource_not_found")

    # GitHub에는 macOS 업로드 특성상 한글 파일명이 NFD(조합형)로 저장되어 있음
    github_filename = unicodedata.normalize("NFD", filename)
    raw_url = STAFF_RAW_BASE_URL + quote(github_filename, safe="")
    req = urllib_request.Request(raw_url, headers={"User-Agent": "CodeNote-Staff-Download/1.0"})
    try:
        with urllib_request.urlopen(req, timeout=20) as upstream:
            content = upstream.read()
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail="resource_download_failed") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=502, detail="resource_server_unavailable") from exc

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "Cache-Control": "private, no-store",
        },
    )


# 인재채용 상태 확인
@app.get("/api/recruit/status")
def recruit_status():
    return {"enabled": _current_recruit_enabled()}


# CONTACT 관리자 인증 - kyh 포함 여부 확인 후 PoketServer /app/check 실제 검증
@app.post("/api/recruit/admin-auth")
def recruit_admin_auth(req: RecruitAdminAuthRequest):
    code = (req.code or "").strip()
    if not code or "kyh" not in code.lower():
        raise HTTPException(status_code=401, detail="invalid_auth_key")

    result = _check_poket_auth(code)
    if result.get("status") != "approved" or not result.get("token"):
        raise HTTPException(status_code=401, detail="invalid_auth_key")

    admin_token = _issue_admin_session()
    notice = _current_notice()
    response = JSONResponse({
        "status": "ok",
        "recruitEnabled": _current_recruit_enabled(),
        "noticeEnabled": notice["enabled"],
        "noticeContent": notice["content"],
    })
    response.set_cookie(
        RECRUIT_ADMIN_COOKIE,
        admin_token,
        max_age=RECRUIT_ADMIN_SESSION_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


# 메인 공지 공개 상태/내용 확인
@app.get("/api/notice/status")
def notice_status():
    notice = _current_notice()
    return {"enabled": notice["enabled"], "content": notice["content"]}


# 관리자 공지 ON/OFF 및 내용 저장
@app.post("/api/notice/state")
def notice_state_update(req: NoticeStateRequest, request: Request):
    _require_admin_session(request)
    notice = _set_notice(req.enabled, req.content)
    return {"status": "ok", **notice}


# 관리자 채용 ON/OFF 변경
@app.post("/api/recruit/state")
def recruit_state_update(req: RecruitStateRequest, request: Request):
    _require_admin_session(request)
    enabled = _set_recruit_enabled(req.enabled)
    return {"status": "ok", "enabled": enabled}


# 채용 OFF 상태에서 이 브라우저에만 1회 /recruit 진입권한 발급
@app.post("/api/recruit/one-time-access")
def recruit_one_time_access(request: Request):
    _require_admin_session(request)
    if _current_recruit_enabled():
        raise HTTPException(status_code=409, detail="recruit_is_open")

    once_token = _issue_once_token()
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        RECRUIT_ONCE_COOKIE,
        once_token,
        max_age=RECRUIT_ONCE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


# 인재채용 - OFF이면 직접 주소 입력도 차단, 1회 권한은 실제 진입 순간 소모
@app.get("/recruit", response_class=HTMLResponse)
def recruit(request: Request):
    allowed_once = False
    if not _current_recruit_enabled():
        allowed_once = _consume_once_token(request)
        if not allowed_once:
            response = RedirectResponse(url="/?recruit=closed", status_code=303)
            response.delete_cookie(RECRUIT_ONCE_COOKIE, path="/")
            return response

    response = templates.TemplateResponse(
        request=request,
        name="recruit.html",
        context={
            "request": request,
            "title": "인재채용 | CodeNote"
        }
    )
    if allowed_once:
        response.delete_cookie(RECRUIT_ONCE_COOKIE, path="/")
    return response


# Google Search Console 인증 파일
@app.get("/googleb2d5fb5c086ced8d.html")
def google_verify():
    return FileResponse("googleb2d5fb5c086ced8d.html")

# 헬스체크
@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"
