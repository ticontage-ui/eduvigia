from app.application import validate_password_policy, token_digest


def test_token_digest_is_not_plain_text():
    token = "token-de-teste"
    digest = token_digest(token)
    assert digest.startswith("sha256:")
    assert token not in digest


def test_password_policy_accepts_strong_password():
    validate_password_policy("SenhaForte@2026")
