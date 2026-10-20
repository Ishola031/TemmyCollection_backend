import html
import re
import requests
from django.conf import settings
from django.utils import timezone




RESEND_API_URL = "https://api.resend.com/emails"


def safe_url(value):
    if not isinstance(value, str):
        return ""

    value = value.strip()

    if not re.match(r"^https?://", value, re.I):
        return ""

    return value


def escape_text(value):
    return html.escape(str(value or ""))


def get_recipient_name(recipient):
    subscriber = recipient.subscriber

    if subscriber and subscriber.user:
        user = subscriber.user
        name = getattr(user, "name", "")

        if not name:
            first_name = getattr(user, "first_name", "")
            last_name = getattr(user, "last_name", "")
            name = f"{first_name} {last_name}".strip()

        if name:
            return name

    return "there"


def render_blocks(blocks):
    rendered = []

    for block in blocks:
        block_type = block.get("type")

        if block_type == "heading":
            text = escape_text(block.get("text"))

            rendered.append(
                f"""
                <tr>
                  <td style="padding:16px 24px;">
                    <h1 style="
                      margin:0;
                      font-size:28px;
                      line-height:1.3;
                      color:#111827;
                    ">
                      {text}
                    </h1>
                  </td>
                </tr>
                """
            )

        elif block_type == "paragraph":
            text = escape_text(block.get("text"))
            text = text.replace("\n", "<br>")
            rendered.append(
                f"""
                <tr>
                  <td style="
                    padding:8px 24px;
                    color:#4b5563;
                    font-size:16px;
                    line-height:1.8;
                  ">
                    {text}
                  </td>
                </tr>
                """
            )

        elif block_type == "image":
            image_url = safe_url(block.get("image_url") or block.get("url"))

            if not image_url:
                continue

            alt = escape_text(block.get("alt", "Newsletter image"))
            link = safe_url(block.get("href"))
            image = f"""
                <img
                  src="{escape_text(image_url)}"
                  alt="{alt}"
                  width="552"
                  style="
                    display:block;
                    width:100%;
                    max-width:552px;
                    height:auto;
                    border:0;
                  "
                >
            """

            if link:
                image = (
                    f'<a href="{escape_text(link)}">'
                    f'{image}</a>'
                )

            rendered.append(
                f"""
                <tr>
                  <td style="padding:12px 24px;">
                    {image}
                  </td>
                </tr>
                """
            )

        elif block_type == "button":
            label = escape_text(block.get("text", "SHOP NOW"))
            url = safe_url(block.get("url"))

            if not url:
                continue

            background = block.get("background_color","#111827",)
            color = block.get("text_color","#ffffff",)

            if not re.fullmatch(r"#[0-9a-fA-F]{6}", background):
                background = "#111827"

            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                color = "#ffffff"

            rendered.append(
                f"""
                <tr>
                  <td align="center" style="padding:20px 24px;">
                    <a
                      href="{escape_text(url)}"
                      style="
                        display:inline-block;
                        background:{background};
                        color:{color};
                        padding:14px 28px;
                        border-radius:8px;
                        text-decoration:none;
                        font-weight:bold;
                        font-size:14px;
                      "
                    >
                      {label}
                    </a>
                  </td>
                </tr>
                """
            )

        elif block_type == "divider":
            rendered.append(
                """
                <tr>
                  <td style="padding:12px 24px;">
                    <hr style="
                      border:0;
                      border-top:1px solid #e5e7eb;
                    ">
                  </td>
                </tr>
                """
            )

        elif block_type == "spacer":
            height = block.get("height", 24)

            try:
                height = max(0, min(int(height), 200))
            except (TypeError, ValueError):
                height = 24

            rendered.append(
                f"""
                <tr>
                  <td height="{height}" style="
                    height:{height}px;
                    font-size:0;
                    line-height:0;
                  ">
                    &nbsp;
                  </td>
                </tr>
                """
            )

        elif block_type == "product":
            name = escape_text(block.get("name"))
            description = escape_text(block.get("description", ""))
            price = escape_text(block.get("price", ""))
            image_url = safe_url(block.get("image_url"))
            product_url = safe_url(block.get("url"))

            if not name:
                continue

            image_html = ""

            if image_url:
                image_html = f"""
                    <img
                      src="{escape_text(image_url)}"
                      alt="{name}"
                      width="220"
                      style="
                        display:block;
                        width:100%;
                        height:auto;
                        border:0;
                      "
                    >
                """

            product_link = ""

            if product_url:
                product_link = f"""
                    <p>
                      <a href="{escape_text(product_url)}">
                        View product
                      </a>
                    </p>
                """

            rendered.append(
                f"""
                <tr>
                  <td style="padding:12px 24px;">
                    <table
                      role="presentation"
                      width="100%"
                      cellspacing="0"
                      cellpadding="0"
                      border="0"
                    >
                      <tr>
                        <td>
                          {image_html}
                          <h3>{name}</h3>
                          <p>{description}</p>
                          <p>{price}</p>
                          {product_link}
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                """
            )

        elif block_type == "product_grid":
            products = block.get("products", [])

            if not isinstance(products, list):
                continue

            cells = []

            for product in products[:4]:
                if not isinstance(product, dict):
                    continue

                name = escape_text(product.get("name"))
                image_url = safe_url(product.get("image_url"))
                product_url = safe_url(product.get("url"))
                price = escape_text(product.get("price", ""))

                if not name:
                    continue

                image_html = ""

                if image_url:
                    image_html = f"""
                        <img
                          src="{escape_text(image_url)}"
                          alt="{name}"
                          width="220"
                          style="
                            display:block;
                            width:100%;
                            height:auto;
                          "
                        >
                    """

                if product_url:
                    name_html = f"""
                        <a href="{escape_text(product_url)}">
                          {name}
                        </a>
                    """
                else:
                    name_html = name

                cells.append(
                    f"""
                    <td
                      width="50%"
                      valign="top"
                      style="padding:8px;"
                    >
                      {image_html}
                      <p>{name_html}</p>
                      <p>{price}</p>
                    </td>
                    """
                )

            if cells:
                rendered.append(
                    f"""
                    <tr>
                      <td style="padding:12px 16px;">
                        <table
                          role="presentation"
                          width="100%"
                          cellspacing="0"
                          cellpadding="0"
                          border="0"
                        >
                          <tr>
                            {"".join(cells)}
                          </tr>
                        </table>
                      </td>
                    </tr>
                    """
                )

        elif block_type == "social_links":
            links = block.get("links", [])

            if not isinstance(links, list):
                continue

            items = []

            for item in links[:10]:
                if not isinstance(item, dict):
                    continue

                label = escape_text(item.get("label"))
                url = safe_url(item.get("url"))

                if not label or not url:
                    continue

                items.append(
                    f"""
                    <a
                      href="{escape_text(url)}"
                      style="margin:0 8px;"
                    >
                      {label}
                    </a>
                    """
                )

            if items:
                rendered.append(
                    f"""
                    <tr>
                      <td align="center" style="padding:20px;">
                        {"".join(items)}
                      </td>
                    </tr>
                    """
                )

    return "".join(rendered)


def render_newsletter_email(campaign, recipient):
    name = escape_text(get_recipient_name(recipient))
    content = render_blocks(campaign.blocks)

    # Replace this with a signed, recipient-specific
    # unsubscribe URL when implementing unsubscribe links.
    unsubscribe_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}"
        "/newsletter/unsubscribe"
    )

    preview = escape_text(campaign.preview_text)

    return f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1"
        >
        <title>{escape_text(campaign.subject)}</title>
      </head>

      <body style="
        margin:0;
        padding:0;
        background:#f3f4f6;
        font-family:Arial,Helvetica,sans-serif;
      ">

        <div style="
          display:none;
          max-height:0;
          overflow:hidden;
          opacity:0;
        ">
          {preview}
        </div>

        <table
          role="presentation"
          width="100%"
          cellspacing="0"
          cellpadding="0"
          border="0"
          style="background:#f3f4f6;"
        >
          <tr>
            <td align="center" style="padding:24px 8px;">

              <table
                role="presentation"
                width="600"
                cellspacing="0"
                cellpadding="0"
                border="0"
                style="
                  width:100%;
                  max-width:600px;
                  background:#ffffff;
                "
              >
                <tr>
                  <td style="
                    padding:24px;
                    text-align:center;
                    font-size:22px;
                    font-weight:bold;
                  ">
                    TEMMY COLLECTION
                  </td>
                </tr>

                <tr>
                  <td style="
                    padding:0 24px 16px;
                    color:#111827;
                    font-size:16px;
                  ">
                    Hello {name},
                  </td>
                </tr>

                {content}

                <tr>
                  <td style="
                    padding:24px;
                    text-align:center;
                    font-size:12px;
                    color:#6b7280;
                  ">
                    You received this email because you subscribed
                    to Temmy Collection newsletters.

                    <br><br>

                    <a href="{escape_text(unsubscribe_url)}">
                      Unsubscribe
                    </a>
                  </td>
                </tr>

              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


def send_email_via_resend(*,to_email,subject,html_content,idempotency_key,):
    api_key = settings.RESEND_API_KEY

    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured.")

    from_email = settings.NEWSLETTER_FROM_EMAIL
    from_name = settings.NEWSLETTER_FROM_NAME

    if not from_email:
        raise RuntimeError("NEWSLETTER_FROM_EMAIL is not configured.")

    response = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        },
        json={
            "from": f"{from_name} <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        },
        timeout=30,
    )

    response.raise_for_status()
    data = response.json()

    if not data.get("id"):
        raise RuntimeError(
            "The email provider did not return a message ID."
        )

    return data



