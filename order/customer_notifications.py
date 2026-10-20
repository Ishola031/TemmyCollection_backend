import logging
from django.conf import settings
from django.utils.html import escape
from newsletter.brevo import brevo_request

logger = logging.getLogger(__name__)


def send_customer_order_email( customer, subject, title, message, order=None, action_url="",):
    """
    Send a transactional order email directly to a customer.
    This does not use newsletter lists or campaigns.
    """
    if not customer or not customer.email:
        logger.warning("Customer email skipped: no customer email available.")
        return False

    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "")
    sender_name = getattr(
        settings,
        "BREVO_SENDER_NAME",
        "TemmyCollection",
    )
    frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")

    if not sender_email:
        logger.error("BREVO_SENDER_EMAIL is not configured.")
        return False

    safe_name = escape(
        getattr(customer, "first_name", "") or "Customer"
    )
    safe_title = escape(title)
    safe_message = escape(message)

    order_section = ""

    if order:
        order_number = escape(str(order.order_number))
        order_total = escape(
            f"{order.payment.currency} {order.total_price}"
            if order.payment_id
            else str(order.total_price)
        )

        order_section = f"""
            <div style="margin:24px 0;padding:18px;background:#f7f7f7;
                        border-radius:8px;text-align:left;">
                <p><strong>Order number:</strong> {order_number}</p>
                <p><strong>Order total:</strong> {order_total}</p>
                <p><strong>Order status:</strong> {escape(order.status)}</p>
            </div>
        """

    button_html = ""

    if action_url:
        if action_url.startswith("/"):
            action_url = f"{frontend_url}{action_url}"

        if action_url.startswith(("https://", "http://")):
            button_html = f"""
                <p style="text-align:center;margin:28px 0;">
                    <a href="{escape(action_url, quote=True)}"
                       style="display:inline-block;background:#171717;
                              color:#ffffff;padding:14px 26px;
                              border-radius:6px;text-decoration:none;
                              font-weight:bold;">
                        View Order
                    </a>
                </p>
            """

    html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{safe_title}</title>
        </head>
        <body style="margin:0;background:#f5f5f5;
                     font-family:Arial,Helvetica,sans-serif;color:#222;">
            <div style="max-width:600px;margin:30px auto;background:#fff;
                        border-radius:12px;overflow:hidden;">
                <div style="background:#171717;color:#fff;text-align:center;
                            padding:28px 20px;">
                    <h1 style="margin:0;">TemmyCollection</h1>
                    <p style="color:#ddd;">Style that speaks for you.</p>
                </div>

                <div style="padding:30px 25px;">
                    <p>Hello {safe_name},</p>
                    <h2>{safe_title}</h2>
                    <p style="font-size:15px;line-height:1.8;">
                        {safe_message}
                    </p>

                    {order_section}
                    {button_html}

                    <p style="font-size:13px;color:#777;line-height:1.7;">
                        This is a transactional email about your
                        TemmyCollection order.
                    </p>
                </div>

                <div style="background:#f8f8f8;text-align:center;
                            padding:18px;font-size:12px;color:#777;">
                    &copy; TemmyCollection. All rights reserved.
                </div>
            </div>
        </body>
        </html>
    """

    try:
        brevo_request(
            "POST",
            "/smtp/email",
            data={
                "sender": {
                    "name": sender_name,
                    "email": sender_email,
                },
                "to": [{"email": customer.email}],
                "subject": subject,
                "htmlContent": html_content,
            },
        )
        return True

    except Exception:
        logger.exception(
            "Failed to send order email to %s",
            customer.email,
        )
        return False
