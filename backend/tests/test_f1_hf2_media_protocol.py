from starlette.requests import Request

from app.application import _public_media_base


def _request(host: str, scheme: str = "http") -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "scheme": scheme,
        "server": ("127.0.0.1", 8000),
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"host", host.encode("ascii"))],
        "client": ("127.0.0.1", 12345),
    })


def test_dev_media_url_uses_http_when_configured(monkeypatch):
    monkeypatch.delenv("EDUVIGIA_WEBRTC_PUBLIC_BASE", raising=False)
    monkeypatch.delenv("EDUVIGIA_HLS_PUBLIC_BASE", raising=False)
    monkeypatch.setenv("EDUVIGIA_MEDIA_PUBLIC_SCHEME", "http")
    request = _request("192.168.1.100:8002", scheme="http")
    assert _public_media_base(request, protocol="webrtc") == "http://192.168.1.100:18889"
    assert _public_media_base(request, protocol="hls") == "http://192.168.1.100:18888"


def test_production_media_url_can_still_use_https(monkeypatch):
    monkeypatch.delenv("EDUVIGIA_WEBRTC_PUBLIC_BASE", raising=False)
    monkeypatch.delenv("EDUVIGIA_HLS_PUBLIC_BASE", raising=False)
    monkeypatch.setenv("EDUVIGIA_MEDIA_PUBLIC_SCHEME", "https")
    request = _request("video.exemplo.local:8002", scheme="http")
    assert _public_media_base(request, protocol="webrtc") == "https://video.exemplo.local:18889"
    assert _public_media_base(request, protocol="hls") == "https://video.exemplo.local:18888"


def test_explicit_media_base_has_priority(monkeypatch):
    monkeypatch.setenv("EDUVIGIA_WEBRTC_PUBLIC_BASE", "https://video.exemplo.local:9443/")
    request = _request("127.0.0.1:8002", scheme="http")
    assert _public_media_base(request, protocol="webrtc") == "https://video.exemplo.local:9443"
