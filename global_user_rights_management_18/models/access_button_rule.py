# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccessButtonRule(models.Model):
    """Hide form-view buttons per role.

    A rule identifies a button by ``(model, button_name)`` where ``button_name``
    is the value of the XML ``name`` attribute on the ``<button>`` element -
    typically a python method on the model (e.g. ``action_confirm``,
    ``action_cancel``, ``action_draft``). At view render time, every form view
    served to a user assigned this role will have the matching button hidden.

    Hiding semantics: union across the user's roles. If any role rule says
    hide, the button is hidden. Superusers and Settings administrators are
    exempt.
    """

    _name = "access.button.rule"
    _description = "Button Visibility Rule"
    _rec_name = "display_name"

    role_id = fields.Many2one(
        "access.role", required=True, ondelete="cascade", index=True,
    )
    model_id = fields.Many2one(
        "ir.model", required=True, ondelete="cascade", string="Model",
    )
    model_name = fields.Char(related="model_id.model", store=True, index=True)
    button_name = fields.Char(
        required=True,
        help="Technical name of the button (the XML 'name' attribute). "
             "For workflow buttons this is usually a method name on the model, "
             "e.g. action_confirm, action_cancel, action_draft.",
    )
    label = fields.Char(
        string="Label",
        help="Optional human-readable label shown in the role configuration "
             "(e.g. 'Confirm', 'Cancel', 'Reset to Draft'). Not enforced at "
             "render time.",
    )
    hide = fields.Boolean(
        default=True,
        help="If checked, the button is hidden for users in this role. "
             "Uncheck to keep a rule on file without enforcing it.",
    )
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        ("uniq_role_model_button", "unique(role_id, model_id, button_name)",
         "A role cannot define the same button rule twice."),
    ]

    @api.depends("role_id", "model_id", "button_name", "label")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s / %s / %s" % (
                rec.role_id.name or "?",
                rec.model_id.model or "?",
                rec.label or rec.button_name or "?",
            )
