def csrf_headers(client):
    response = client.get("/api/auth/csrf")
    if response.status_code != 200:
        raise AssertionError(f"csrf token request failed: {response.status_code}")
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def post_json_with_csrf(client, path, payload=None, **kwargs):
    return client.post(
        path,
        json={} if payload is None else payload,
        headers=csrf_headers(client),
        **kwargs,
    )


def put_json_with_csrf(client, path, payload=None, **kwargs):
    return client.put(
        path,
        json={} if payload is None else payload,
        headers=csrf_headers(client),
        **kwargs,
    )


def delete_with_csrf(client, path, **kwargs):
    return client.delete(path, headers=csrf_headers(client), **kwargs)
