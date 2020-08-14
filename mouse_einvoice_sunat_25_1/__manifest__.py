# -*- coding: utf-8 -*-

{
    'name': 'Factura electrónica - Catálogo 25 SUNAT (1/5)',
    'version': '13.0.1.0.0',
    'author': 'Mouse Technologies',
    'category': 'Accounting & Finance',
    'summary': 'Catálogo 25 (1/5) de la SUNAT para la factura electrónica.',
    'license': 'LGPL-3',
    'description' : """
Factura electronica - Catálogo 25 SUNAT (1/5).
====================================

Catálogos:
--------------------------------------------
    * Catálogo 25 (parte 1/5)
    """,
    'website': 'https://www.mstech.pe',
    'depends': [
        'mouse_einvoice_sunat_25',
    ],
    'data': [
        'data/einvoice_data.xml',
    ],
    'auto_install': True,
}
