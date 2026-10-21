"""DOM Router review receiver: loopback-only diagnostic JSON events, no forwarding."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from aiohttp import WSMsgType, web

VERSION = "1.0.0"
MAX_BYTES = 65536
EVENT_PATH = "/v1/demo/events"
ROOT = Path(__file__).resolve().parent
EXTENSION_ORIGIN = re.compile(r"chrome-extension://[a-p]{32}\Z")
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
STORE = web.AppKey("store", object)
SOCKETS = web.AppKey("sockets", set)
NONCE = web.AppKey("nonce", str)
ORIGIN = web.AppKey("origin", str)
LOG = logging.getLogger("dom-router-review")
PORT = web.AppKey("port", int)


class Rejected(ValueError):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical(event):
    return json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def parse_event(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise Rejected("DUPLICATE_JSON_KEY")
            obj[key] = value
        return obj
    if len(raw if isinstance(raw, bytes) else raw.encode("utf-8")) > MAX_BYTES:
        raise Rejected("EVENT_TOO_LARGE", 413)
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(Rejected("NONFINITE_NUMBER")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, Rejected):
            raise
        raise Rejected("INVALID_JSON") from exc
    validate_event(value)
    return value


def require(ok, code="INVALID_EVENT"):
    if not ok:
        raise Rejected(code)


def exact(obj, names):
    require(isinstance(obj, dict) and set(obj) == set(names), "EVENT_FIELDS_INVALID")


def text(value, limit, minimum=1):
    require(isinstance(value, str) and minimum <= len(value) <= limit, "STRING_INVALID")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise Rejected("STRING_ENCODING_INVALID") from exc


def uuid(value):
    text(value, 36)
    try:
        require(str(UUID(value)) == value.lower(), "UUID_INVALID")
    except ValueError as exc:
        raise Rejected("UUID_INVALID") from exc


def validate_event(e):
    exact(e, "schemaVersion eventId eventType occurredAt profile channel carrier scopeId source correlation payload".split())
    require(type(e["schemaVersion"]) is int and e["schemaVersion"] == 1, "SCHEMA_VERSION_INVALID")
    require(e["eventType"] == "diagnostic.observed" and e["channel"] == "demo"
            and e["carrier"] == "GENERIC", "REVIEW_DIAGNOSTIC_ONLY")
    uuid(e["eventId"])
    text(e["occurredAt"], 50)
    try:
        date = datetime.fromisoformat(e["occurredAt"].replace("Z", "+00:00"))
        require("T" in e["occurredAt"] and date.utcoffset() is not None, "EVENT_TIME_INVALID")
    except ValueError as exc:
        raise Rejected("EVENT_TIME_INVALID") from exc
    exact(e["profile"], ["id", "revision"])
    require(isinstance(e["profile"]["id"], str) and IDENTIFIER.fullmatch(e["profile"]["id"]), "PROFILE_ID_INVALID")
    require(type(e["profile"]["revision"]) is int and e["profile"]["revision"] >= 1)
    text(e["scopeId"], 100)
    s = e["source"]
    exact(s, ["instanceId", "tabId", "frameId", "documentGeneration", "origin"])
    uuid(s["instanceId"])
    uuid(s["documentGeneration"])
    require(all(type(s[k]) is int and s[k] >= 0 for k in ("tabId", "frameId")))
    text(s["origin"], 200)
    try:
        u = urlsplit(s["origin"])
        require(u.scheme in ("http", "https") and u.hostname and not u.username and not u.password
                and not u.path and not u.query and not u.fragment, "SOURCE_ORIGIN_INVALID")
        require(u.scheme == "https" or u.hostname == "127.0.0.1", "SOURCE_ORIGIN_INVALID")
        _ = u.port
    except ValueError as exc:
        raise Rejected("SOURCE_ORIGIN_INVALID") from exc
    c = e["correlation"]
    exact(c, ["flowId", "callId"])
    require(isinstance(c["flowId"], str) and IDENTIFIER.fullmatch(c["flowId"]), "FLOW_ID_INVALID")
    if c["callId"] is not None:
        text(c["callId"], 120)
    p = e["payload"]
    require(isinstance(p, dict) and len(p) <= 16, "PAYLOAD_INVALID")
    for key, value in p.items():
        text(key, 100)
        require(type(value) in (str, int, float, bool, type(None)), "PAYLOAD_NOT_FLAT")
        if isinstance(value, str):
            text(value, 2048, 0)
        if isinstance(value, float):
            require(math.isfinite(value), "NONFINITE_NUMBER")
    # This recipient is for public/synthetic examples, not live authentication URLs.
    if "qrUrl" in p:
        text(p["qrUrl"], 2048)
        try:
            u = urlsplit(p["qrUrl"])
        except ValueError as exc:
            raise Rejected("PUBLIC_EXAMPLE_URL_REQUIRED") from exc
        require(u.scheme == "https" and u.netloc in ("example.com", "example.invalid")
                and not u.username and not u.password, "PUBLIC_EXAMPLE_URL_REQUIRED")


class EventStore:
    def __init__(self, path, *, max_events=1000, retention_seconds=86400):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "event_id TEXT UNIQUE NOT NULL, received_at TEXT NOT NULL, received_epoch REAL NOT NULL, "
                        "transport TEXT NOT NULL, digest TEXT NOT NULL, event TEXT NOT NULL)")
        self.max_events, self.retention_seconds = max_events, retention_seconds
        self.prune()

    def prune(self):
        with self.db:
            self.db.execute("DELETE FROM events WHERE received_epoch < ?", (time.time() - self.retention_seconds,))
            self.db.execute("DELETE FROM events WHERE sequence NOT IN (SELECT sequence FROM events ORDER BY sequence DESC LIMIT ?)", (self.max_events,))

    def put(self, event, transport):
        self.prune()
        raw = canonical(event)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        old = self.db.execute("SELECT digest,sequence FROM events WHERE event_id=?", (event["eventId"],)).fetchone()
        if old:
            if old[0] != digest:
                raise Rejected("EVENT_ID_CONFLICT", 409)
            return {"stored": True, "eventId": event["eventId"], "duplicate": True, "sequence": old[1]}
        with self.db:
            cursor = self.db.execute("INSERT INTO events(event_id,received_at,received_epoch,transport,digest,event) VALUES(?,?,?,?,?,?)",
                                     (event["eventId"], utc_now(), time.time(), transport, digest, raw))
            sequence = cursor.lastrowid
        self.prune()
        LOG.info("event.stored transport=%s sequence=%s eventId=%s", transport, sequence, event["eventId"])
        return {"stored": True, "eventId": event["eventId"], "duplicate": False, "sequence": sequence}

    def records(self, limit=100):
        self.prune()
        rows = self.db.execute("SELECT sequence,received_at,transport,event FROM events ORDER BY sequence DESC LIMIT ?", (limit,)).fetchall()
        return [{"sequence": s, "receivedAt": t, "transport": via, "event": json.loads(raw)} for s, t, via, raw in rows]

    def count(self):
        self.prune()
        return self.db.execute("SELECT count(*) FROM events").fetchone()[0]

    def clear(self):
        with self.db:
            self.db.execute("DELETE FROM events")
        self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        LOG.info("events.cleared")

    def close(self):
        self.db.close()


def make_profile(kind, port):
    if kind == "genqrcode-ws":
        return json.loads((ROOT / "profiles" / "genqrcode-ws.profile.json").read_text(encoding="utf-8"))
    transport = kind.removeprefix("dom-")
    require(transport in ("ws", "http"), "PROFILE_NOT_FOUND")
    origin = f"http://127.0.0.1:{port}"
    return {"schemaVersion": 1, "profileId": f"review-dom-{transport}", "revision": 1,
            "engineMajor": 1, "name": f"Review · DOM → {transport.upper()}",
            "description": "Local synthetic DOM data only. No business submissions.",
            "enabled": False, "channel": "demo", "carrier": "GENERIC", "connectionRef": f"local-{transport}-demo",
            "origins": [origin], "flows": [{"id": f"read-review-{transport}", "name": "Click → read → send",
            "source": {"type": "dom.event", "origin": origin, "event": "click", "selector": f"#send-{transport}",
                       "requireTrustedClick": True, "reads": [{"name": "document-id", "selector": "#document-id", "read": "value", "maxLength": 100},
                       {"name": "recipient", "selector": "#recipient", "read": "text", "maxLength": 200}]},
            "steps": [{"id": "read-fields", "type": "extract.fields", "fields": [{"name": "documentId", "from": "/dom/document-id"},
                       {"name": "recipient", "from": "/dom/recipient"}]},
                      {"id": "emit-review", "type": "emit.event", "eventType": "diagnostic.observed",
                       "bindings": {"/documentId": "/vars/documentId", "/recipient": "/vars/recipient"}}]}]}


@web.middleware
async def guard(request, handler):
    origin = request.headers.get("Origin")
    is_extension = bool(origin and EXTENSION_ORIGIN.fullmatch(origin))
    # Privileged extension fetch may omit Origin. An explicit extension header
    # is accepted only when there is no contradictory browser Origin.
    declared = request.headers.get("X-Dom-Router-Origin")
    extension_fetch = is_extension or (not origin and bool(declared and EXTENSION_ORIGIN.fullmatch(declared)))
    try:
        # Exact Host matching also rejects DNS rebinding and proxy absolute-host tricks.
        if request.headers.get("Host") != request.app[ORIGIN].removeprefix("http://"):
            raise Rejected("HOST_NOT_ALLOWED", 403)
        if origin and origin != request.app[ORIGIN] and not is_extension:
            raise Rejected("ORIGIN_NOT_ALLOWED", 403)
        if (request.headers.get("Sec-Fetch-Site") == "cross-site" and not is_extension
                and request.path not in ("/", "/app.js", "/styles.css")):
            raise Rejected("CROSS_SITE_NOT_ALLOWED", 403)
        if request.path == EVENT_PATH:
            if request.method in ("POST", "OPTIONS") or request.headers.get("Upgrade", "").lower() == "websocket":
                if not (is_extension if request.headers.get("Upgrade", "").lower() == "websocket" else extension_fetch):
                    raise Rejected("EXTENSION_ORIGIN_REQUIRED", 403)
        response = await handler(request)
    except Rejected as exc:
        LOG.warning("request.rejected code=%s", exc.code)
        response = web.json_response({"stored": False, "error": exc.code}, status=exc.status)
    except web.HTTPException as exc:
        response = web.json_response({"stored": False, "error": "HTTP_" + str(exc.status)}, status=exc.status)
    if is_extension and request.path == EVENT_PATH:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, HEAD, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Dom-Router-Origin"
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    return response


async def events(request):
    store = request.app[STORE]
    if request.method in ("HEAD", "OPTIONS"):
        return web.Response(status=200 if request.method == "HEAD" else 204)
    if request.method == "POST":
        if request.content_type != "application/json":
            raise Rejected("JSON_CONTENT_TYPE_REQUIRED", 415)
        event = parse_event(await request.read())
        return web.json_response(store.put(event, "http"))
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=MAX_BYTES, compress=False)
    if not ws.can_prepare(request).ok:
        raise Rejected("WEBSOCKET_UPGRADE_REQUIRED", 426)
    await ws.prepare(request)
    request.app[SOCKETS].add(ws)
    LOG.info("ws.connected")
    try:
        async for message in ws:
            if message.type == WSMsgType.TEXT:
                try:
                    receipt = store.put(parse_event(message.data), "ws")
                    await ws.send_json(receipt)
                except Rejected as exc:
                    LOG.warning("ws.rejected code=%s", exc.code)
                    await ws.send_json({"stored": False, "error": exc.code})
                    await ws.close(code=1008, message=exc.code.encode())
            elif message.type == WSMsgType.BINARY:
                await ws.close(code=1003, message=b"TEXT_JSON_REQUIRED")
    finally:
        request.app[SOCKETS].discard(ws)
        LOG.info("ws.disconnected")
    return ws


async def api_events(request):
    return web.json_response({"version": VERSION, "count": request.app[STORE].count(),
                              "wsClients": len(request.app[SOCKETS]), "records": request.app[STORE].records()})


async def clear_events(request):
    # UI nonce is for this destructive dashboard action, not an extension pairing key.
    if request.headers.get("Origin") != request.app[ORIGIN] or not secrets.compare_digest(
            request.headers.get("X-Review-Nonce", ""), request.app[NONCE]):
        raise Rejected("DASHBOARD_CONFIRMATION_REQUIRED", 403)
    request.app[STORE].clear()
    return web.json_response({"cleared": True})


async def status(request):
    return web.json_response({"name": "DOM Router Review Receiver", "version": VERSION, "diagnosticOnly": True,
                              "count": request.app[STORE].count(), "wsClients": len(request.app[SOCKETS])})


async def session(request):
    if request.headers.get("Origin") not in (None, request.app[ORIGIN]):
        raise Rejected("DASHBOARD_ONLY", 403)
    return web.json_response({"nonce": request.app[NONCE], "origin": request.app[ORIGIN]})


async def profile(request):
    kind = request.match_info["name"]
    if kind not in ("dom-http", "dom-ws", "genqrcode-ws"):
        raise web.HTTPNotFound()
    response = web.json_response(make_profile(kind, request.app[PORT]), dumps=lambda v: json.dumps(v, ensure_ascii=False, indent=2))
    response.headers["Content-Disposition"] = f'attachment; filename="{kind}.profile.json"'
    return response


async def asset(request):
    names = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/styles.css": ("styles.css", "text/css")}
    name, content_type = names[request.path]
    return web.Response(text=(ROOT / "web" / name).read_text(encoding="utf-8"), content_type=content_type)


async def lifecycle(app):
    async def prune():
        while True:
            await asyncio.sleep(60)
            app[STORE].prune()
    task = asyncio.create_task(prune())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    app[STORE].close()


async def close_sockets(app):
    await asyncio.gather(*(ws.close(code=1001, message=b"RECEIVER_STOPPING") for ws in tuple(app[SOCKETS])))


def create_app(data_dir, port=19494, *, max_events=1000, retention_seconds=86400):
    app = web.Application(middlewares=[guard], client_max_size=MAX_BYTES)
    app[STORE] = EventStore(Path(data_dir) / "events.sqlite3", max_events=max_events, retention_seconds=retention_seconds)
    app[SOCKETS], app[NONCE], app[ORIGIN], app[PORT] = set(), secrets.token_urlsafe(32), f"http://127.0.0.1:{port}", port
    app.cleanup_ctx.append(lifecycle)
    app.on_shutdown.append(close_sockets)
    app.router.add_route("*", EVENT_PATH, events)
    app.router.add_get("/health", status)
    app.router.add_get("/api/events", api_events)
    app.router.add_get("/api/session", session)
    app.router.add_post("/api/clear", clear_events)
    app.router.add_get("/profiles/{name}.profile.json", profile)
    for route in ("/", "/app.js", "/styles.css"):
        app.router.add_get(route, asset)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=19494)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024..65535")
    args.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[
        logging.StreamHandler(), RotatingFileHandler(args.data_dir / "receiver.log", maxBytes=1048576,
                                                     backupCount=2, encoding="utf-8")])
    LOG.info("receiver.start version=%s address=http://127.0.0.1:%s diagnosticOnly=true", VERSION, args.port)
    try:
        web.run_app(create_app(args.data_dir, args.port), host="127.0.0.1", port=args.port, access_log=None,
                    shutdown_timeout=3, print=None)
    except OSError as exc:
        LOG.error("Cannot bind port %s: %s. Stop this receiver's previous instance or use --port.", args.port, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
