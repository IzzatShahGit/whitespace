from httpx import AsyncClient

USER = {"email": "Ahmed@Example.com", "full_name": "Ahmed Khan", "password": "towels-2026!"}


async def _register(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=USER)
    assert response.status_code == 201, response.text


async def test_register_signs_in_and_hides_tokens(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=USER)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ahmed@example.com"  # stored lowercase
    assert "password" not in body and "password_hash" not in body
    set_cookie = response.headers.get_list("set-cookie")
    assert any(c.startswith("ws_access=") and "HttpOnly" in c for c in set_cookie)
    assert any(c.startswith("ws_refresh=") and "Path=/api/v1/auth" in c for c in set_cookie)

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["full_name"] == "Ahmed Khan"


async def test_duplicate_email_rejected(client: AsyncClient) -> None:
    await _register(client)
    response = await client.post(
        "/api/v1/auth/register", json={**USER, "email": "ahmed@example.com"}
    )
    assert response.status_code == 409


async def test_short_password_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json={**USER, "password": "short"})
    assert response.status_code == 422


async def test_login_with_right_and_wrong_password(client: AsyncClient) -> None:
    await _register(client)
    client.cookies.clear()

    wrong = await client.post(
        "/api/v1/auth/login", json={"email": USER["email"], "password": "not-it-at-all"}
    )
    assert wrong.status_code == 401
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever1"}
    )
    assert unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]  # no hint which one was wrong

    ok = await client.post(
        "/api/v1/auth/login", json={"email": "AHMED@example.com", "password": USER["password"]}
    )
    assert ok.status_code == 200
    assert (await client.get("/api/v1/auth/me")).status_code == 200


async def test_me_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_refresh_rotates_and_old_token_is_rejected(client: AsyncClient) -> None:
    await _register(client)
    old_refresh = client.cookies.get("ws_refresh")

    rotated = await client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    assert client.cookies.get("ws_refresh") != old_refresh

    # Replaying the old token fails and ends every session (possible theft).
    client.cookies.set("ws_refresh", old_refresh, path="/api/v1/auth")
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401


async def test_logout_ends_session(client: AsyncClient) -> None:
    await _register(client)
    refresh_token = client.cookies.get("ws_refresh")
    assert (await client.post("/api/v1/auth/logout")).status_code == 204

    client.cookies.set("ws_refresh", refresh_token, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
