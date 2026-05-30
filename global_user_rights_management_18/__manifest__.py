# -*- coding: utf-8 -*-
{
    'name': 'Access Rights Studio',
    'version': '18.0.1.0.0',
    'sequence': 1,
    'category': 'Administration',
    'summary': 'Centralized access control for roles, menus, fields, records and actions',
    'description': """
Access Rights Studio
====================

A centralized security management module for Odoo that helps administrators control:

    * Roles and direct user rules
    * Model access rights with CRUD permissions
    * Advanced access controls for export, import, print, archive, share and duplicate
    * Menu visibility by role or user
    * Field-level read and write restrictions
    * Record-level visibility by own, team, department, company, assigned or global scope
    * Audit log for permission changes

This module synchronizes standard security settings with Odoo's native security engine
for groups, access rights, record rules and menu visibility, while keeping field-level
restrictions and audit tracking in a custom layer.
""",
    'author': 'Future Pilot',
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/access_role_data.xml',
        'views/access_role_views.xml',
        'views/access_user_rule_views.xml',
        'views/access_menu_rule_views.xml',
        'views/access_field_rule_views.xml',
        'views/access_record_rule_views.xml',
        'views/access_button_rule_views.xml',
        'views/access_audit_log_views.xml',
        'views/res_users_views.xml',
        'wizards/role_assignment_wizard_views.xml',
        'views/menu.xml',
        'views/access_rights_guide_views.xml',
    ],
    'support': 'futurepilot222@gmail.com',
    'price': 40.0,
    'currency': 'USD',
    'license': 'OPL-1',
    'installable': True,
    'application': True,
}