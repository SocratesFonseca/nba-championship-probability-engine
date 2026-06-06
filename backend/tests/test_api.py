def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "test"}


def test_data_status_endpoint_without_downloaded_files(client):
    response = client.get("/data/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_dir_exists"] is True
    assert payload["database_has_import_metadata"] is False
    assert payload["files_valid"] is False
    assert payload["missing_files"]
    assert payload["last_imported_at"] is None
