DOM Router Python Review Receiver 1.0.0
공개 예제·합성 데이터용 로컬 수신 프로그램

1. 실행
Python 3.10 이상을 설치한 뒤 ZIP을 일반 폴더에 풀고 start.cmd를 실행합니다.
Windows: start.cmd
macOS/Linux: sh start.sh
최초 실행 시 가상환경을 만들고 PyPI에서 aiohttp와 의존성을 설치하므로 인터넷이 필요합니다.
다음부터는 설치된 가상환경을 재사용합니다. 관리자 권한은 필요하지 않습니다.
브라우저에서 http://127.0.0.1:19494/ 를 여세요.
서버는 127.0.0.1에만 연결되며, 다른 PC에서 접근하는 서비스가 아닙니다.
기존 19484 포트의 observer DLL은 건드리지 않습니다.

수동 실행:
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python receiver.py
macOS/Linux는 .venv/bin/python을 사용합니다.

2. GenQRCode 실제 사이트 검증
DOM Router를 설치/활성화하고 별도 창에서 위 로컬 수신부를 실행합니다.
확장 → 연결 → 빠른 연결:
ws://127.0.0.1:19494/v1/demo/events
연결을 누르고, 로컬 주소 권한을 허용하세요. 인증키와 확장 ID 등록은 필요 없습니다.
수신부 화면의 GenQRCode → WS JSON을 저장합니다.
확장 → 프로필 불러오기 → genqrcode-ws.profile.json 선택.
연결 local-ws-demo를 선택하고 저장 → 적용 / reload를 누릅니다.
genqrcode.com 접근 권한을 허용하세요.
https://genqrcode.com/ko 에서 https://example.com/dom-router-review 를 입력하고 QR 생성.
수신부의 저장 기록에 diagnostic.observed, 같은 URL, generated:true, imageFormat:svg가 나타나는지 확인하세요.
이미 같은 사이트의 GenQRCode 프로필을 적용했다면 기존 프로필을 먼저 중지하거나 그 프로필의 연결을 변경해 적용하세요.
같은 소스에 새 프로필을 중복 적용하면 SOURCE_OWNERSHIP_CONFLICT가 발생할 수 있습니다.

이 예제는 QR 이미지를 디코딩하지 않습니다.
생성 요청의 URL을 고정하고 HTTP 200과 정상 SVG 응답을 확인한 뒤 그 URL을 전송합니다.
사이트의 임시 오류나 응답 형식 변경은 확장 로그에서 확인하세요.

3. 인터넷 사이트 없이 DOM → WS/HTTP 확인
수신부 화면에서 DOM → WS JSON 또는 DOM → HTTP JSON을 내려받습니다.
WS 연결: ws://127.0.0.1:19494/v1/demo/events (local-ws-demo)
HTTP 연결: http://127.0.0.1:19494/v1/demo/events (local-http-demo)
각 연결을 먼저 확인한 뒤 해당 프로필을 불러와 저장하고 적용하세요.
수신부 페이지를 새로고침하고 해당 WS/HTTP 감지 버튼을 누릅니다.
버튼 자체는 이벤트를 서버에 보내지 않습니다. 적용된 확장이 DOM에서 합성 값을 읽고 전송합니다.
서버의 transport: ws 또는 http 기록에서 REVIEW-001 / Example recipient를 확인합니다.
HTTP에는 상시 연결이 없으므로 WS 연결 개수나 아이콘만으로 HTTP 동작을 판단하지 마세요.

4. 데이터와 삭제
서버는 diagnostic.observed + demo + GENERIC 이벤트만 허용합니다.
실제 document.registered / qr.ready / LG / SK / KT 업무 이벤트는 거절합니다.
qrUrl이 있다면 https://example.com 또는 https://example.invalid 주소만 허용합니다.
그 외 진단 문자열을 자동으로 개인정보 판별하는 프로그램은 아닙니다. 합성 값만 넣으세요.
수신 JSON은 data/events.sqlite3에 저장됩니다. 기본 최근 1,000건, 최대 24시간 유지합니다.
화면에는 최근 100건이 표시됩니다. 60초마다 또는 조회/저장 시 만료 기록을 정리합니다.
data/receiver.log와 순환 백업에는 상태·이벤트 ID·오류 코드만 기록하며 payload는 쓰지 않습니다.
이벤트 ID가 같고 내용도 같으면 중복으로 저장하지 않습니다. 내용이 다르면 EVENT_ID_CONFLICT입니다.
화면의 JSON 저장은 현재 표시된 최근 100건의 전체 이벤트를 별도 파일로 내보냅니다.
기록 삭제는 수신부 DB만 지웁니다. 확장 로그·대기열·별도로 내보낸 JSON은 남습니다.
종료는 실행 창에서 Ctrl+C. 종료 뒤 폴더를 삭제하면 이 수신부의 로컬 파일을 제거할 수 있습니다.

5. 프로토콜
POST /v1/demo/events  Content-Type: application/json  본문: 공통 이벤트 JSON 한 개.
WebSocket ws://127.0.0.1:19494/v1/demo/events  프레임: 공통 이벤트 JSON 한 개.
구독/HELLO/페어링은 필요하지 않으며 기존 json-event / authentication:none 연결을 사용합니다.
수신부는 SQLite 커밋 후 {stored:true,eventId,duplicate,sequence}를 반환합니다.
확장의 일반 WS 모드는 이 저장 응답을 기다리지 않습니다. 확장 “송신 완료”와 수신부 “저장”을 구분하세요.
이 수신부는 Origin/Host를 검사해 일반 외부 웹사이트 요청을 거절하지만 다른 로컬 앱의 신원을 보증하지는 않습니다.
프로그램은 외부 서버에 접속하거나 이벤트를 전달하지 않습니다. 최초 의존성 설치와 공개 QR 사이트 사용은 별도입니다.
평문 HTTP/WS 테스트 수신부이므로 실제 개인정보·인증정보를 처리하는 운영 수신부를 대체하지 않습니다.
이 테스트 프로그램의 존재가 확장의 보안 정책 준수나 웹스토어 통과를 보증하는 것은 아닙니다.

6. 포트 충돌 및 오류
19494 사용 중이면 기존 실행 창을 닫거나 start.cmd --port 19495 로 실행하세요.
포트를 바꾸면 연결 주소도 바꾸고 수신부 웹페이지에서 DOM 프로필을 새로 내려받아 적용하세요.
파일로 동봉한 DOM 프로필은 기본 포트 19494용입니다.
WS_CONNECTION_FAILED: 수신부 실행 여부, 127.0.0.1 주소, 포트, 다른 프로그램 충돌을 확인하세요.
PUBLIC_EXAMPLE_URL_REQUIRED: 실제 인증 링크 대신 example.com 예제 URL을 사용하세요.
REVIEW_DIAGNOSTIC_ONLY: production 업무 프로필을 이 수신부에 연결하지 마세요.
기록이 없으면 확장 적용 상태와 실행 로그를 확인하세요. 수신부 연결 성공만으로 사이트 감지가 시작되지는 않습니다.

7. 개발자 테스트
.venv\Scripts\python -m unittest discover -s tests -v
검증 절차와 실제 검증 결과는 VERIFICATION.json을 참고하세요.
ZIP에는 가상환경·개인 자격정보·실행 중인 DB/로그를 포함하지 않습니다.
