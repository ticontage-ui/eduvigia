import os

# Valores exclusivamente de teste. setdefault preserva valores definidos por CI/ambiente.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_VERSION", "2.0.0-F8-R1")
os.environ.setdefault("DATABASE_URL", "sqlite:///./eduvigia-test.db")
os.environ.setdefault("EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD", "Teste@2026!")
os.environ.setdefault(
    "EDUVIGIA_STREAM_SIGNING_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef",
)
os.environ.setdefault(
    "EDUVIGIA_CREDENTIAL_KEY",
    "4bV57HNT7lzNSNQI19_-kb8OTKe_k1HyV3BOaYlaaIs=",
)