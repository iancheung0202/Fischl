"""Asks PayPal whether a payment for the Elite Track is real."""

from datetime import datetime

import config.settings as settings

from utils.request import requests_session

LIVE = getattr(settings, "PAYPAL_MODE", "live") == "live"
API = "https://api-m.paypal.com" if LIVE else "https://api-m.sandbox.paypal.com"
IPN = (
    "https://ipnpb.paypal.com/cgi-bin/webscr"
    if LIVE
    else "https://ipnpb.sandbox.paypal.com/cgi-bin/webscr"
)
CLIENT_SECRET = getattr(settings, "PAYPAL_CLIENT_SECRET", "")
RECEIVER = getattr(settings, "PAYPAL_RECEIVER_EMAIL", "").lower()
CURRENCY = "USD"
TIMEOUT = 15


def same_amount(value):
    """Says whether an amount PayPal reports is the Elite Track price."""
    try:
        return float(value) == float(settings.ELITE_TRACK_PRICE)
    except (TypeError, ValueError):
        return False


def can_check_orders():
    """Says whether the PayPal secret needed to look an order up is configured."""
    return bool(CLIENT_SECRET)


def order(order_id):
    """Gives an order as PayPal holds it, or None when PayPal does not know it."""
    token = requests_session.post(
        f"{API}/v1/oauth2/token",
        auth=(settings.PAYPAL_CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=TIMEOUT,
    )
    if token.status_code != 200:
        raise RuntimeError(f"PayPal login failed: HTTP {token.status_code}")
    answer = requests_session.get(
        f"{API}/v2/checkout/orders/{order_id}",
        headers={"Authorization": f"Bearer {token.json()['access_token']}"},
        timeout=TIMEOUT,
    )
    return answer.json() if answer.status_code == 200 else None


def made_since(found, since):
    """Says whether an order was made after a moment; yes when PayPal gives no date."""
    try:
        made = datetime.fromisoformat(found["create_time"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        return True
    return made.timestamp() >= since


def order_paid_for(order_id, user_id, guild_id, since):
    """Says whether an order is this member's completed Elite Track payment of this season."""
    found = order(order_id)
    units = (found or {}).get("purchase_units") or [{}]
    amount = units[0].get("amount") or {}
    return (
        bool(found)
        and found.get("status") == "COMPLETED"
        and units[0].get("custom_id") == f"{user_id}-{guild_id}"
        and amount.get("currency_code") == CURRENCY
        and same_amount(amount.get("value"))
        and made_since(found, since)
    )


def notification_is_real(body, form):
    """Says whether PayPal confirms a notification of the full price paid to the configured account."""
    answer = requests_session.post(
        IPN,
        data=b"cmd=_notify-validate&" + body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=TIMEOUT,
    )
    if answer.status_code != 200:
        raise RuntimeError(f"PayPal validation failed: HTTP {answer.status_code}")
    return (
        answer.text.strip() == "VERIFIED"
        and bool(RECEIVER)
        and form.get("receiver_email", "").lower() == RECEIVER
        and form.get("mc_currency") == CURRENCY
        and same_amount(form.get("mc_gross"))
    )
