# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccessUserRule(models.Model):
    """Per-user direct permission override on a single model.

    A user rule is independent of roles: it grants extra access (read / write /
    create / unlink) to a specific user, on top of whatever the user's roles
    already provide. Useful for one-off carve-outs without authoring a full role.
    """

    _name = "access.user.rule"
    _description = "User-Level Access Rule"
    _rec_name = "display_name"

    user_id = fields.Many2one(
        "res.users", required=True, ondelete="cascade", index=True,
    )
    model_id = fields.Many2one(
        "ir.model", required=True, ondelete="cascade", string="Model",
    )
    model_name = fields.Char(related="model_id.model", store=True)

    perm_read = fields.Boolean(default=True)
    perm_write = fields.Boolean()
    perm_create = fields.Boolean()
    perm_unlink = fields.Boolean(string="Delete")

    perm_approve = fields.Boolean()
    perm_export = fields.Boolean()
    perm_import = fields.Boolean()
    perm_print = fields.Boolean()
    perm_duplicate = fields.Boolean()
    perm_archive = fields.Boolean()
    perm_share = fields.Boolean()

    active = fields.Boolean(default=True)
    note = fields.Char(string="Reason")

    group_id = fields.Many2one(
        "res.groups", copy=False,
        help="Private res.groups used to materialise this user rule.",
    )
    ir_access_id = fields.Many2one("ir.model.access", copy=False)

    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("user_id", "model_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s / %s" % (
                rec.user_id.display_name or "?",
                rec.model_id.name or "?",
            )

    _sql_constraints = [
        ("uniq_user_model", "unique(user_id, model_id)",
         "Each user can have only one rule per model."),
    ]

    def _ensure_group(self):
        Groups = self.env["res.groups"].sudo()
        Access = self.env["ir.model.access"].sudo()
        for rec in self:
            if not rec.group_id:
                rec.group_id = Groups.create({
                    "name": "User Rule: %s / %s" % (
                        rec.user_id.login, rec.model_id.model,
                    ),
                })
            rec.group_id.sudo().write({"user_ids": [(4, rec.user_id.id)]})
            vals = {
                "name": "user_rule_%d_%s" % (
                    rec.user_id.id, (rec.model_id.model or "").replace(".", "_"),
                ),
                "model_id": rec.model_id.id,
                "group_id": rec.group_id.id,
                "perm_read": rec.perm_read,
                "perm_write": rec.perm_write,
                "perm_create": rec.perm_create,
                "perm_unlink": rec.perm_unlink,
            }
            if rec.ir_access_id:
                rec.ir_access_id.write(vals)
            else:
                rec.ir_access_id = Access.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules._ensure_group()
        return rules

    def write(self, vals):
        res = super().write(vals)
        self._ensure_group()
        return res

    def unlink(self):
        groups = self.mapped("group_id")
        accesses = self.mapped("ir_access_id")
        res = super().unlink()
        for grp in groups:
            try:
                grp.sudo().unlink()
            except Exception:
                pass
        for acc in accesses:
            try:
                acc.sudo().unlink()
            except Exception:
                pass
        return res
