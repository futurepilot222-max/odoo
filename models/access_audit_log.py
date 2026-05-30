# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccessAuditLog(models.Model):
    _name = "access.audit.log"
    _description = "Access Rights Audit Log"
    _order = "create_date desc, id desc"
    _rec_name = "model_name"

    user_id = fields.Many2one(
        "res.users", required=True, default=lambda s: s.env.uid,
        ondelete="restrict", index=True, string="Changed By",
    )
    model_name = fields.Char(string="Model", index=True)
    record_id = fields.Integer(string="Record ID", index=True)
    record_name = fields.Char(string="Record")
    field_name = fields.Char(string="Field")
    old_value = fields.Text()
    new_value = fields.Text()
    action = fields.Selection(
        [
            ("create", "Created"),
            ("write", "Updated"),
            ("unlink", "Deleted"),
            ("assign", "Assigned"),
            ("revoke", "Revoked"),
        ],
        required=True, default="write",
    )
    notes = fields.Char()

    @api.model
    def log(self, action, model_name, record_id, record_name=None,
            field_name=None, old_value=None, new_value=None, notes=None):
        return self.sudo().create({
            "user_id": self.env.uid,
            "action": action,
            "model_name": model_name,
            "record_id": record_id or 0,
            "record_name": record_name or "",
            "field_name": field_name or "",
            "old_value": "" if old_value is None else str(old_value),
            "new_value": "" if new_value is None else str(new_value),
            "notes": notes,
        })
