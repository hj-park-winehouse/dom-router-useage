DOM Router Python Review Receiver 1.0.0
Local receiver for public examples and synthetic data

Requirements and start
Install Python 3.10 or later. Extract this archive to a writable folder.
Windows: double-click start.cmd. macOS/Linux: run sh start.sh.
The first run creates a virtual environment and installs aiohttp and its dependencies from PyPI. Internet access is required for this installation. Subsequent starts reuse that environment.
Open http://127.0.0.1:19494/ in Chrome. No administrator access, DLL, business login, pairing key, or extension ID registration is required.
The server binds only to 127.0.0.1. It does not replace or modify the existing observer receiver on port 19484.
To stop, press Ctrl+C in the receiver terminal.

Actual public website test
1. Start this receiver and install/enable DOM Router.
2. In the extension, Connections > Quick connect: ws://127.0.0.1:19494/v1/demo/events. Connect and grant the requested local-host access.
3. Download GenQRCode > WS JSON from the receiver dashboard, then import it in the extension. Choose local-ws-demo, save, and Apply / reload. Grant genqrcode.com access.
4. If another GenQRCode profile is already applied for the same source, stop it first, or update that existing profile's receiver instead. Duplicate source ownership may be rejected.
5. Open https://genqrcode.com/ko. Enter https://example.com/dom-router-review and click Generate QR Code.
6. Check the receiver dashboard for diagnostic.observed with the same URL, generated:true, imageFormat:svg, an event ID and a received timestamp.
This profile freezes the URL from the generation request and validates HTTP 200 and the SVG response. It does not decode the QR image. Inspect extension logs if the website fails or changes its response format.

Local DOM test (no public website needed)
Download DOM > WS JSON or DOM > HTTP JSON from the dashboard.
Use ws://127.0.0.1:19494/v1/demo/events (local-ws-demo) or http://127.0.0.1:19494/v1/demo/events (local-http-demo).
Connect, import the corresponding profile, save and apply it. Reload the receiver page, then click the matching Observe WS / Observe HTTP button.
These buttons do not POST an event on their own: the applied extension must observe the trusted click and selected DOM values.
Check the stored transport and synthetic REVIEW-001 / Example recipient payload.
HTTP is not a persistent connection; its operation is not represented by the dashboard's WS client count.

Protocol and storage
POST /v1/demo/events accepts one application/json event.
WebSocket at the same path accepts one JSON event per text message. No HELLO or pairing is needed; use json-event / authentication:none.
Only diagnostic.observed + demo + GENERIC events are accepted. Business events and real authentication QR URLs are rejected. If qrUrl is present, it must use https://example.com or https://example.invalid.
Other strings cannot automatically be classified as personal information; submit synthetic data only.
After SQLite commit the receiver returns {stored:true,eventId,duplicate,sequence}. DOM Router's generic WS mode does not wait for this durable receipt; inspect the receiver's records as well as the extension's sent log.
Identical event IDs and contents are deduplicated. Reusing an ID with different contents is rejected.
data/events.sqlite3 retains up to 1,000 events for up to 24 hours. The dashboard shows the latest 100. Expiry is checked every 60 seconds and on reads/writes.
data/receiver.log and rotated backups record operational metadata, event IDs and error codes, not payloads.
JSON Export exports the currently displayed records. Clear removes this receiver's DB events only; exported files and the extension's own logs/queue remain.
Stop the receiver before deleting its folder and local files.

Scope
This program does not forward data, contact a developer backend, scan documents, issue authentication QR codes or submit business jobs. Dependency installation and your own use of a public QR website are separate network operations.
Host/Origin checks reject ordinary requests from unrelated websites, but do not authenticate other programs on the same computer.
This is an unencrypted loopback HTTP/WS test receiver for synthetic/public examples. It is not a production receiver for personal or authentication data and does not establish Chrome Web Store compliance for other data handling in the extension.
The distributed extension also includes business-specific templates. This kit tests the shared event path using public examples; it does not demonstrate those restricted websites or replace the need to explain/review their behavior.

Troubleshooting
Port in use: stop a previous instance or run start.cmd --port 19495 (sh start.sh --port 19495 on macOS/Linux). Update extension endpoints and download fresh DOM profiles from that port's dashboard. Bundled static DOM profiles use port 19494.
WS_CONNECTION_FAILED: check that the receiver is running, the port is correct and the address uses 127.0.0.1.
PUBLIC_EXAMPLE_URL_REQUIRED: use an example.com URL rather than a live authentication link.
REVIEW_DIAGNOSTIC_ONLY: do not connect a production/business profile to this receiver.
Connected but no events: verify profile application and extension execution logs. Connecting does not by itself apply a profile.

Tests
Windows: .venv\Scripts\python -m unittest discover -s tests -v
macOS/Linux: .venv/bin/python -m unittest discover -s tests -v
See VERIFICATION.json for the recorded scope of verification. This archive excludes the virtual environment, credentials and runtime logs/database.
