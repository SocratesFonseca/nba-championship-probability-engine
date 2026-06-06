def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "test"}


def test_data_status_endpoint_without_downloaded_files(client):
    response = client.get("/data/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == "nba_api"
    assert payload["training_dataset_available"] is False
    assert payload["metadata_available"] is False
    assert payload["raw_cache_files"] == 0
    assert payload["last_generated_at"] is None
