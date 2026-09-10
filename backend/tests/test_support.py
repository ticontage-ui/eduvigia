from app.application import SupportRequestIn


def test_support_request_schema():
    payload = SupportRequestIn(
        name="Operador Teste",
        email="operador@escola.local",
        category="ERRO",
        subject="Erro ao abrir monitoramento",
        message="O monitoramento não abriu durante o teste de homologação.",
    )
    assert payload.category == "ERRO"
