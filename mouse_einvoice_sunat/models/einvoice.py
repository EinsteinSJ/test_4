# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class EinvoiceTempl(models.Model) :
    _name = 'einvoice.templ'
    _description = 'Plantilla para Códigos de la SUNAT'
    
    code = fields.Char(string='Código', index=True, required=True)
    name = fields.Char(string='Nombre', index=True, required=True, translate=False)
    
    @api.depends('code', 'name')
    def name_get(self) :
        return [(rec.id, (rec.code or '') + (rec.code and rec.name and ' - ' or '') + (rec.name or '')) for rec in self]
    
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100) :
        args = args or []
        recs = self.browse()
        if name :
            recs = self.search(args + ['|', ('code',operator,name), ('name',operator,name)], limit=limit)
        if not recs :
            recs = self.search(['|', ('code',operator,name), ('name',operator,name)] + args, limit=limit)
        return recs.name_get()

#Model: l10n_latam.document.type
#Module: l10n_latam_base
#to fill
class Einvoice01(models.Model) :
    _name = 'einvoice.01'
    _description = 'Códigos de Tipo de Comprobante'
    _inherit = 'einvoice.templ'

#Model: res.currency
#Module: base
#class Einvoice02(models.Model) :

#Model: uom.uom
#Module: uom, (uom_unece)
#class Einvoice03(models.Model) :

#Model: res.country
#Module: base
#class Einvoice04(models.Model) :

#Model: account.tax, account.tax.template
#Module: l10n_pe
#Field: l10n_pe_edi_tax_code
class Einvoice05(models.Model) :
    _name = 'einvoice.05'
    _description = 'Códigos de Tipo de Tributo'
    _inherit = 'einvoice.templ'
    
    un_5153 = fields.Char(string='UN/ECE 5153-Duty or tax or fee type name code')
    impuesto = fields.Char(string='Impuesto')

#Model: l10n_latam.identification.type
#Module: l10n_latam_base, l10n_pe
#class Einvoice06(models.Model) :

class Einvoice07(models.Model) :
    _name = 'einvoice.07'
    _description = 'Códigos de Tipo de Afectación del IGV'
    _inherit = 'einvoice.templ'
    
    un_5305 = fields.Char(string='UN/ECE 5305-Duty or tax or fee category code')
    onerosa = fields.Boolean(string='Operación Onerosa')

class Einvoice08(models.Model) :
    _name = 'einvoice.08'
    _description = 'Códigos de Tipo de Sistema de Cálculo del ISC'
    _inherit = 'einvoice.templ'

class Einvoice09(models.Model) :
    _name = 'einvoice.09'
    _description = 'Códigos de Tipo de Nota de Crédito Electrónica'
    _inherit = 'einvoice.templ'

class Einvoice10(models.Model) :
    _name = 'einvoice.10'
    _description = 'Códigos de Tipo de Nota de Débito Electrónica'
    _inherit = 'einvoice.templ'

#Model: account.tax, account.tax.template
#Module: l10n_pe
#Field: l10n_pe_edi_unece_category
class Einvoice11(models.Model) :
    _name = 'einvoice.11'
    _description = 'Códigos de Tipo de Valor de Venta'
    _inherit = 'einvoice.templ'
    
    un_5305 = fields.Char(string='UN/ECE 5305-Duty or tax or fee category code')

class Einvoice12(models.Model) :
    _name = 'einvoice.12'
    _description = 'Códigos de Documentos Relacionados Tributarios'
    _inherit = 'einvoice.templ'

#Model: res.country.state, res.city, l10n_pe.l10n_pe.res.city.district
#Module: l10n_pe
#class Einvoice13(models.Model) :

class Einvoice14(models.Model) :
    _name = 'einvoice.14'
    _description = 'Códigos de Otros Conceptos Tributarios'
    _inherit = 'einvoice.templ'

class Einvoice15(models.Model) :
    _name = 'einvoice.15'
    _description = 'Códigos de Elementos Adicionales en la Factura Electrónica'
    _inherit = 'einvoice.templ'

class Einvoice16(models.Model) :
    _name = 'einvoice.16'
    _description = 'Códigos de Tipo de Precio de Venta Unitario'
    _inherit = 'einvoice.templ'

class Einvoice17(models.Model) :
    _name = 'einvoice.17'
    _description = 'Códigos de Tipo de Operación'
    _inherit = 'einvoice.templ'

class Einvoice18(models.Model) :
    _name = 'einvoice.18'
    _description = 'Códigos de Modalidad de Traslado'
    _inherit = 'einvoice.templ'

class Einvoice19(models.Model) :
    _name = 'einvoice.19'
    _description = 'Códigos de Estado de ítem (resumen diario)'
    _inherit = 'einvoice.templ'

class Einvoice20(models.Model) :
    _name = 'einvoice.20'
    _description = 'Códigos de Motivo de Traslado'
    _inherit = 'einvoice.templ'

class Einvoice21(models.Model) :
    _name = 'einvoice.21'
    _description = 'Códigos de Documentos Relacionados (sólo guía de remisión electrónica)'
    _inherit = 'einvoice.templ'

class Einvoice22(models.Model) :
    _name = 'einvoice.22'
    _description = 'Códigos de Régimen de Percepciones'
    _inherit = 'einvoice.templ'
    
    tasa = fields.Float(string='Tasa (%)')

class Einvoice23(models.Model) :
    _name = 'einvoice.23'
    _description = 'Códigos de Régimen de Retenciones'
    _inherit = 'einvoice.templ'
    
    tasa = fields.Float(string='Tasa (%)')

class Einvoice56(models.Model):
    _name = 'einvoice.56'
    _description = 'Códigos de Tipo de servicio público'
    _inherit = 'einvoice.templ'

class Einvoice24(models.Model) :
    _name = 'einvoice.24'
    _description = 'Códigos de Tarifa de Servicios Públicos'
    _inherit = 'einvoice.templ'
    
    servicio = fields.Many2one(comodel_name='einvoice.56', string='Servicio')

class Einvoice25(models.Model) :
    _name = 'einvoice.25'
    _description = 'Códigos de Producto SUNAT'
    _inherit = 'einvoice.templ'

class Einvoice26(models.Model) :
    _name = 'einvoice.26'
    _description = 'Códigos de Tipo de préstamo (créditos hipotecarios)'
    _inherit = 'einvoice.templ'

class Einvoice27(models.Model) :
    _name = 'einvoice.27'
    _description = 'Códigos de Indicador de primera vivienda'
    _inherit = 'einvoice.templ'

class Einvoice51(models.Model) :
    _name = 'einvoice.51'
    _description = 'Códigos de Tipo de Operación'
    _inherit = 'einvoice.templ'

class Einvoice52(models.Model):
    _name = 'einvoice.52'
    _description = 'Códigos de Leyendas'
    _inherit = 'einvoice.templ'

class Einvoice53(models.Model):
    _name = 'einvoice.53'
    _description = 'Códigos de Cargos, descuentos y otras deducciones'
    _inherit = 'einvoice.templ'
    
    item = fields.Boolean(string='Ítem')

class Einvoice54(models.Model):
    _name = 'einvoice.54'
    _description = 'Códigos de Bienes y servicios sujetos a detracciones'
    _inherit = 'einvoice.templ'

class Einvoice55(models.Model):
    _name = 'einvoice.55'
    _description = 'Códigos de Identificación del concepto tributario'
    _inherit = 'einvoice.templ'

class Einvoice57(models.Model):
    _name = 'einvoice.57'
    _description = 'Códigos de Tipo de servicio público - telecomunicaciones'
    _inherit = 'einvoice.templ'

class Einvoice58(models.Model):
    _name = 'einvoice.58'
    _description = 'Códigos de Tipo de medidor (recibo de luz)'
    _inherit = 'einvoice.templ'

class Einvoice59(models.Model):
    _name = 'einvoice.59'
    _description = 'Códigos de Medios de pago'
    _inherit = 'einvoice.templ'

class Einvoice60(models.Model):
    _name = 'einvoice.60'
    _description = 'Códigos de Tipo de dirección'
    _inherit = 'einvoice.templ'
