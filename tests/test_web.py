"""The website: host rules, ticket history, transcript links, profile API and payment pages."""

import hashlib
import os
import sys
import types
from pathlib import Path

import pytest

WEB = str(Path(__file__).resolve().parent.parent / "web")
OWN = ("utils", "app", "config", "main")
SETTINGS = dict(
    API_BASE="https://discord.test/api",
    CLIENT_ID="1",
    CLIENT_SECRET="s",
    REDIRECT_URI="https://fischl.app/dashboard",
    PROFILE_REDIRECT_URI="https://fischl.app/profile",
    MYSTICRAFT_CLIENT_ID="2",
    MYSTICRAFT_CLIENT_SECRET="s",
    MYSTICRAFT_REDIRECT_URI="https://ticket.mysticraft.xyz/callback",
    BOT_TOKEN="bot",
    BRAWL_TOKEN="brawl",
    MYSTICRAFT_TOKEN="mysti",
    PAYPAL_CLIENT_ID="pp",
    ELITE_TRACK_PRICE="4.99",
    POSTGRES_HOST="h",
    POSTGRES_USER="u",
    POSTGRES_PASSWORD="p",
    POSTGRES_DB="d",
)
SITE = "https://fischl.app"
HISTORY = "https://ticket.mysticraft.xyz"


def own(name):
    return name.split(".")[0] in OWN


@pytest.fixture(scope="module")
def web():
    """Loads the website's modules under their own names, then gives the bot's back."""
    kept = {name: module for name, module in sys.modules.items() if own(name)}
    for name in kept:
        del sys.modules[name]
    config = types.ModuleType("config")
    config.__path__ = []
    settings = types.ModuleType("config.settings")
    settings.__dict__.update(SETTINGS)
    sys.modules.update({"config": config, "config.settings": settings})
    sys.path.insert(0, WEB)
    try:
        import main

        loaded = {name: module for name, module in sys.modules.items() if own(name)}
    finally:
        sys.path.remove(WEB)
        for name in [name for name in sys.modules if own(name)]:
            del sys.modules[name]
        sys.modules.update(kept)
    main.app.config["TESTING"] = True
    return types.SimpleNamespace(
        main=main,
        logs=loaded["app.logs"],
        profile=loaded["app.profile"],
        history=loaded["app.ticket_history"],
        minigames=loaded["utils.minigames"],
        expeditions=loaded["app.expeditions"],
        paypal=loaded["utils.paypal"],
    )


@pytest.fixture
def client(web):
    web.profile.cache.clear()
    return web.main.app.test_client()


class Answer:
    def __init__(self, status=200, data=None, content=b""):
        self.status_code, self.data, self.content = status, data, content

    def json(self):
        return self.data


class Discord:
    """Stands in for the HTTP session; answers by the end of the address."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def ask(self, method, url, **options):
        self.calls.append((method, url, options))
        for ending, answer in self.routes.items():
            if url.endswith(ending):
                return answer(options) if callable(answer) else answer
        return Answer(404, {})

    def get(self, url, **options):
        return self.ask("GET", url, **options)

    def post(self, url, **options):
        return self.ask("POST", url, **options)


def wire(monkeypatch, web, routes):
    discord = Discord(routes)
    for module in (web.logs, web.profile, web.history, web.minigames):
        monkeypatch.setattr(module, "requests_session", discord)
    return discord


def log_in(client, **values):
    site = HISTORY if "user_data" in values else SITE
    with client.session_transaction(base_url=site) as session:
        session.update(values)


def test_other_hosts_get_404_except_logs(client):
    assert client.get("/", base_url="https://evil.test").status_code == 404
    assert client.get("/logs/x", base_url="https://evil.test").status_code == 400


def test_site_pages(client):
    assert b"<html" in client.get("/", base_url=SITE).data
    assert client.get("/legal", base_url=SITE).status_code == 200
    assert client.get("/variables", base_url=SITE).status_code == 200
    assert client.get("/legal", base_url=HISTORY).status_code == 404
    assert client.get("/nothing", base_url=SITE).status_code == 404


def test_logins_go_to_discord(client):
    site = client.get("/login", base_url=SITE).headers["Location"]
    assert "client_id=1&redirect_uri=https://fischl.app/dashboard" in site
    assert site.endswith("&response_type=code&scope=identify%20guilds&prompt=none")
    auth = client.get("/auth", base_url=SITE).headers["Location"]
    assert "redirect_uri=https://fischl.app/profile&" in auth
    history = client.get("/login", base_url=HISTORY).headers["Location"]
    assert history == (
        "https://discord.test/api/oauth2/authorize?client_id=2"
        "&redirect_uri=https://ticket.mysticraft.xyz/callback"
        "&response_type=code&scope=identify&prompt=none"
    )


def test_logout_clears_the_session(client):
    log_in(client, user_data={"id": "5"})
    assert client.get("/logout", base_url=HISTORY).headers["Location"] == "/"
    with client.session_transaction(base_url=HISTORY) as session:
        assert not session


def test_history_page_needs_login(client):
    assert b"login" in client.get("/", base_url=HISTORY).data.lower()
    assert client.get("/api/tickets", base_url=HISTORY).status_code == 401
    assert client.get("/api/tickets", base_url=SITE).status_code == 404


def closed(link, title="Ticket closed", when="2026-01-02T03:04:05Z", fields=None):
    return {
        "embeds": [
            {
                "title": title,
                "description": "Your ticket in **🎫 Mysticraft** was closed",
                "timestamp": when,
                "fields": fields or [],
            }
        ],
        "components": [{"type": 1, "components": [{"type": 2, "url": link}]}],
    }


def test_history_lists_closed_tickets_newest_first(client, web, monkeypatch):
    pages = [
        [
            {
                "id": "9",
                **closed("a", fields=[{"value": "Support"}, {"value": "Done"}]),
            },
            {"id": "8", **closed("a")},
            {"id": "7", **closed("b", when="2026-03-01T00:00:00+00:00")},
            {"id": "6", **closed("c", title="Ticket Closed")},
            {"id": "5", **closed("d", when="")},
            {"id": "4", "embeds": [{"title": "Ticket closed"}]},
        ],
        [],
    ]
    discord = wire(
        monkeypatch,
        web,
        {
            "/users/@me/channels": Answer(200, {"id": "77"}),
            "/channels/77/messages": lambda options: Answer(200, pages.pop(0)),
        },
    )
    log_in(client, user_data={"id": "5"})
    body = client.get("/api/tickets", base_url=HISTORY).get_json()
    assert body["error"] is None
    assert [t["transcript_link"] for t in body["tickets"]] == ["b", "a", "d"]
    first = body["tickets"][1]
    assert (first["category"], first["closing_reason"]) == ("Support", "Done")
    assert first["guild_name"] == "Mysticraft"
    assert first["date_str"] == "2026-01-02T03:04:05+00:00"
    assert body["tickets"][2]["date_str"] == "Unknown"
    assert body["tickets"][0]["category"] == "Tickets"
    assert discord.calls[2][2]["params"] == {"limit": 100, "before": "4"}
    assert discord.calls[0][2]["headers"] == {"Authorization": "Bot mysti"}


def test_history_without_a_dm_channel_is_empty(client, web, monkeypatch):
    wire(monkeypatch, web, {"/users/@me/channels": Answer(403, {})})
    log_in(client, user_data={"id": "5"})
    body = client.get("/api/tickets", base_url=HISTORY).get_json()
    assert body == {"tickets": [], "error": None}


def test_callback_logs_the_member_in(client, web, monkeypatch):
    discord = wire(
        monkeypatch,
        web,
        {
            "/oauth2/token": Answer(200, {"access_token": "tok"}),
            "/users/@me": Answer(
                200, {"id": "5", "username": "ian", "discriminator": "0"}
            ),
        },
    )
    answer = client.get("/callback?code=abc", base_url=HISTORY)
    assert answer.headers["Location"] == "/"
    assert discord.calls[0][2]["data"]["code"] == "abc"
    with client.session_transaction(base_url=HISTORY) as session:
        assert session["user_data"] == {
            "id": "5",
            "username": "ian",
            "discriminator": "0",
            "access_token": "tok",
        }


@pytest.mark.parametrize(
    "query, routes, text",
    [
        ("error=denied", {}, b"Authentication cancelled."),
        ("", {}, b"No authorization code received."),
        (
            "code=x",
            {"/oauth2/token": Answer(400, {})},
            b"Failed to authenticate with Discord.",
        ),
        (
            "code=x",
            {"/oauth2/token": Answer(200, {})},
            b"Failed to retrieve access token.",
        ),
        (
            "code=x",
            {
                "/oauth2/token": Answer(200, {"access_token": "t"}),
                "/users/@me": Answer(401),
            },
            b"Failed to fetch user information.",
        ),
    ],
)
def test_callback_failures(client, web, monkeypatch, query, routes, text):
    wire(monkeypatch, web, routes)
    assert text in client.get(f"/callback?{query}", base_url=HISTORY).data
    assert client.get(f"/callback?{query}", base_url=SITE).status_code == 404


def link(channel, message, content):
    checksum = hashlib.sha256(content + channel.encode()).hexdigest()[:20]
    return f"/logs/{channel}-{message}-{checksum}"


def test_log_link_shows_the_transcript(client, web, monkeypatch):
    discord = wire(
        monkeypatch,
        web,
        {
            "/channels/10/messages/20": lambda options: (
                Answer(200, {"attachments": [{"url": "https://cdn.test/file.html"}]})
                if options["headers"]["Authorization"] == "Bot brawl"
                else Answer(403)
            ),
            "/file.html": Answer(200, content=b"<html>hi</html>"),
        },
    )
    answer = client.get(link("10", "20", b"<html>hi</html>"), base_url=SITE)
    assert answer.data == b"<html>hi</html>"
    assert answer.mimetype == "text/html"
    assert [call[2].get("headers") for call in discord.calls] == [
        {"Authorization": "Bot bot"},
        {"Authorization": "Bot brawl"},
        None,
    ]


def test_log_link_failures(client, web, monkeypatch):
    wire(
        monkeypatch,
        web,
        {
            "/channels/10/messages/20": Answer(
                200, {"attachments": [{"url": "x/file"}]}
            ),
            "/channels/10/messages/21": Answer(200, {"attachments": []}),
            "/file": Answer(200, content=b"real"),
        },
    )
    assert client.get("/logs/10-20", base_url=SITE).status_code == 400
    assert client.get(link("10", "20", b"fake"), base_url=SITE).status_code == 403
    assert client.get("/logs/10-21-abc", base_url=SITE).status_code == 404
    assert client.get("/logs/10-99-abc", base_url=SITE).status_code == 404
    assert client.get("/logs/1x-20-abc", base_url=SITE).status_code == 404


def test_log_on_the_history_site_uses_its_own_bot(client, web, monkeypatch):
    discord = wire(monkeypatch, web, {})
    assert client.get("/logs/10-20-abc", base_url=HISTORY).status_code == 404
    assert [call[2]["headers"] for call in discord.calls] == [
        {"Authorization": "Bot mysti"}
    ]


def test_profile_needs_login(client):
    assert client.get("/profile", base_url=SITE).headers["Location"] == "/auth"
    assert client.get("/api/profile/data", base_url=SITE).status_code == 401
    assert client.get("/api/profile/1/state", base_url=SITE).status_code == 401


def test_profile_login_keeps_the_user_in_the_session(client, web, monkeypatch):
    monkeypatch.setattr(
        web.profile.requests,
        "post",
        lambda url, **options: Answer(200, {"access_token": "tok"}),
    )
    monkeypatch.setattr(
        web.profile.requests,
        "get",
        lambda url, **options: Answer(
            200, {"id": 5, "username": "ian", "avatar": "abc"}
        ),
    )
    answer = client.get("/profile?code=x", base_url=SITE)
    assert answer.headers["Location"] == "/profile"
    with client.session_transaction(base_url=SITE) as session:
        assert session["discord_token"] == "tok" and session["user_id"] == "5"
        assert session["user"]["avatar"].endswith("/avatars/5/abc.png?size=128")
    page = client.get("/profile/123", base_url=SITE)
    assert b'"gid": "123"' in page.data and b'"price": "4.99"' in page.data


def test_profile_data_lists_shared_servers_with_events(client, web, monkeypatch):
    mine = [
        {"id": "1", "name": "beta", "icon": None},
        {"id": "2", "name": "Alpha", "icon": "i"},
        {"id": "3", "name": "no events"},
        {"id": "4", "name": "bot not there"},
    ]
    wire(
        monkeypatch,
        web,
        {
            "/users/@me/guilds": lambda options: Answer(
                200,
                (
                    mine
                    if options["headers"]["Authorization"].startswith("Bearer")
                    else [{"id": "1"}, {"id": "2"}, {"id": "3"}]
                ),
            )
        },
    )
    monkeypatch.setattr(web.profile, "check_events_enabled", lambda gid: gid != "3")
    log_in(client, discord_token="tok", user_id="5")
    body = client.get("/api/profile/data", base_url=SITE).get_json()
    assert body == {
        "guilds": [
            {"id": "2", "name": "Alpha", "icon": "i"},
            {"id": "1", "name": "beta", "icon": None},
        ]
    }


def guarded(client, web, monkeypatch, enabled=True):
    wire(
        monkeypatch, web, {"/users/@me/guilds": Answer(200, [{"id": "1", "name": "g"}])}
    )
    monkeypatch.setattr(web.profile, "check_events_enabled", lambda gid: enabled)
    monkeypatch.setattr(web.profile, "is_elite_active", lambda uid, gid: True)
    log_in(client, discord_token="tok", user_id="5")


def test_dispatch_and_claim(client, web, monkeypatch):
    guarded(client, web, monkeypatch)
    sent = []
    monkeypatch.setattr(
        web.expeditions,
        "dispatch",
        lambda *args: sent.append(args)
        or ((True, None) if args[3] == 4 else (None, "No.")),
    )
    monkeypatch.setattr(
        web.expeditions,
        "claim",
        lambda uid, gid, run: {"mora": 9} if run == 3 else None,
    )
    post = lambda path, body: client.post(path, json=body, base_url=SITE)
    assert post(
        "/api/profile/1/dispatch", {"character": "Fischl", "hours": 4}
    ).get_json() == {"ok": True}
    assert sent[0] == ("5", "1", "Fischl", 4, True)
    bad = post("/api/profile/1/dispatch", {"character": "Fischl", "hours": "abc"})
    assert (bad.status_code, bad.get_json()) == (400, {"error": "No."})
    assert sent[1][3] == 0
    assert post("/api/profile/1/claim", {"id": 3}).get_json() == {"mora": 9}
    assert post("/api/profile/1/claim", {"id": "abc"}).status_code == 400
    assert post("/api/profile/2/claim", {"id": 3}).status_code == 404


def test_a_discord_outage_is_not_kept_as_no_servers(client, web, monkeypatch):
    answers = [Answer(503, {}), Answer(200, [{"id": "1", "name": "g"}])]
    wire(monkeypatch, web, {"/users/@me/guilds": lambda options: answers.pop(0)})
    log_in(client, discord_token="tok", user_id="5")
    with pytest.raises(RuntimeError):
        web.profile.cached("x", 1, lambda: (_ for _ in ()).throw(RuntimeError("down")))
    web.main.app.config["PROPAGATE_EXCEPTIONS"] = False
    try:
        assert (
            client.post("/api/profile/1/claim", json={}, base_url=SITE).status_code
            == 500
        )
    finally:
        web.main.app.config["PROPAGATE_EXCEPTIONS"] = None
    assert "ug:5" not in web.profile.cache


def test_guard_refuses_a_server_without_events(client, web, monkeypatch):
    guarded(client, web, monkeypatch, enabled=False)
    answer = client.post("/api/profile/1/claim", json={"id": 3}, base_url=SITE)
    assert answer.status_code == 400
    assert answer.get_json() == {"error": "Events are not enabled in this realm."}


def test_cache_keeps_a_value_for_its_time_and_drops_old_ones(web, monkeypatch):
    cache, now = web.profile.cache, [1000.0]
    cache.clear()
    monkeypatch.setattr(web.profile.time, "time", lambda: now[0])
    monkeypatch.setattr(web.profile, "CACHE_LIMIT", 2)
    assert web.profile.cached("a", 10, lambda: 1) == 1
    assert web.profile.cached("a", 10, lambda: 2) == 1
    now[0] = 1011.0
    assert web.profile.cached("a", 10, lambda: 3) == 3
    web.profile.cached("b", 100, lambda: 4)
    now[0] = 1030.0
    web.profile.cached("c", 10, lambda: 5)
    assert set(cache) == {"b", "c"}


def test_payment_success_page(client, web):
    assert client.get("/payment/success?guild_id=1", base_url=SITE).headers[
        "Location"
    ] == ("/login")
    log_in(client, discord_token="tok", user_id="5")
    page = client.get("/payment/success?guild_id=123", base_url=SITE)
    assert b'href="/profile/123"' in page.data
    assert b"window.location.href = '/profile/123';" in page.data
    assert client.get("/payment/success", base_url=SITE).status_code == 400
    bad = client.get("/payment/success?guild_id=<script>", base_url=SITE)
    assert bad.status_code == 400 and b"<script>" not in bad.data
    assert (
        client.get("/payment/success?guild_id=１２", base_url=SITE).status_code == 400
    )


def paid(web, monkeypatch, used=False, checked=True, real=True):
    """Stands in for the database and PayPal; gives the list of activations made."""
    done = []
    monkeypatch.setattr(
        web.profile,
        "activate_elite_subscription",
        lambda *args: done.append(args) or (True, "ok"),
    )
    monkeypatch.setattr(web.profile, "order_spent", lambda *args: used)
    monkeypatch.setattr(web.paypal, "can_check_orders", lambda: checked)
    monkeypatch.setattr(web.paypal, "order_paid_for", lambda *args: real)
    monkeypatch.setattr(web.paypal, "notification_is_real", lambda *args: real)
    return done


BODY = {"user_id": "5", "guild_id": "1", "order_id": "o"}


def test_payment_activate(client, web, monkeypatch):
    done = paid(web, monkeypatch)
    assert client.post("/payment/activate", json=BODY, base_url=SITE).status_code == 401
    log_in(client, discord_token="tok", user_id="5")
    answer = client.post("/payment/activate", json=BODY, base_url=SITE)
    assert answer.get_json() == {"success": True, "message": "ok"}
    assert done == [(5, 1, "o")]
    other = client.post(
        "/payment/activate", json={**BODY, "user_id": "6"}, base_url=SITE
    )
    assert other.status_code == 403 and len(done) == 1
    assert other.get_json() == {
        "error": "User ID mismatch",
        "details": "Request: 6, Session: 5",
    }
    assert client.post("/payment/activate", data="x", base_url=SITE).status_code == 500


@pytest.mark.parametrize(
    "stub, body, error",
    [
        ({"used": True}, BODY, "This order has already been used."),
        ({"real": False}, BODY, "Payment could not be verified."),
        ({}, {**BODY, "order_id": ""}, "Missing order"),
        ({}, {**BODY, "order_id": 7}, "Missing order"),
        ({}, {**BODY, "order_id": "../x?y=1"}, "Missing order"),
    ],
)
def test_payment_activate_refuses(client, web, monkeypatch, stub, body, error):
    done = paid(web, monkeypatch, **stub)
    log_in(client, discord_token="tok", user_id="5")
    answer = client.post("/payment/activate", json=body, base_url=SITE)
    assert (answer.status_code, answer.get_json()) == (400, {"error": error})
    assert done == []


def test_payment_activate_without_the_paypal_secret_skips_the_lookup(
    client, web, monkeypatch
):
    done = paid(web, monkeypatch, checked=False, real=False)
    log_in(client, discord_token="tok", user_id="5")
    assert client.post("/payment/activate", json=BODY, base_url=SITE).status_code == 200
    assert done == [(5, 1, "o")]


def test_manual_activation_needs_the_configured_token(client, web, monkeypatch):
    done = paid(web, monkeypatch)
    send = lambda token: client.post(
        "/payment/manual-activate", json={**BODY, "support_token": token}, base_url=SITE
    )
    for token in ("support_manual_activation_2024", "", None, "é"):
        assert send(token).status_code == 403
    monkeypatch.setattr(web.profile, "SUPPORT_TOKEN", "s3cret")
    assert send("wrong").status_code == 403
    assert send("s3cret").get_json() == {
        "success": True,
        "message": "Manually activated subscription for order o",
    }
    assert done == [(5, 1, "o")]


def test_webhook_activates_completed_payments_only(client, web, monkeypatch):
    done = paid(web, monkeypatch)
    send = lambda form: client.post("/payment/webhook", data=form, base_url=SITE)
    assert (
        send({"payment_status": "Pending", "custom": "5-1", "txn_id": "t"}).data
        == b"OK"
    )
    assert (
        send({"payment_status": "Completed", "custom": "bad", "txn_id": "t"}).data
        == b"OK"
    )
    assert send({"payment_status": "Completed", "txn_id": "t"}).data == b"OK"
    assert send({"payment_status": "Completed", "custom": "5-1"}).data == b"OK"
    assert done == []
    assert (
        send({"payment_status": "Completed", "custom": "5-1", "txn_id": "t"}).data
        == b"OK"
    )
    assert done == [(5, 1, "t")]


@pytest.mark.parametrize("stub", [{"real": False}, {"used": True}])
def test_webhook_ignores_a_notification_paypal_does_not_confirm(
    client, web, monkeypatch, stub
):
    done = paid(web, monkeypatch, **stub)
    form = {"payment_status": "Completed", "custom": "5-1", "txn_id": "t"}
    assert client.post("/payment/webhook", data=form, base_url=SITE).data == b"OK"
    assert done == []


def test_paypal_confirms_a_notification(web, monkeypatch):
    sent = []

    class PayPal:
        def post(self, url, **options):
            sent.append((url, options["data"]))
            return types.SimpleNamespace(status_code=200, text=self.text)

    paypal = PayPal()
    monkeypatch.setattr(web.paypal, "requests_session", paypal)
    form = {"mc_currency": "USD", "mc_gross": "4.99", "receiver_email": "Me@x.test"}
    monkeypatch.setattr(web.paypal, "RECEIVER", "me@x.test")
    paypal.text = "VERIFIED\n"
    assert web.paypal.notification_is_real(b"a=1", form) is True
    assert sent[0] == (
        "https://ipnpb.paypal.com/cgi-bin/webscr",
        b"cmd=_notify-validate&a=1",
    )
    assert (
        web.paypal.notification_is_real(b"a=1", {**form, "mc_gross": "0.01"}) is False
    )
    assert (
        web.paypal.notification_is_real(b"a=1", {**form, "mc_currency": "JPY"}) is False
    )
    assert web.paypal.notification_is_real(b"a=1", {}) is False
    assert (
        web.paypal.notification_is_real(
            b"a=1", {**form, "receiver_email": "you@x.test"}
        )
        is False
    )
    monkeypatch.setattr(web.paypal, "RECEIVER", "")
    assert (
        web.paypal.notification_is_real(b"a=1", {**form, "receiver_email": ""}) is False
    )
    monkeypatch.setattr(web.paypal, "RECEIVER", "me@x.test")
    paypal.text = "INVALID"
    assert web.paypal.notification_is_real(b"a=1", form) is False


def test_paypal_order_must_be_this_members_completed_full_payment(web, monkeypatch):
    good = {
        "status": "COMPLETED",
        "purchase_units": [
            {"custom_id": "5-1", "amount": {"currency_code": "USD", "value": "4.99"}}
        ],
    }
    found = [good]
    monkeypatch.setattr(web.paypal, "order", lambda order_id: found[0])
    assert web.paypal.order_paid_for("o", 5, 1, 1000) is True
    assert web.paypal.order_paid_for("o", 6, 1, 1000) is False
    assert web.paypal.order_paid_for("o", 5, 2, 1000) is False
    for change in (
        {"status": "APPROVED"},
        {"purchase_units": []},
        {
            "purchase_units": [
                {"custom_id": "5-1", "amount": {"currency_code": "USD", "value": "1"}}
            ]
        },
        {
            "purchase_units": [
                {
                    "custom_id": "5-1",
                    "amount": {"currency_code": "EUR", "value": "4.99"},
                }
            ]
        },
    ):
        found[0] = {**good, **change}
        assert web.paypal.order_paid_for("o", 5, 1, 1000) is False
    found[0] = {**good, "create_time": "1970-01-01T00:10:00Z"}
    assert web.paypal.order_paid_for("o", 5, 1, 1000) is False
    assert web.paypal.order_paid_for("o", 5, 1, 600) is True
    found[0] = None
    assert web.paypal.order_paid_for("o", 5, 1, 1000) is False


def test_paypal_order_lookup(web, monkeypatch):
    calls = []

    class PayPal:
        def post(self, url, **options):
            calls.append((url, options["auth"]))
            return Answer(200, {"access_token": "t"})

        def get(self, url, **options):
            calls.append((url, options["headers"]))
            return Answer(200, {"id": "o"}) if url.endswith("/o") else Answer(404, {})

    monkeypatch.setattr(web.paypal, "requests_session", PayPal())
    monkeypatch.setattr(web.paypal, "CLIENT_SECRET", "sec")
    assert web.paypal.can_check_orders() is True
    assert web.paypal.order("o") == {"id": "o"}
    assert calls == [
        ("https://api-m.paypal.com/v1/oauth2/token", ("pp", "sec")),
        (
            "https://api-m.paypal.com/v2/checkout/orders/o",
            {"Authorization": "Bearer t"},
        ),
    ]
    assert web.paypal.order("x") is None


def test_half_finished_login_leaves_no_session(client, web, monkeypatch):
    monkeypatch.setattr(
        web.profile.requests,
        "post",
        lambda url, **o: Answer(200, {"access_token": "tok"}),
    )
    monkeypatch.setattr(
        web.profile.requests, "get", lambda url, **o: Answer(401, {"message": "401"})
    )
    web.main.app.config["PROPAGATE_EXCEPTIONS"] = False
    try:
        assert client.get("/profile?code=x", base_url=SITE).status_code == 500
    finally:
        web.main.app.config["PROPAGATE_EXCEPTIONS"] = None
    with client.session_transaction(base_url=SITE) as session:
        assert not session


def test_order_spent(web, monkeypatch):
    monkeypatch.setattr(web.minigames.time, "time", lambda: 1000.0)
    for rows, used in (([(1,)], True), ([], False)):
        conn = Connection(rows)
        monkeypatch.setattr(web.minigames, "get_db_connection", lambda: conn)
        assert web.minigames.order_spent("o", "5", "1") is used
        assert conn.closed and conn.kept.ran[0][1] == ("o", 5, 1, 1000.0)


def test_an_order_serves_its_buyer_for_one_season_only(web, monkeypatch):
    """Runs the real statements on Postgres; needs TEST_DATABASE_URL."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    import psycopg2

    from commands.Events.helperFunctions import SCHEMA

    with psycopg2.connect(url) as conn, conn.cursor() as cursor:
        cursor.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        cursor.execute(SCHEMA)
    monkeypatch.setattr(
        web.minigames, "get_db_connection", lambda: psycopg2.connect(url)
    )
    wire(monkeypatch, web, {"/users/@me/channels": Answer(403, {})})
    spent, activate = (
        web.minigames.order_spent,
        web.minigames.activate_elite_subscription,
    )
    refused = (False, "This order has already been used.")
    assert not spent("o", 5, 1)
    assert activate(5, 1, "o")[0] is True and activate(5, 1, "o")[0] is True
    assert not spent("o", 5, 1) and not spent("p", 6, 1)
    assert spent("o", 6, 1) and spent("o", 5, 2)
    assert activate(6, 1, "o") == refused and activate(5, 2, "o") == refused
    assert not web.minigames.is_elite_active(6, 1)
    end = web.minigames.get_current_season()["end_ts"]
    monkeypatch.setattr(web.minigames.time, "time", lambda: end + 1)
    assert spent("o", 5, 1) and activate(5, 1, "o") == refused
    assert activate(5, 1)[0] is True
    with psycopg2.connect(url) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT * FROM minigame_elite_orders")
        assert cursor.fetchall() == [("o", 5, 1, end)]
        cursor.execute("UPDATE minigame_elite SET order_id = 'old' WHERE user_id = 5")
        cursor.execute(SCHEMA)
        cursor.execute(
            "SELECT user_id FROM minigame_elite_orders WHERE order_id = 'old'"
        )
        assert cursor.fetchall() == [(5,)]


class Cursor:
    def __init__(self, rows):
        self.rows, self.ran = rows, []

    def __enter__(self):
        return self

    def __exit__(self, *error):
        return False

    def execute(self, sql, values=None):
        self.ran.append((sql, values))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows):
        self.kept, self.committed, self.closed = Cursor(rows), False, False

    def cursor(self):
        return self.kept

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_elite_is_active_until_it_runs_out(web, monkeypatch):
    now = web.minigames.time.time()
    for rows, active in (([(now + 60,)], True), ([(now - 60,)], False), ([], False)):
        conn = Connection(rows)
        monkeypatch.setattr(web.minigames, "get_db_connection", lambda: conn)
        assert web.minigames.is_elite_active("5", "1") is active
        assert conn.closed and conn.kept.ran[0][1] == (5, 1)
    assert web.minigames.is_elite_active("x", "1") is False


def test_events_enabled_matches_channels_and_threads(web, monkeypatch):
    conn = Connection([(30,), (40,)])
    monkeypatch.setattr(web.minigames, "get_db_connection", lambda: conn)
    web.minigames.enabled_channels.update(at=0.0, ids=set())
    web.minigames.guild_channels.clear()
    discord = wire(
        monkeypatch,
        web,
        {
            "/guilds/1/channels": Answer(200, [{"id": "10"}]),
            "/guilds/1/threads/active": Answer(200, {"threads": [{"id": "40"}]}),
            "/guilds/2/channels": Answer(200, [{"id": "11"}]),
            "/guilds/3/channels": Answer(403, {}),
        },
    )
    assert web.minigames.check_events_enabled(1) is True
    assert web.minigames.check_events_enabled(2) is False
    assert web.minigames.check_events_enabled(3) is False
    calls = len(discord.calls)
    assert web.minigames.check_events_enabled("1") is True
    assert len(discord.calls) == calls and len(conn.kept.ran) == 1


def test_activating_elite_saves_and_dms(web, monkeypatch):
    conn = Connection([(1,)])
    monkeypatch.setattr(web.minigames, "get_db_connection", lambda: conn)
    discord = wire(
        monkeypatch,
        web,
        {
            "/guilds/1": Answer(200, {"name": "Realm"}),
            "/users/@me/channels": Answer(200, {"id": "77"}),
            "/channels/77/messages": Answer(200, {}),
        },
    )
    end = web.minigames.get_current_season()["end_ts"]
    assert web.minigames.activate_elite_subscription(5, 1, "order") == (
        True,
        "Elite subscription activated successfully",
    )
    assert conn.committed and conn.closed
    assert conn.kept.ran[0][1][:4] == ("order", 5, 1, end)
    assert conn.kept.ran[1][1] == (5, 1, "Realm", end, "order")
    assert len(conn.kept.ran) == 2
    embed = discord.calls[-1][2]["json"]["embed"]
    assert (
        "**Realm**" in embed["description"]
        and f"<t:{int(end)}:R>" in embed["description"]
    )
    assert embed["footer"] == {"text": "Order ID: order"} and embed["color"] == 0xFA0ADD


def test_activating_elite_survives_a_closed_dm_and_reports_a_database_error(
    web, monkeypatch
):
    conn = Connection([])
    monkeypatch.setattr(web.minigames, "get_db_connection", lambda: conn)
    wire(monkeypatch, web, {"/users/@me/channels": Answer(403, {})})
    assert web.minigames.activate_elite_subscription(5, 1)[0] is True
    assert conn.kept.ran[0][1][2:] == (
        "Server 1",
        web.minigames.get_current_season()["end_ts"],
        "",
    )
    assert len(conn.kept.ran) == 1

    def broken():
        raise RuntimeError("down")

    monkeypatch.setattr(web.minigames, "get_db_connection", broken)
    assert web.minigames.activate_elite_subscription(5, 1) == (
        False,
        "Error activating subscription: down",
    )
