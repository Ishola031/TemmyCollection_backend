import requests
from django.conf import settings
from urllib.parse import quote
from html import escape



BREVO_BASE_URL = "https://api.brevo.com/v3"




# 
def brevo_headers():
    api_key = getattr(settings, "BREVO_API_KEY", None)

    if not api_key:
        raise RuntimeError("BREVO_API_KEY is not configured.")

    return {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

# 
def brevo_request(method, endpoint, data=None, params=None):
    response = requests.request(
        method=method,
        url=f"{BREVO_BASE_URL}{endpoint}",
        headers=brevo_headers(),
        json=data,
        params=params,
        timeout=30,
    )

    if not response.ok:
        try:
            error_data = response.json()
        except ValueError:
            error_data = {}

        message = (
            error_data.get("message")
            or error_data.get("code")
            or response.text
            or "Brevo request failed."
        )

        raise RuntimeError(f"Brevo error ({response.status_code}): {message}")

    if response.status_code == 204:
        return {}

    try:
        return response.json()
    except ValueError:
        return {}

# 
def get_brevo_list_id():
    list_id = getattr(settings, "BREVO_LIST_ID", None)

    if not list_id:
        raise RuntimeError(
            "BREVO_LIST_ID is not configured."
        )

    return int(list_id)

# 
def create_brevo_contact(email, first_name="", last_name="", subscribed=False,):
    list_id = get_brevo_list_id()

    payload = {
        "email": email,
        "attributes": {
            "FIRSTNAME": first_name,
            "LASTNAME": last_name,
        },
        "listIds": [list_id] if subscribed else [],
        "updateEnabled": True,
    }

    if subscribed:
        payload["emailBlacklisted"] = False

    result = brevo_request(
        "POST",
        "/contacts",
        data=payload,
    )

    # Brevo may return an empty response for an existing contact.
    if not result or not result.get("id"):
        encoded_email = quote(email, safe="")
        result = brevo_request(
            "GET",
            f"/contacts/{encoded_email}",
        )

    return result

# 
def unsubscribe_brevo_contact(email):
    encoded_email = quote(email, safe="")

    return brevo_request(
        "PUT",
        f"/contacts/{encoded_email}",
        data={
            "emailBlacklisted": True,
            "unlinkListIds": [get_brevo_list_id()],
        },
    )


def get_brevo_templates():
    return brevo_request(
        "GET",
        "/smtp/templates",
        params={
            "templateStatus": True,
            "limit": 1000,
            "offset": 0,
            "sort": "desc",
        },
    )


def get_brevo_campaigns():
    return brevo_request(
        "GET",
        "/emailCampaigns",
        params={
            "limit": 100,
            "offset": 0,
            "sort": "desc",
        },
    )


def get_brevo_campaign(campaign_id):
    return brevo_request(
        "GET",
        f"/emailCampaigns/{campaign_id}",
    )


def create_brevo_campaign(name,subject,preview,html_content,sender_name,sender_email,list_ids=None,):
    if list_ids is None:
        list_ids = [get_brevo_list_id()]

    payload = {
        "name": name,
        "subject": subject,
        "previewText": preview or "",
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "recipients": {
            "listIds": list_ids,
        },
        "htmlContent": html_content,
        "type": "classic",
    }

    return brevo_request(
        "POST",
        "/emailCampaigns",
        data=payload,
    )


def send_brevo_campaign(campaign_id):
    return brevo_request(
        "POST",
        f"/emailCampaigns/{campaign_id}/sendNow",
    )


def send_brevo_test(email,subject,html_content,sender_name,sender_email):
    return brevo_request("POST", "/smtp/email",
        data={
            "sender": {
                "name": sender_name,
                "email": sender_email,
            },
            "to": [
                {"email": email}
            ],
            "subject": subject,
            "htmlContent": html_content,
        },
    )

# CONFIRM
def send_brevo_welcome_email(email, first_name="",):
    sender_email = getattr(settings, "BREVO_SENDER_EMAIL","",)
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "TemmyCollection",)
    store_url = getattr(settings, "FRONTEND_URL","",).rstrip("/")

    if not sender_email:
        raise RuntimeError("BREVO_SENDER_EMAIL is not configured.")

    if not store_url:
        raise RuntimeError(
            "FRONTEND_URL is not configured."
        )

    safe_name = escape(first_name.strip()) if first_name else ""
    greeting = (f"Hi {safe_name}," if safe_name else "Hello,")

    html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Welcome to TemmyCollection</title>
            </head>
            <body style="margin:0;padding:0;background:#f5f5f5;
                        font-family:Arial,Helvetica,sans-serif;color:#222222;">
                <div style="max-width:600px;margin:30px auto;background:#ffffff;
                            border-radius:12px;overflow:hidden;">
                    <div style="background:#171717;color:#ffffff;
                                text-align:center;padding:32px 20px;">
                        <h1 style="margin:0;font-size:28px;">
                            TemmyCollection
                        </h1>
                        <p style="margin:10px 0 0;color:#dddddd;">
                            Style that speaks for you.
                        </p>
                    </div>

                    <div style="padding:35px 28px;text-align:center;">
                        <h2 style="font-size:24px;margin:0 0 20px;">
                            Welcome to the family!
                        </h2>

                        <p style="font-size:16px;line-height:1.8;text-align:left;">
                            {greeting}
                        </p>

                        <p style="font-size:16px;line-height:1.8;text-align:left;">
                            Thank you for subscribing to TemmyCollection.
                            You'll receive updates about our latest arrivals,
                            new styles, special offers, and fashion inspiration.
                        </p>

                        <p style="font-size:16px;line-height:1.8;text-align:left;">
                            We're glad you're here. Keep an eye on your inbox
                            for what's new!
                        </p>

                        <a href="{escape(store_url, quote=True)}"
                        style="display:inline-block;margin:20px 0;
                                padding:15px 30px;background:#171717;
                                color:#ffffff;text-decoration:none;
                                border-radius:6px;font-weight:bold;">
                            Shop Now
                        </a>

                        <p style="font-size:13px;line-height:1.7;color:#777777;
                                margin-top:25px;">
                            You received this email because you subscribed
                            to TemmyCollection newsletter updates.
                        </p>
                    </div>

                    <div style="background:#f8f8f8;text-align:center;
                                padding:18px;font-size:12px;color:#777777;">
                        &copy; TemmyCollection. All rights reserved.
                    </div>
                </div>
            </body>
            </html>
    """

    return brevo_request(
        "POST",
        "/smtp/email",
        data={
            "sender": {
                "name": sender_name,
                "email": sender_email,
            },
            "to": [
                {"email": email}
            ],
            "subject": "Welcome to TemmyCollection!",
            "htmlContent": html_content,
        },
    )


def send_brevo_campaign_email(email, subject, html_content, preview_text=""):
    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "")
    sender_name = getattr(settings,"BREVO_SENDER_NAME","TemmyCollection",)

    if not sender_email:
        raise RuntimeError("BREVO_SENDER_EMAIL is not configured.")

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [{"email": email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    if preview_text:
        payload["headers"] = {
            "X-Mailin-custom": "newsletter-campaign"
        }

    return brevo_request(
        "POST",
        "/smtp/email",
        data=payload,
    )



