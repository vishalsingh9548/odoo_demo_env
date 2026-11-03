{
    'name': 'Home Kouzina Access',
    'version': '18.0.1.0.0',
    'summary': 'Single access group that switches on all Home Kouzina custom functionality',
    'description': """
Defines one group, "Home Kouzina Access". Menus, fields, tabs, buttons, filters,
list columns, wizards and reports added by the Home Kouzina custom modules are
only available to users who are members of this group.
    """,
    'category': 'Hidden',
    'author': 'Home Kouzina',
    'depends': ['base'],
    'data': [
        'security/hk_security.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
