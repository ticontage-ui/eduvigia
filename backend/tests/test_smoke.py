def test_asgi_entrypoint_imports():
    from app.main import app

    assert app.title == "EduVigIA API"
    assert app.version == "2.0.0-F7-R2"
