# -*- coding: utf-8 -*-

{
    'name': 'Factura electrónica - Base',
    'version': '13.0.1.0.0',
    'author': 'Mouse Technologies',
    'category': 'Accounting & Finance',
    'summary': 'Tablas y requisitos para la factura electrónica.',
    'license': 'LGPL-3',
    'description' : """
Factura electronica - Base.
====================================

Tablas:
--------------------------------------------
    * Tablas requeridas por la Factura electrónica
    """,
    'website': 'https://www.mstech.pe',
    'depends': [
        'l10n_pe',
        'l10n_latam_invoice_document',
        'account_debit_note',
        'uom_unece',
        'mouse_einvoice_sunat',
        'mouse_ruc_validation',
    ],
    'external_dependencies ': {
        'python': [
            'pyOpenSSL',
            'signxml',
            'qrcode',
        ],
    },
    'data': [
        'data/ir_cron_data.xml',
        'data/ir_ui_view_data.xml', #l10n_latam_invoice_document.report_invoice_document
        'data/l10n_latam.document.type.csv',
        'data/res.currency.csv',
        'views/ir_sequence_views.xml',
        'views/res_company_views.xml',
        'views/account_views.xml',
        'views/account_move_views.xml',
        'views/report_invoice.xml',
        'views/report_templates.xml',
        'wizard/account_move_reversal_views.xml',
        'wizard/account_debit_note_views.xml',
    ],
    'installable': True,
    'uninstall_hook': 'after_uninstall',
    'sequence': 1,
}
