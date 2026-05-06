"""
WhatsApp Template Registry
===========================
Maps internal template IDs to WhatsApp provider template IDs.
The provider manages the actual template content; we only pass the ID + variables.

Usage:
    from channels.whatsapp.templates import WA_TEMPLATES
    wa_template_id = WA_TEMPLATES.get("order.create.erw_angles")
"""

WA_TEMPLATES = {
    "order.create.erw_angles": {
        "provider_template_id": "dispatch_plan_created",
        "has_attachment": False,
        "attachment_payload_keys": []
    },
    "order.create.tmt": {
        "provider_template_id": "dispatch_plan_created",
        "has_attachment": False,
        "attachment_payload_keys": []
    },
    "order.create.fmcg": {
        "provider_template_id": "dispatch_plan_created_fmcg",
        "has_attachment": False,
        "attachment_payload_keys": []
    },
    "purchase_order.create": {
        "provider_template_id": "po_created",
        "has_attachment": False,
        "attachment_payload_keys": []
    },
    "invoice.generated": {
        "provider_template_id": "invoice_pdf_template",
        "has_attachment": True,
        "attachment_payload_keys": ["invoice_s3_url"]
    }
}
