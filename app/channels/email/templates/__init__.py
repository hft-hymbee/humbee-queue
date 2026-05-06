"""
Email Template Registry
=======================
Maps internal template IDs to HTML file paths and configures attachment handling.
"""

EMAIL_TEMPLATES = {
    "order.create.erw_angles": {
        "html_path": "channels/email/templates/dispatch_plan_created.html",
        "has_attachment": False,
        "attachment_payload_keys": []
    },
    "order.create.tmt": {
        "html_path": "channels/email/templates/dispatch_plan_created.html",
        "has_attachment": False,
        "attachment_payload_keys": []
    },
    "order.create.fmcg": {
        "html_path": "channels/email/templates/dispatch_plan_created_without_order_booking.html",
        "has_attachment": False,
        "attachment_payload_keys": []
    },
    "purchase_order.create": {
        "html_path": "channels/email/templates/po_created_mail.html",
        "has_attachment": False,
        "attachment_payload_keys": []
    },
    "invoice.generated": {
        "html_path": "channels/email/templates/invoice_mail.html",
        "has_attachment": True,
        "attachment_payload_keys": ["invoice_s3_url", "eway_bill_s3_url"]
    }
}
