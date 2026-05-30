# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccessRole(models.Model):
    _name = "access.role"
    _description = "Access Role"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(
        help="Technical short code used to derive the underlying res.groups xml id.",
    )
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    group_id = fields.Many2one(
        "res.groups",
        string="Linked Security Group",
        ondelete="restrict",
        copy=False,
        help="The native Odoo group automatically created and kept in sync with this role.",
    )
    category_id = fields.Many2one(
        "ir.module.category",
        string="Application",
        help="Optional application category the role appears under.",
    )

    line_ids = fields.One2many(
        "access.role.line", "role_id", string="Model Permissions", copy=True,
    )
    menu_rule_ids = fields.One2many(
        "access.menu.rule", "role_id", string="Menu Rules", copy=True,
    )
    field_rule_ids = fields.One2many(
        "access.field.rule", "role_id", string="Field Rules", copy=True,
    )
    record_rule_ids = fields.One2many(
        "access.record.rule", "role_id", string="Record Rules", copy=True,
    )
    button_rule_ids = fields.One2many(
        "access.button.rule", "role_id", string="Button Rules", copy=True,
    )

    user_ids = fields.Many2many(
        "res.users", "access_role_users_rel", "role_id", "user_id",
        string="Users",
    )
    user_count = fields.Integer(compute="_compute_user_count")

    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("archived", "Archived")],
        default="draft",
    )

    menu_strict_mode = fields.Boolean(
        string="Strict Menu Mode",
        help="When enabled, users assigned this role will see ONLY the menus "
             "explicitly ticked Visible on the Menu Visibility tab (plus their "
             "ancestor menus). Menus a user could otherwise see via other "
             "groups will be hidden. If the user has multiple strict roles, "
             "the union of allowed menus applies.",
    )

    crud_strict_mode = fields.Boolean(
        string="Strict CRUD Mode",
        help="When enabled, for every model listed on the Model Permissions "
             "tab the role's CRUD flags become the CEILING for users assigned "
             "this role. Operations not ticked here (Write/Create/Delete) are "
             "blocked even if other groups would normally grant them. Models "
             "NOT listed on the tab are unaffected (fall back to native "
             "behaviour). Multiple strict roles combine by union: the user is "
             "allowed an operation if ANY of their strict roles grants it.",
    )

    @api.depends("user_ids")
    def _compute_user_count(self):
        for rec in self:
            rec.user_count = len(rec.user_ids)

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if rec.code and not rec.code.replace("_", "").isalnum():
                raise ValidationError(_(
                    "Role code must be alphanumeric (underscores allowed): %s"
                ) % rec.code)

    # ------------------------------------------------------------------
    # res.groups sync
    # ------------------------------------------------------------------
    def _group_name(self):
        self.ensure_one()
        return "Role: %s" % self.name

    def _ensure_group(self):
        """Create the linked res.groups if missing, otherwise sync its name."""
        Groups = self.env["res.groups"].sudo()
        for rec in self:
            if not rec.group_id:
                rec.group_id = Groups.create({
                    "name": rec._group_name(),
                    "category_id": rec.category_id.id or False,
                })
            else:
                vals = {"name": rec._group_name()}
                if rec.category_id and rec.group_id.category_id != rec.category_id:
                    vals["category_id"] = rec.category_id.id
                rec.group_id.sudo().write(vals)

    def _sync_users(self):
        """Sync members of the linked res.groups to match user_ids."""
        for rec in self:
            if not rec.group_id:
                continue
            rec.group_id.sudo().write({"user_ids": [(6, 0, rec.user_ids.ids)]})

    def _sync_all(self):
        """Re-sync every native security artefact derived from this role."""
        self._ensure_group()
        self._sync_users()
        self.mapped("line_ids")._sync_model_access()
        self.mapped("menu_rule_ids")._sync_menu_visibility()
        self.mapped("field_rule_ids")._sync_field_groups()
        self.mapped("record_rule_ids")._sync_ir_rule()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        roles = super().create(vals_list)
        roles._ensure_group()
        roles._sync_all()
        for role in roles:
            self.env["access.audit.log"].sudo().log(
                "create", role._name, role.id, role.display_name,
                notes="Role created",
            )
        return roles

    def write(self, vals):
        old_snapshot = {r.id: r._audit_snapshot() for r in self}
        res = super().write(vals)
        if any(k in vals for k in ("name", "category_id")):
            self._ensure_group()
        if "user_ids" in vals:
            self._sync_users()
        self._log_audit("write", vals, old_snapshot)
        return res

    def unlink(self):
        for rec in self:
            self.env["access.audit.log"].sudo().log(
                "unlink", rec._name, rec.id, rec.display_name,
                notes="Role deleted",
            )
        for rec in self:
            grp = rec.group_id
            super(AccessRole, rec).unlink()
            if grp:
                try:
                    grp.sudo().unlink()
                except Exception:
                    # group may still be referenced elsewhere; leave it.
                    pass
        return True

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    def _audit_snapshot(self):
        self.ensure_one()
        return {
            "name": self.name,
            "code": self.code,
            "active": self.active,
            "state": self.state,
            "user_ids": self.user_ids.ids,
        }

    def _log_audit(self, action, vals, old_snapshot=None):
        if not isinstance(vals, dict) or not vals:
            return
        Log = self.env["access.audit.log"].sudo()
        for rec in self:
            old = (old_snapshot or {}).get(rec.id, {})
            for key, new_value in vals.items():
                Log.create({
                    "user_id": self.env.uid,
                    "model_name": rec._name,
                    "record_id": rec.id,
                    "record_name": rec.display_name,
                    "field_name": key,
                    "old_value": str(old.get(key, "")),
                    "new_value": str(new_value),
                    "action": action,
                })

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_activate(self):
        self.write({"state": "active"})
        self._sync_all()

    def action_archive_role(self):
        self.write({"state": "archived", "active": False})

    def action_resync(self):
        self._sync_all()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Re-synchronised"),
                "message": _("Security artefacts have been refreshed."),
                "type": "success",
            },
        }

    def action_open_users(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Users"),
            "res_model": "res.users",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.user_ids.ids)],
        }


class AccessRoleLine(models.Model):
    _name = "access.role.line"
    _description = "Access Role - Model Permission Line"
    _rec_name = "model_id"

    role_id = fields.Many2one(
        "access.role", required=True, ondelete="cascade", index=True,
    )
    model_id = fields.Many2one(
        "ir.model", required=True, ondelete="cascade", string="Model",
    )
    model_name = fields.Char(related="model_id.model", store=True, string="Technical Name")

    # Basic CRUD permissions
    perm_read = fields.Boolean(string="Read", default=True)
    perm_write = fields.Boolean(string="Write")
    perm_create = fields.Boolean(string="Create")
    perm_unlink = fields.Boolean(string="Delete")

    # Advanced permissions (enforced by hooks / view groups)
    perm_approve = fields.Boolean(string="Approve")
    perm_export = fields.Boolean(string="Export")
    perm_import = fields.Boolean(string="Import")
    perm_print = fields.Boolean(string="Print")
    perm_duplicate = fields.Boolean(string="Duplicate")
    perm_archive = fields.Boolean(string="Archive")
    perm_share = fields.Boolean(string="Share")

    ir_access_id = fields.Many2one(
        "ir.model.access", ondelete="set null", copy=False,
        help="Native ir.model.access record automatically kept in sync.",
    )

    _sql_constraints = [
        ("uniq_role_model", "unique(role_id, model_id)",
         "A role cannot define the same model twice."),
    ]

    def _ir_access_name(self):
        self.ensure_one()
        return "access_%s_%s" % (
            (self.model_id.model or "").replace(".", "_"),
            (self.role_id.code or self.role_id.name or "role").lower().replace(" ", "_"),
        )

    def _sync_model_access(self):
        Access = self.env["ir.model.access"].sudo()
        for line in self:
            if not line.role_id.group_id:
                line.role_id._ensure_group()
            vals = {
                "name": line._ir_access_name(),
                "model_id": line.model_id.id,
                "group_id": line.role_id.group_id.id,
                "perm_read": line.perm_read,
                "perm_write": line.perm_write,
                "perm_create": line.perm_create,
                "perm_unlink": line.perm_unlink,
            }
            if line.ir_access_id:
                line.ir_access_id.write(vals)
            else:
                line.ir_access_id = Access.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sync_model_access()
        return lines

    def write(self, vals):
        res = super().write(vals)
        perm_keys = {
            "model_id", "perm_read", "perm_write", "perm_create", "perm_unlink",
        }
        if perm_keys & set(vals.keys()):
            self._sync_model_access()
        return res

    def unlink(self):
        access_ids = self.mapped("ir_access_id")
        res = super().unlink()
        if access_ids:
            try:
                access_ids.unlink()
            except Exception:
                pass
        return res
