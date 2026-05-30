# -*- coding: utf-8 -*-
from lxml import etree

from odoo import api, models, _
from odoo.exceptions import AccessError


# Internal models that must never be subject to strict CRUD, button hiding or
# field-level enforcement, otherwise we deadlock the security engine itself.
_BYPASS_MODELS = frozenset([
    "access.role", "access.role.line", "access.user.rule",
    "access.menu.rule", "access.field.rule", "access.record.rule",
    "access.button.rule",
    "access.audit.log", "access.role.assignment.wizard",
    "ir.model.access", "ir.rule", "res.groups", "ir.model.fields",
    "ir.ui.menu", "ir.ui.view", "ir.model", "ir.actions.actions",
    "ir.actions.act_window", "ir.actions.server", "ir.actions.report",
])

# Users exempt from strict-mode role enforcement.
# UID 1 (res.users.user_root) is Odoo's built-in superuser - always exempt.
# UID 2 (typically res.users.user_admin) is kept exempt as a recovery account
# so a misconfigured role cannot lock out the system administrator.
_BYPASS_USER_IDS = frozenset([1, 2])

_OP_TO_PERM = {
    "read": "perm_read",
    "write": "perm_write",
    "create": "perm_create",
    "unlink": "perm_unlink",
}


class Base(models.AbstractModel):
    """Hook into every model to enforce:

      * field-level write rules (readonly fields blocked unless user is in role)
      * strict-mode CRUD ceiling (via _check_access override)
      * button hiding (via get_view arch mutation)

    Odoo 18 notes:
      * check_access_rights()/check_access_rule() are deprecated and no longer
        called by the framework; access is enforced through _check_access(),
        which returns None when allowed or a (records, exc_factory) pair when
        denied.
      * Per-user view changes must go in get_view(), NOT _get_view():
        _get_view() runs inside the @ormcache'd _get_view_cache(), whose key
        excludes the user, so per-user mutations there leak across users.
      * Modifiers are expressed as direct attributes on nodes
        (``invisible="..."``, ``readonly="..."``); the old JSON-encoded
        ``modifiers`` attribute is no longer used.
    """

    _inherit = "base"

    # ------------------------------------------------------------------
    # Strict-mode CRUD ceiling
    # ------------------------------------------------------------------
    # Odoo 18 deprecated check_access_rights()/check_access_rule(); the ORM now
    # routes every access check through _check_access(). It returns None when
    # allowed, or a (forbidden_records, exception_factory) pair when denied.
    def _check_access(self, operation):
        result = super()._check_access(operation)
        if result is not None:
            return result
        if self._gurm_strict_denies(operation):
            def _make_strict_error():
                return AccessError(_(
                    "Your role configuration does not allow operation "
                    "'%(op)s' on '%(model)s'.",
                    op=operation,
                    model=self._description or self._name,
                ))
            return self, _make_strict_error
        return None

    def _gurm_strict_denies(self, operation):
        if self._name in _BYPASS_MODELS:
            return False
        perm_field = _OP_TO_PERM.get(operation)
        if not perm_field:
            return False
        env = self.env
        if env.su or env.uid in (None, False) or env.uid in _BYPASS_USER_IDS:
            return False
        user = env.user

        cache = getattr(env.cr, "_gurm_cache", None)
        if cache is None:
            cache = {}
            env.cr._gurm_cache = cache

        cache_key = ("_gurm_strict_lines", user.id, self._name)
        if cache_key not in cache:
            cache[cache_key] = env["access.role.line"].sudo().search([
                ("role_id.crud_strict_mode", "=", True),
                ("role_id.state", "=", "active"),
                ("role_id.user_ids", "in", user.id),
                ("model_name", "=", self._name),
            ])
        lines = cache[cache_key]
        if not lines:
            return False
        return not any(line[perm_field] for line in lines)

    # ------------------------------------------------------------------
    # Button-level view-arch hiding (Odoo 18 get_view API)
    # ------------------------------------------------------------------
    # NOTE: button hiding is per-user, so it must NOT be done in _get_view().
    # In Odoo 18 _get_view() runs inside _get_view_cache(), which is
    # @ormcache'd on a key that does not include the user or their groups
    # (see ir.ui.view._get_view_cache_key). Any per-user mutation there would
    # be cached and leaked across users. get_view() is the per-request,
    # non-cached entry point, so we mutate the final arch string here instead.
    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if self._name in _BYPASS_MODELS:
            return result
        button_names = self._gurm_buttons_to_hide()
        if not button_names:
            return result
        node = etree.fromstring(result["arch"])
        if node.tag != "form":
            return result
        changed = False
        for btn in node.xpath("//button[@name]"):
            if btn.get("name") in button_names:
                # Odoo 18 expresses modifiers as direct attributes.
                btn.set("invisible", "1")
                changed = True
        if changed:
            result["arch"] = etree.tostring(node, encoding="unicode")
        return result

    def _gurm_buttons_to_hide(self):
        if self._name in _BYPASS_MODELS:
            return set()
        env = self.env
        if env.su or env.uid in (None, False) or env.uid in _BYPASS_USER_IDS:
            return set()
        user = env.user

        cache = getattr(env.cr, "_gurm_cache", None)
        if cache is None:
            cache = {}
            env.cr._gurm_cache = cache
        cache_key = ("_gurm_btn_hide", user.id, self._name)
        if cache_key not in cache:
            rules = env["access.button.rule"].sudo().search([
                ("model_name", "=", self._name),
                ("hide", "=", True),
                ("role_id.state", "=", "active"),
                ("role_id.user_ids", "in", user.id),
            ])
            cache[cache_key] = set(rules.mapped("button_name"))
        return cache[cache_key]

    # ------------------------------------------------------------------
    # Field-level write guard
    # ------------------------------------------------------------------
    def write(self, vals):
        if vals and not self.env.su and self.env.uid:
            self._gurm_check_field_writes(vals)
        return super().write(vals)

    def _gurm_check_field_writes(self, vals):
        if self._name in _BYPASS_MODELS:
            return
        env = self.env
        if env.su or env.uid in (None, False) or env.uid in _BYPASS_USER_IDS:
            return
        user = env.user

        FieldRule = env["access.field.rule"].sudo()
        cache_key = ("_gurm_field_rules", self._name)
        cache = getattr(env.cr, "_gurm_cache", None)
        if cache is None:
            cache = {}
            env.cr._gurm_cache = cache
        if cache_key not in cache:
            cache[cache_key] = FieldRule.search([
                ("model_name", "=", self._name),
                ("readonly", "=", True),
            ])
        rules = cache[cache_key]
        if not rules:
            return

        user_group_ids = set(user.all_group_ids.ids)
        for fname in vals.keys():
            applicable = rules.filtered(lambda r: r.field_name == fname)
            if not applicable:
                continue
            allowed_group_ids = applicable.mapped("role_id.group_id").ids
            if not (set(allowed_group_ids) & user_group_ids):
                raise AccessError(_(
                    "You are not allowed to modify field '%(field)s' on "
                    "'%(model)s'.",
                    field=fname,
                    model=self._name,
                ))
