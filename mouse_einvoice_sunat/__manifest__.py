# -*- coding: utf-8 -*-

{
    'name': 'Factura electrónica - Catálogos SUNAT',
    'version': '13.0.1.0.0',
    'author': 'Mouse Technologies',
    'category': 'Accounting & Finance',
    'summary': 'Catálogos de la SUNAT para la factura electrónica.',
    'license': 'LGPL-3',
    'description' : """
Factura electronica - Catálogos SUNAT.
====================================

Catálogos:
--------------------------------------------
    * Catálogos requeridas por la Factura electrónica
    """,
    'website': 'https://www.mstech.pe',
    'depends': [
        'account',
    ],
    'data': [
        'data/einvoice_data.xml',
        'security/ir.model.access.csv',
        'views/einvoice_views.xml',
    ],
    'installable': True,
}
