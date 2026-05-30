# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccessMenuRule(models.Model):
    """Menu visibility per role.

    Adds the role's linked res.groups to the targeted menu's groups_id when
    ``visible`` is True, and removes it when False. Native menu filtering then
    takes care of hiding the menu for users outside the role.
    """

    _name = "access.menu.rule"
    _description = "Menu Visibility Rule"
    _rec_name = "menu_id"

    role_id = fields.Many2one(
        "access.role", required=True, ondelete="cascade", index=True,
    )
    menu_id = fields.Many2one(
        "ir.ui.menu", required=True, ondelete="cascade", string="Menu",
    )
    visible = fields.Boolean(
        default=True,
        help="Tick to grant the role visibility on the menu. Untick to hide it.",
    )

    _sql_constraints = [
        ("uniq_role_menu", "unique(role_id, menu_id)",
         "A role cannot define the same menu visibility twice."),
    ]

    def _sync_menu_visibility(self):
        for rec in self:
            if not rec.role_id.group_id:
                rec.role_id._ensure_group()
            grp = rec.role_id.group_id
            if rec.visible:
                rec.menu_id.sudo().write({"group_ids": [(4, grp.id)]})
            else:
                rec.menu_id.sudo().write({"group_ids": [(3, grp.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules._sync_menu_visibility()
        return rules

    def write(self, vals):
        res = super().write(vals)
        if {"menu_id", "visible", "role_id"} & set(vals.keys()):
            self._sync_menu_visibility()
        return res

    def unlink(self):
        for rec in self:
            if rec.role_id.group_id and rec.menu_id:
                rec.menu_id.sudo().write({
                    "group_ids": [(3, rec.role_id.group_id.id)],
                })
        return super().unlink()
