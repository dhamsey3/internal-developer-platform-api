from api.routes.system import system_readiness


def test_system_readiness_reports_tokens_and_preview_routing(monkeypatch):
    monkeypatch.setattr("api.routes.system.settings.GITHUB_DISPATCH_TOKEN", "dispatch")
    monkeypatch.setattr("api.routes.system.settings.DEPLOYMENT_CALLBACK_TOKEN", "callback")

    readiness = system_readiness()

    assert readiness["dispatch_token_present"] is True
    assert readiness["callback_token_present"] is True
    assert readiness["preview_routing_configured"] is False
