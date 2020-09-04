# -*- coding: utf-8 -*-

{
    'name' : 'Facturación Electrónica - Punto de Venta',
    'version' : '13.0.1.0.0',
    'author' : 'Mouse Technologies',
    'category' : 'Accounting & Finance',
    'summary': 'Facturación electrónica en el Punto de Venta.',
    'license': 'LGPL-3',
    'description' : """
Factura electronica - Punto de Venta.
====================================

Tablas:
--------------------------------------------
    * Cambios necesarios en el Punto de Venta
    """,
    'website': 'https://www.mouse.pe',
    'depends' : [
        'mouse_einvoice_base',
        'point_of_sale',
    ],
    'data': [
        'views/assets.xml',
    ],
    'qweb': [
        'static/src/xml/pos.xml',
    ],
    'installable': True,
    'auto_install': False,
    'sequence': 1,
}
