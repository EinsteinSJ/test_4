# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class L10nLatamIdentificationType(models.Model) :
    _inherit = 'l10n_latam.identification.type'
    _order = 'l10n_pe_vat_code asc, name asc'
    
    l10n_pe_vat_code = fields.Char(string='SUNAT code')
    
    def name_get(self) :
        res_old = super(L10nLatamIdentificationType, self).name_get()
        res = list(res_old)
        for tupla in res_old :
            res.remove(tupla)
            lista = list(tupla)
            lista[0] = self.browse(lista[0])
            lista[1] = (lista[0].l10n_pe_vat_code and (lista[0].l10n_pe_vat_code + ' - ') or '') + lista[1]
            lista[0] = lista[0].id
            res.append(tuple(lista))
        return res
    
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100) :
        args = args or []
        recs = self.browse()
        if name :
            recs = self.search(args + ['|', ('l10n_pe_vat_code',operator,name), ('name',operator,name)], limit=limit)
        if not recs :
            recs = self.search(['|', ('l10n_pe_vat_code',operator,name), ('name',operator,name)] + args, limit=limit)
        return recs.name_get()
