# -*- coding: utf-8 -*-
from odoo import api, models


# Mirrors base_model._BYPASS_USER_IDS - UID 1 (Odoo superuser) and UID 2
# (installed admin) are exempt from strict menu rules as a recovery account.
_BYPASS_USER_IDS = frozenset([1, 2])


class IrUiMenu(models.Model):
    """Restrict visible menus when the user belongs to a strict-mode role.

    Odoo's native menu visibility is additive: a menu is visible if its
    ``groups_id`` is empty or intersects the user's groups. That means giving a
    user a 'Viewer' role with only Sales+Purchase visibility does NOT remove
    other menus the user can already see through their existing groups.

    With strict-mode roles, the visibility set becomes a WHITELIST: when a
    user has at least one role with ``menu_strict_mode = True``, they can only
    see the union of menus (plus ancestors) explicitly marked Visible on those
    strict roles. Superusers and system administrators are exempt.
    """

    _inherit = "ir.ui.menu"

    def _gurm_strict_whitelist_ids(self):
        """Return the set of menu ids allowed by the current user's strict
        roles, or None if no strict role applies (meaning: no restriction)."""
        env = self.env
        if env.uid in (None, False) or env.uid in _BYPASS_USER_IDS:
            return None
        user = env.user
        roles = user.role_ids.filtered(lambda r: r.menu_strict_mode and r.state == "active")
        if not roles:
            return None
        allowed = set()
        rules = roles.mapped("menu_rule_ids").filtered(lambda r: r.visible)
        for rule in rules:
            menu = rule.menu_id
            if not menu:
                continue
            allowed.add(menu.id)
            # add the full parent chain so nested menus actually render
            parent = menu.parent_id
            while parent:
                allowed.add(parent.id)
                parent = parent.parent_id
        return allowed

    @api.model
    def _visible_menu_ids(self, debug=False):
        result = super()._visible_menu_ids(debug=debug)
        whitelist = self._gurm_strict_whitelist_ids()
        if whitelist is None:
            return result
        return set(result) & whitelist
