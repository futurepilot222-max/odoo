# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class AccessFieldRule(models.Model):
    """Field-level read / write restriction per role.

    Two enforcement layers:
      1. The linked res.groups is added to the underlying ir.model.fields
         ``groups`` setting when the rule marks the field as ``invisible``.
         Users outside the role then never see the field in any view.
      2. The ``readonly`` flag is enforced at runtime via a write() guard in
         ``base_model.py``. Without the role's group, writes to the field are
         rejected with AccessError.
    """

    _name = "access.field.rule"
    _description = "Field-Level Access Rule"
    _rec_name = "field_id"

    role_id = fields.Many2one(
        "access.role", required=True, ondelete="cascade", index=True,
    )
    model_id = fields.Many2one(
        "ir.model", required=True, ondelete="cascade", string="Model",
    )
    field_id = fields.Many2one(
        "ir.model.fields", required=True, ondelete="cascade", string="Field",
        domain="[('model_id', '=', model_id)]",
    )
    model_name = fields.Char(related="model_id.model", store=True)
    field_name = fields.Char(related="field_id.name", store=True)

    readonly = fields.Boolean(
        help="If set, users WITHOUT the role's group cannot write to this field.",
    )
    invisible = fields.Boolean(
        help="If set, the field is hidden from any view for users outside the role.",
    )

    _sql_constraints = [
        ("uniq_role_field", "unique(role_id, field_id)",
         "A role cannot define the same field rule twice."),
    ]

    def _sync_field_groups(self):
        """Add / remove the role's group on the ir.model.fields.groups m2m."""
        for rec in self:
            if not rec.role_id.group_id:
                rec.role_id._ensure_group()
            grp = rec.role_id.group_id
            field = rec.field_id.sudo()
            if rec.invisible:
                # field belongs ONLY to the role - users outside it cannot see it.
                if grp not in field.groups:
                    field.write({"groups": [(4, grp.id)]})
            else:
                if grp in field.groups:
                    field.write({"groups": [(3, grp.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules._sync_field_groups()
        return rules

    def write(self, vals):
        res = super().write(vals)
        if {"role_id", "field_id", "invisible"} & set(vals.keys()):
            self._sync_field_groups()
        return res

    def unlink(self):
        # detach from field.groups before deletion
        for rec in self:
            if rec.role_id.group_id and rec.field_id:
                rec.field_id.sudo().write({
                    "groups": [(3, rec.role_id.group_id.id)],
                })
        return super().unlink()

    @api.model
    def _check_field_writable(self, model_name, field_name, user):
        """Return True iff ``user`` may write ``field_name`` on ``model_name``.

        A field is writable when no rule marks it as readonly, OR when the user
        belongs to at least one role that grants writability (i.e. carries the
        role's res.groups).
        """
        rules = self.sudo().search([
            ("model_name", "=", model_name),
            ("field_name", "=", field_name),
            ("readonly", "=", True),
        ])
        if not rules:
            return True
        # if user is in any of the role groups granting access, allow
        user_groups = user.all_group_ids
        for rule in rules:
            if rule.role_id.group_id and rule.role_id.group_id in user_groups:
                return True
        return False
