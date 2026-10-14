"""HTTPS helper: this PC's Python build has no CA bundle, so urllib fails on
every HTTPS call. We use requests (already installed via ultralytics) or
certifi's CA file with urllib as a fallback."""
import json
import ssl
import urllib.parse
import urllib.request

try:
    import requests as _requests
except Exception:
    _requests = None

_CTX = None


def _ssl_ctx():
    global _CTX
    if _CTX is None:
        try:
            import certifi
            _CTX = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            _CTX = ssl.create_default_context()
    return _CTX


def _json_or_none(text):
    try:
        return json.loads(text) if text else {}
    except Exception:
        return {}


def get_json(url, params=None, timeout=15):
    if _requests is not None:
        r = _requests.get(url, params=params, timeout=timeout)
        return r.status_code, _json_or_none(r.text)
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
        return resp.status, _json_or_none(resp.read().decode())


def post_form(url, params, timeout=15):
    if _requests is not None:
        r = _requests.post(url, data=params, timeout=timeout)
        return r.status_code, _json_or_none(r.text)
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
        return resp.status, _json_or_none(resp.read().decode())


def post_json(url, payload, timeout=5, headers=None):
    data = json.dumps(payload).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    if _requests is not None:
        r = _requests.post(url, data=data, headers=h, timeout=timeout)
        return r.status_code == 200
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
        return resp.status == 200
