# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    role_ids = fields.Many2many(
        "access.role",
        "access_role_users_rel", "user_id", "role_id",
        string="Access Roles",
        help="Roles defined in Global User Rights Management. Selecting a role "
             "automatically grants the user the role's linked res.groups.",
    )
    user_rule_ids = fields.One2many(
        "access.user.rule", "user_id", string="User-Level Rules",
    )

    def _sync_role_groups(self):
        """Ensure ``group_ids`` reflects whatever roles are assigned."""
        for user in self:
            role_groups = user.role_ids.mapped("group_id")
            missing = role_groups - user.group_ids
            if missing:
                user.sudo().write({"group_ids": [(4, g.id) for g in missing]})

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._sync_role_groups()
        for user in users:
            self.env["access.audit.log"].sudo().log(
                "assign", "res.users", user.id, user.display_name,
                "role_ids", "", str(user.role_ids.ids),
                notes="User created with roles",
            )
        return users

    def write(self, vals):
        old_roles = {u.id: u.role_ids.ids for u in self}
        res = super().write(vals)
        if "role_ids" in vals:
            self._sync_role_groups()
            for user in self:
                new = user.role_ids.ids
                old = old_roles.get(user.id, [])
                if set(old) != set(new):
                    self.env["access.audit.log"].sudo().log(
                        "assign", "res.users", user.id, user.display_name,
                        "role_ids", str(old), str(new),
                    )
        return res
