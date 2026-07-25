from services.monitoring_service import get_cluster_health


def test_dry_run_cluster_is_not_reported_as_healthy():
    health = get_cluster_health()
    assert health["status"] == "not_configured"
    assert health["nodes"] == 0
    assert health["ready_nodes"] == 0
