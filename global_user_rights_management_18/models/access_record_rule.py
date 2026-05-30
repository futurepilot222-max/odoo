# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


RULE_TYPES = [
    ("own", "Own Records Only"),
    ("team", "Team Records"),
    ("department", "Department Records"),
    ("company", "Current Company"),
    ("assigned", "Assigned to User"),
    ("custom", "Custom Domain"),
    ("global", "Global (No Filter)"),
]


class AccessRecordRule(models.Model):
    """Record-level visibility rule per role.

    Translates a high-level ``rule_type`` into an ir.rule domain on a target
    model. Native ir.rule then enforces it on every read / write / unlink.
    """

    _name = "access.record.rule"
    _description = "Record-Level Access Rule"
    _rec_name = "display_name"

    role_id = fields.Many2one(
        "access.role", required=True, ondelete="cascade", index=True,
    )
    model_id = fields.Many2one(
        "ir.model", required=True, ondelete="cascade", string="Model",
    )
    model_name = fields.Char(related="model_id.model", store=True)
    rule_type = fields.Selection(RULE_TYPES, required=True, default="own")
    custom_domain = fields.Char(
        string="Custom Domain",
        help="Used only when ``rule_type`` is 'custom'. Must be a valid Python "
             "expression that evaluates to a list of tuples, e.g. "
             "[('user_id','=',user.id)].",
    )

    perm_read = fields.Boolean(default=True)
    perm_write = fields.Boolean(default=True)
    perm_create = fields.Boolean(default=True)
    perm_unlink = fields.Boolean(default=True, string="Delete")

    ir_rule_id = fields.Many2one("ir.rule", copy=False, ondelete="set null")
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        ("uniq_role_model", "unique(role_id, model_id)",
         "A role can have only one record rule per model."),
    ]

    @api.depends("role_id", "model_id", "rule_type")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s / %s / %s" % (
                rec.role_id.name or "?",
                rec.model_id.model or "?",
                dict(RULE_TYPES).get(rec.rule_type, rec.rule_type) or "?",
            )

    @api.constrains("rule_type", "custom_domain")
    def _check_custom_domain(self):
        for rec in self:
            if rec.rule_type == "custom":
                if not rec.custom_domain:
                    raise ValidationError(_(
                        "A custom domain is required when 'Custom Domain' is selected."
                    ))
                # naive validation: must start with [ and end with ]
                d = rec.custom_domain.strip()
                if not (d.startswith("[") and d.endswith("]")):
                    raise ValidationError(_(
                        "Custom domain must be a Python list of tuples."
                    ))

    def _build_domain(self):
        """Map ``rule_type`` to an ir.rule ``domain_force`` string."""
        self.ensure_one()
        model = self.env[self.model_id.model] if self.model_id.model in self.env else None

        def has_field(name):
            return bool(model and name in model._fields)

        if self.rule_type == "own":
            if has_field("create_uid"):
                return "[('create_uid', '=', user.id)]"
            if has_field("user_id"):
                return "[('user_id', '=', user.id)]"
            return "[(1, '=', 0)]"  # nothing
        if self.rule_type == "assigned":
            if has_field("user_id"):
                return "[('user_id', '=', user.id)]"
            if has_field("user_ids"):
                return "[('user_ids', 'in', [user.id])]"
            return "[(1, '=', 0)]"
        if self.rule_type == "team":
            if has_field("team_id"):
                return "['|', ('team_id.member_ids', 'in', [user.id]), ('team_id.user_id', '=', user.id)]"
            return "[(1, '=', 1)]"
        if self.rule_type == "department":
            if has_field("department_id"):
                return (
                    "[('department_id', 'in', user.employee_id.department_id.ids)]"
                )
            return "[(1, '=', 1)]"
        if self.rule_type == "company":
            if has_field("company_id"):
                return "[('company_id', 'in', company_ids)]"
            return "[(1, '=', 1)]"
        if self.rule_type == "global":
            return "[(1, '=', 1)]"
        if self.rule_type == "custom":
            return self.custom_domain or "[(1, '=', 1)]"
        return "[(1, '=', 1)]"

    def _sync_ir_rule(self):
        Rule = self.env["ir.rule"].sudo()
        for rec in self:
            if not rec.role_id.group_id:
                rec.role_id._ensure_group()
            domain_force = rec._build_domain()
            vals = {
                "name": "Record Rule: %s / %s / %s" % (
                    rec.role_id.name, rec.model_id.model, rec.rule_type,
                ),
                "model_id": rec.model_id.id,
                "domain_force": domain_force,
                "groups": [(6, 0, [rec.role_id.group_id.id])],
                "perm_read": rec.perm_read,
                "perm_write": rec.perm_write,
                "perm_create": rec.perm_create,
                "perm_unlink": rec.perm_unlink,
            }
            if rec.ir_rule_id:
                rec.ir_rule_id.write(vals)
            else:
                rec.ir_rule_id = Rule.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules._sync_ir_rule()
        return rules

    def write(self, vals):
        res = super().write(vals)
        tracked = {
            "role_id", "model_id", "rule_type", "custom_domain",
            "perm_read", "perm_write", "perm_create", "perm_unlink",
        }
        if tracked & set(vals.keys()):
            self._sync_ir_rule()
        return res

    def unlink(self):
        ir_rules = self.mapped("ir_rule_id")
        res = super().unlink()
        for r in ir_rules:
            try:
                r.unlink()
            except Exception:
                pass
        return res
