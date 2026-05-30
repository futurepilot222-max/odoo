# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccessRightsGuide(models.TransientModel):
    _name = "access.rights.guide"
    _description = "Access Rights Studio - User Guide"

    content = fields.Html(string="User Guide", readonly=True, sanitize=False)

    @api.model
    def _get_guide_html(self):
        """Return the static HTML rendered on the in-app user guide page."""
        return _("""
<div class="oe_access_guide" style="max-width:900px;">
    <h1>Access Rights Studio &mdash; User Guide</h1>
    <p class="text-muted">
        Centralized access control for roles, menus, fields, records and actions.
        All settings stay in sync with Odoo's native security engine.
    </p>

    <h2>1. Roles</h2>
    <p>
        A <b>Role</b> is a reusable bundle of permissions backed by a native Odoo
        security group. Create roles under
        <b>Access Management &rarr; Roles</b>, then assign them to users.
    </p>

    <h2>2. User Permissions</h2>
    <p>
        Grant access directly to a single user (without a role) under
        <b>Access Management &rarr; User Permissions</b>. Useful for one-off
        exceptions.
    </p>

    <h2>3. Menu Permissions</h2>
    <p>
        Control which menus are visible per role or user under
        <b>Menu Permissions</b>. Hidden menus are removed from that user's UI.
    </p>

    <h2>4. Field Permissions</h2>
    <p>
        Restrict <b>read</b> or <b>write</b> access on individual fields under
        <b>Field Permissions</b> &mdash; enforced as a custom layer on top of Odoo.
    </p>

    <h2>5. Record Rules</h2>
    <p>
        Limit which records a user can see by scope: <i>own, team, department,
        company, assigned</i> or <i>global</i>, under <b>Record Rules</b>.
    </p>

    <h2>6. Button / Action Permissions</h2>
    <p>
        Allow or block <b>export, import, print, archive, share and duplicate</b>
        actions under <b>Button Permissions</b>.
    </p>

    <h2>7. Assign Roles</h2>
    <p>
        Use the <b>Assign Roles</b> wizard (managers only) to apply one or more
        roles to many users at once.
    </p>

    <h2>8. Audit Log</h2>
    <p>
        Every permission change is recorded under <b>Audit Log</b> for traceability.
    </p>

    <hr/>
    <p class="text-muted">
        Need help? Contact support at
        <a href="mailto:futurepilot222@gmail.com">futurepilot222@gmail.com</a>.
    </p>
</div>
""")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res["content"] = self._get_guide_html()
        return res
