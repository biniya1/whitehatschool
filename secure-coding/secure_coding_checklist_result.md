# 시큐어 코딩 체크리스트 점검 결과

`secure_coding_checklist.csv`(강사 제공)의 각 항목에 대해, 최종 구현이 이를 만족하는지
점검한 결과입니다. 각 항목은 Pass/Partial로 표시하고, 근거가 되는 구현 위치를 명시합니다.

| Section | Checklist Item | 결과 | 구현 내용 |
|---|---|---|---|
| 회원가입 및 프로필 관리 | 서버측 입력 검증 | Pass | `forms.py`의 `RegisterForm`/`ProfileForm`이 사용자명(영문/숫자/`_`, 3~20자), 비밀번호(영문+숫자 포함 8자 이상) 등을 서버측에서 검증. Jinja2 autoescape로 모든 출력이 기본 이스케이프됨 |
| | CSRF 보호 | Pass | `extensions.py`의 `CSRFProtect`를 전역 적용(`app.py`). 모든 폼은 WTForms `hidden_tag()`/수동 `csrf_token()`으로 토큰 포함. 토큰 누락/불일치 시 `CSRFError` 핸들러가 안전하게 리다이렉트 |
| | 비밀번호 보안 | Pass | `models.py User.set_password`가 Werkzeug `generate_password_hash`(솔트 포함 강력한 해시)로 저장. 평문 저장 없음 |
| | 세션 쿠키 설정 | Pass | `config.py`에서 `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE=Lax`, `SESSION_COOKIE_SECURE`는 HTTPS 환경(ngrok 등)에서 환경변수로 활성화 가능 |
| | 세션 만료 및 재인증 | Pass | `PERMANENT_SESSION_LIFETIME=30분` 설정, 로그인 시 `session.permanent=True`. 민감 작업(비밀번호 변경)은 `routes/main.py profile()`에서 현재 비밀번호 재확인을 요구 |
| | 실패 로그인 방어 | Pass | `models.py User.register_failed_login`: 5회 실패 시 15분 계정 잠금(`locked_until`). `routes/auth.py login()`에서 사용자 존재 여부와 무관하게 동일한 일반 오류 메시지 사용(계정 존재 여부 추측 방지) |
| | 오류 메시지 | Pass | `app.py`의 404/403/413/500 커스텀 핸들러가 일반 메시지만 노출, 예외는 `app.logger.exception`으로 서버 로그에만 기록. `debug=False`가 기본값 |
| 상품 등록 및 관리 | 폼 입력 검증 | Pass | `forms.py ProductForm`: 제목/설명 길이 제한, 가격은 `NumberRange(min=0, max=1_000_000_000)`으로 숫자·범위 검증 |
| | XSS 방어 | Pass | 모든 템플릿이 Jinja2 autoescape 사용(`|safe` 미사용). `tests/test_security.py::test_product_description_is_escaped_in_output`로 검증 |
| | 인증된 사용자만 등록 | Pass | `routes/products.py`의 등록/수정/삭제 라우트 모두 `@login_required` 적용 |
| | 소유자 확인 | Pass | `edit_product`/`delete_product`에서 `product.seller_id != user.id and not user.is_admin` 검사. `tests/test_security.py::test_cannot_edit_or_delete_other_users_product`로 검증(IDOR 방지) |
| | 데이터 무결성 | Pass | SQLAlchemy 컬럼 제약(`nullable=False` 등) + WTForms 검증을 통과해야 DB에 저장됨 |
| 실시간 채팅 및 메시징 | 메시지 내용 검증 | Pass | `routes/chat.py`: 메시지 길이 1~500자 서버측 검증, 빈 문자열 거부. 출력은 템플릿 autoescape로 이스케이프 |
| | 사용자 인증 | Pass | `@socketio.on('connect')`에서 세션 미인증 시 연결 자체를 거부(`return False`). 각 이벤트 핸들러에서도 재확인 |
| | 메시지 검증 | Pass | 클라이언트가 보낸 `username`은 신뢰하지 않고 서버 세션의 실제 사용자명으로 대체(스푸핑 방지) — 스타터 코드의 취약점을 수정한 부분 |
| | Rate Limiting | Pass | `security.py ChatRateLimiter`: 사용자당 10초에 5개 메시지로 제한(전역 채팅/1:1 채팅 모두 적용) |
| | 연결 암호화 | Partial | 개발 환경은 로컬 HTTP + Werkzeug 개발 서버 사용(과제 범위). `cors_allowed_origins` 기본값(동일 출처만 허용)으로 CSWSH 방지. 운영 환경에서는 WSS(TLS 종단 리버스 프록시) 필요 — REPORT.md 한계점에 기술 |
| 안전 거래 및 신고 | 폼 입력 검증 | Pass | `forms.py ReportForm`: `target_type`은 select(`product`/`user`)로 제한, `reason`은 5~500자 |
| | 인증된 사용자 접근 | Pass | `routes/reports.py report()`에 `@login_required` |
| | 데이터 무결성 및 로그 관리 | Pass | 신고 저장 시 `reporter_id`/`target_type`/`target_id`/`reason`/`created_at` 모두 기록되어 감사 로그 역할 수행 |
| | 신고 남용 방지 | Pass | `Report` 테이블에 `(reporter_id, target_type, target_id)` unique 제약으로 동일 대상 중복 신고 차단 + 사용자당 시간당 20건 신고 제한(`REPORTS_PER_HOUR_LIMIT`) |
| 전체 시스템 | ORM 및 파라미터 바인딩 | Pass | 스타터의 raw `sqlite3` 문자열 쿼리를 Flask-SQLAlchemy ORM으로 전면 교체(`models.py`, 모든 routes) |
| | 데이터베이스 권한 | Partial | SQLite 파일 기반 특성상 별도 DB 계정 권한 분리는 적용 대상이 아님. 파일은 웹 루트/정적 서빙 경로 밖에 위치, `.gitignore`로 커밋 방지 |
| | 보안 헤더 설정 | Pass | `security.py apply_security_headers`: CSP(`unsafe-inline` 없음), X-Frame-Options, X-Content-Type-Options, Referrer-Policy, (HTTPS 시) HSTS 적용 |
| | HTTPS 적용 | Partial | 로컬 개발 서버는 HTTP. ngrok로 외부 테스트 시 HTTPS 터널 제공됨. `SESSION_COOKIE_SECURE`는 환경변수로 전환 가능 |
| | 에러 및 예외 처리 | Pass | 커스텀 에러 핸들러가 내부 정보 노출 없이 일반 메시지만 반환, 예외는 서버 로그에만 기록 |
| | 라이브러리 및 의존성 관리 | Pass | `requirements.txt`/`enviroments.yaml`에 버전 범위 명시. 정기적 `pip list --outdated` 점검 권장(REPORT.md 유지보수 항목) |

## 요약

- 27개 항목 중 24개 Pass, 3개 Partial.
- Partial 항목은 모두 "로컬 개발 환경/TLS 미적용"이라는 동일한 근본 원인에서 기인하며,
  실제 배포 시 리버스 프록시(Nginx 등) + TLS 인증서 적용으로 해소 가능함을 REPORT.md에 명시.
