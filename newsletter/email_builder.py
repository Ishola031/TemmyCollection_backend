from html import escape
from urllib.parse import urlparse


def safe_url(value):
    if not isinstance(value, str):
        return ""

    value = value.strip()
    parsed = urlparse(value)

    if parsed.scheme not in {"https", "http"}:
        return ""

    if not parsed.netloc:
        return ""

    return escape(value, quote=True)


def render_campaign_html(campaign):
    blocks = campaign.content_blocks or []
    output = []

    # Support the original campaign fields as a fallback.
    if not blocks:
        if campaign.hero_image:
            image_url = safe_url(campaign.hero_image)

            if image_url:
                output.append(
                    f'<img src="{image_url}" '
                    'alt="" style="width:100%;height:auto;">'
                )

        if campaign.heading:
            output.append(
                f"<h1>{escape(campaign.heading)}</h1>"
            )

        if campaign.body:
            output.append(
                f"<p>{escape(campaign.body).replace(chr(10), '<br>')}</p>"
            )

        if campaign.content_image:
            image_url = safe_url(campaign.content_image)

            if image_url:
                output.append(
                    f'<img src="{image_url}" '
                    'alt="" style="width:100%;height:auto;">'
                )

        if campaign.button_text and campaign.button_url:
            button_url = safe_url(campaign.button_url)

            if button_url:
                output.append(
                    f'<p><a href="{button_url}" '
                    'style="display:inline-block;padding:12px 24px;'
                    'background:#111;color:#fff;text-decoration:none;">'
                    f'{escape(campaign.button_text)}</a></p>'
                )

    else:
        for block in blocks:
            block_type = block.get("type")

            if block_type == "heading":
                text = escape(str(block.get("text", "")))
                level = block.get("level", 2)

                if level not in {1, 2, 3, 4, 5, 6}:
                    level = 2

                output.append(
                    f"<h{level}>{text}</h{level}>"
                )

            elif block_type == "paragraph":
                text = escape(str(block.get("text", "")))
                text = text.replace("\n", "<br>")

                output.append(f"<p>{text}</p>")

            elif block_type == "image":
                image_url = safe_url(block.get("url", ""))
                alt = escape(str(block.get("alt", "")), quote=True)

                if image_url:
                    output.append(
                        f'<img src="{image_url}" alt="{alt}" '
                        'style="max-width:100%;height:auto;">'
                    )

            elif block_type == "button":
                button_url = safe_url(block.get("url", ""))
                button_text = escape(
                    str(block.get("text", "Shop Now"))
                )

                if button_url:
                    output.append(
                        f'<p><a href="{button_url}" '
                        'style="display:inline-block;padding:12px 24px;'
                        'background:#111;color:#fff;'
                        'text-decoration:none;">'
                        f"{button_text}</a></p>"
                    )

            elif block_type == "divider":
                output.append("<hr>")

            elif block_type == "spacer":
                height = block.get("height", 20)

                if (
                    isinstance(height, int)
                    and 0 <= height <= 200
                ):
                    output.append(
                        f'<div style="height:{height}px;"></div>'
                    )

            elif block_type == "product":
                name = escape(str(block.get("name", "")))
                description = escape(
                    str(block.get("description", ""))
                )
                image_url = safe_url(block.get("image", ""))
                product_url = safe_url(block.get("url", ""))

                if image_url:
                    output.append(
                        f'<img src="{image_url}" alt="{name}" '
                        'style="max-width:100%;height:auto;">'
                    )

                output.append(f"<h3>{name}</h3>")

                if description:
                    output.append(f"<p>{description}</p>")

                if product_url:
                    output.append(
                        f'<p><a href="{product_url}">'
                        "View Product</a></p>"
                    )

            elif block_type == "product_grid":
                products = block.get("products", [])

                if isinstance(products, list):
                    for product in products[:20]:
                        if isinstance(product, dict):
                            name = escape(
                                str(product.get("name", ""))
                            )
                            url = safe_url(
                                product.get("url", "")
                            )
                            image = safe_url(
                                product.get("image", "")
                            )

                            if image:
                                output.append(
                                    f'<img src="{image}" '
                                    f'alt="{name}" '
                                    'style="max-width:100%;height:auto;">'
                                )

                            if url:
                                output.append(
                                    f'<p><a href="{url}">'
                                    f"{name}</a></p>"
                                )
                            else:
                                output.append(f"<p>{name}</p>")

            elif block_type == "social_links":
                links = block.get("links", [])

                if isinstance(links, list):
                    for item in links[:20]:
                        if not isinstance(item, dict):
                            continue

                        url = safe_url(item.get("url", ""))
                        label = escape(
                            str(item.get("label", "Social"))
                        )

                        if url:
                            output.append(
                                f'<a href="{url}">{label}</a> '
                            )

    content = "\n".join(output)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{escape(campaign.subject)}</title>
    </head>
    <body style="margin:0;padding:24px;font-family:Arial,sans-serif;">
        <div style="max-width:640px;margin:0 auto;">
            {content}
            <hr>
            <p style="font-size:12px;color:#666;">
                You are receiving this email because you subscribed
                to the TemmyCollection newsletter.
                {{ unsubscribe }}
            </p>
        </div>
    </body>
    </html>
    """

