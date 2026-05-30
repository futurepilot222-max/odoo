# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class RoleAssignmentWizard(models.TransientModel):
    _name = "access.role.assignment.wizard"
    _description = "Assign Roles to Users"

    role_ids = fields.Many2many(
        "access.role", string="Roles to Assign", required=True,
    )
    user_ids = fields.Many2many(
        "res.users", string="Target Users", required=True,
    )
    operation = fields.Selection(
        [("add", "Add Roles"), ("remove", "Remove Roles"), ("set", "Replace All Roles")],
        default="add", required=True,
    )

    def action_apply(self):
        self.ensure_one()
        for user in self.user_ids:
            if self.operation == "add":
                new_ids = list(set(user.role_ids.ids) | set(self.role_ids.ids))
            elif self.operation == "remove":
                new_ids = list(set(user.role_ids.ids) - set(self.role_ids.ids))
            else:
                new_ids = self.role_ids.ids
            user.write({"role_ids": [(6, 0, new_ids)]})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Roles updated"),
                "message": _("%d user(s) updated.") % len(self.user_ids),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
