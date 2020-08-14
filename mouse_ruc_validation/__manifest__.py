# -*- coding: utf-8 -*-

{
    'name': 'Validador de RUC y DNI',
    'version': '1.0.0',
    'author': 'Mouse Technologies',
    'category': 'Generic Modules/Base',
    'summary': 'Valida RUC y DNI',
    'license': 'AGPL-3',
    'description' : """
Validador de RUC y DNI
-----------------------

Clientes y Proveedores:
-----------------------
    * Validacion RUC y DNI
""",
    'website': 'https://www.mstech.pe',
    'depends': [
        'mouse_toponyms',
    ],
    'data': [
        'data/l10n_latam_identification_type_data.xml',
        'views/res_partner_views.xml',
        'views/l10n_latam_identification_type_views.xml',
        'views/res_company_views.xml',
    ],
    'sequence': 1,
    'post_init_hook': 'after_install',
    'uninstall_hook': 'after_uninstall',
}
