# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class Company(models.Model) :
    _inherit = 'res.company'
    
    def _get_default_l10n_latam_identification_type_id(self, module='l10n_latam_base', xml_id='it_vat') :
        valor = self.partner_id._get_default_l10n_latam_identification_type_id(module=module, xml_id=xml_id)
        return valor
    
    l10n_latam_identification_type_id = fields.Many2one(comodel_name='l10n_latam.identification.type', related='partner_id.l10n_latam_identification_type_id', readonly=False, store=True)
    
    @api.model
    def create(self, vals) :
        company = super(Company, self).create(vals)
        if not company.l10n_latam_identification_type_id and company.country_id == self.env.ref('base.pe') :
            company.write({'l10n_latam_identification_type_id': vals.get('l10n_latam_identification_type_id') or self._get_default_l10n_latam_identification_type_id().id})
        return company
    
    def write(self, vals) :
        res = super(Company, self).write(vals)
        valor_ruc = self._get_default_l10n_latam_identification_type_id()
        sin_ruc = self.filtered(lambda r: r.country_id == self.env.ref('base.pe') and r.partner_id.l10n_latam_identification_type_id != valor_ruc)
        if sin_ruc.ids :
            sin_ruc.partner_id.write({'l10n_latam_identification_type_id': valor_ruc.id})
        return res
