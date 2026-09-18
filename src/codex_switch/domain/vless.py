"""VLESS URI validation and transport mapping; all functions are pure."""

import base64
import hashlib
import json
import re
from urllib.parse import parse_qsl, unquote, urlsplit
import uuid

from .errors import SwitchError
from .models import Server


def parse_vless(text: str) -> Server:
    if not isinstance(text, str) or len(text) > 16384:
        raise SwitchError("Ссылка слишком длинная.")
    text = text.strip()
    if not text.lower().startswith("vless://"):
        raise SwitchError("Вставь ссылку, которая начинается с vless://.")
    try:
        url = urlsplit(text)
        host, port = url.hostname, url.port if url.port is not None else 443
        user = str(uuid.UUID(unquote(url.username or "")))
        if url.password or not host or url.path not in ("", "/"):
            raise ValueError()
        if any(c.isspace() or ord(c) < 32 for c in host) or not 1 <= port <= 65535:
            raise ValueError()
        pairs = parse_qsl(url.query, keep_blank_values=True, max_num_fields=48)
    except (ValueError, AttributeError):
        raise SwitchError("В ссылке некорректный UUID, адрес сервера или порт.") from None
    query = dict(pairs)
    if len(query) != len(pairs):
        raise SwitchError("В ссылке повторяются параметры. Проверь её у провайдера.")
    known = {"type", "security", "encryption", "flow", "sni", "serverName", "fp", "pbk",
             "sid", "spx", "alpn", "host", "path", "serviceName", "mode", "authority",
             "headerType", "allowInsecure", "insecure", "extra", "remark", "remarks"}
    if set(query) - known:
        raise SwitchError("В ссылке есть неподдерживаемые параметры. Поддерживаются TCP, WS, gRPC, XHTTP и HTTPUpgrade.")
    if any(ord(c) < 32 for value in query.values() for c in value):
        raise SwitchError("Параметры ссылки содержат недопустимые символы.")
    transport = query.get("type", "tcp") or "tcp"
    transport = {"raw": "tcp", "splithttp": "xhttp"}.get(transport, transport)
    if transport not in {"tcp", "ws", "grpc", "xhttp", "httpupgrade"}:
        raise SwitchError("Этот транспорт пока не поддерживается. Доступны TCP, WS, gRPC, XHTTP и HTTPUpgrade.")
    security = query.get("security", "none") or "none"
    if security not in {"none", "tls", "reality"}:
        raise SwitchError("Поддерживаются TLS, REALITY и соединения без TLS.")
    if query.get("encryption", "none") not in ("", "none"):
        raise SwitchError("Пока поддерживаются VLESS-ссылки с encryption=none.")
    if query.get("allowInsecure", "0").lower() not in ("0", "false", "") or query.get("insecure", "0").lower() not in ("0", "false", ""):
        raise SwitchError("Отключение проверки TLS-сертификата не поддерживается.")
    flow = query.get("flow", "")
    if flow not in ("", "xtls-rprx-vision") or (flow and (transport != "tcp" or security == "none")):
        raise SwitchError("XTLS Vision поддерживается только с TCP и TLS / REALITY.")
    if query.get("headerType", "none") not in ("", "none"):
        raise SwitchError("TCP-маскировка headerType не поддерживается.")
    stream = {"network": transport, "security": security}
    server_name = query.get("sni") or query.get("serverName") or host
    fingerprint = query.get("fp") or "chrome"
    if security == "tls":
        tls = {"serverName": server_name, "fingerprint": fingerprint}
        if query.get("alpn"):
            tls["alpn"] = query["alpn"].split(",")
        stream["tlsSettings"] = tls
    if security == "reality":
        try:
            public_key = query["pbk"]
            if not re.fullmatch(r"[A-Za-z0-9_-]{43}", public_key) or len(base64.urlsafe_b64decode(public_key + "=")) != 32:
                raise ValueError()
            sid = query.get("sid", "")
            if len(sid) > 16 or len(sid) % 2 or not re.fullmatch(r"[a-fA-F0-9]*", sid):
                raise ValueError()
        except (KeyError, ValueError):
            raise SwitchError("В REALITY-ссылке отсутствует корректный pbk или sid.") from None
        if transport not in ("tcp", "grpc", "xhttp"):
            raise SwitchError("REALITY доступен с TCP, gRPC и XHTTP.")
        stream["realitySettings"] = {"serverName": server_name, "fingerprint": fingerprint,
                                     "password": public_key, "shortId": sid, "spiderX": query.get("spx", "/")}
    if transport == "ws":
        stream["wsSettings"] = {"path": query.get("path", "/"), "headers": {"Host": query.get("host") or server_name}}
    elif transport == "grpc":
        mode = query.get("mode", "gun")
        if mode not in ("gun", "multi", ""):
            raise SwitchError("Неизвестный режим gRPC.")
        stream["grpcSettings"] = {"serviceName": query.get("serviceName", ""), "multiMode": mode == "multi"}
        if query.get("authority"):
            stream["grpcSettings"]["authority"] = query["authority"]
    elif transport in ("xhttp", "httpupgrade"):
        settings = {"path": query.get("path", "/"), "host": query.get("host") or server_name}
        if transport == "xhttp":
            mode = query.get("mode", "auto")
            if mode not in ("auto", "packet-up", "stream-up", "stream-one"):
                raise SwitchError("Неизвестный режим XHTTP.")
            settings["mode"] = mode
            if query.get("extra"):
                # Extra can contain arbitrary destinations; reject instead of silently changing behavior.
                raise SwitchError("XHTTP-ссылки с параметром extra пока не поддерживаются.")
        stream[transport + "Settings"] = settings
    name = unquote(url.fragment) or query.get("remarks") or query.get("remark") or host
    name = "".join(c for c in name if ord(c) >= 32)[:80].strip() or host
    outbound = {"tag": "vpn", "protocol": "vless", "settings": {"vnext": [{"address": host, "port": port,
                "users": [{"id": user, "encryption": "none", **({"flow": flow} if flow else {})}]}]},
                "streamSettings": stream}
    identity = hashlib.sha256(json.dumps(outbound, sort_keys=True).encode()).hexdigest()[:24]
    return Server(identity, name, host, port, transport, security, outbound)
