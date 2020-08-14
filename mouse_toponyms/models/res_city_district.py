# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class L10nPeResCityDistrict(models.Model) :
    _inherit = 'l10n_pe.res.city.district'
    
    name = fields.Char(required=True, translate=False)
    country_id = fields.Many2one(comodel_name='res.country', required=True)
    state_id = fields.Many2one(comodel_name='res.country.state', required=True)
    city_id = fields.Many2one(required=True)
    code = fields.Char(required=True)
    
    @api.onchange('country_id')
    def _onchange_country_id(self) :
        if self.state_id :
            self.state_id = False
        else :
            self.code = False
    
    @api.onchange('state_id')
    def _onchange_state_id(self) :
        if self.city_id :
            self.city_id = False
        else :
            self.code = self.state_id.code
    
    @api.onchange('city_id')
    def _onchange_city_id(self) :
        if self.state_id :
            self.state_id = False
        else :
            self.code = self.city_id.l10n_pe_code or self.state_id.code
    
    _sql_constraints = [('unique_district_name', 'unique(city_id, name)', 'This district already exists in this city.'),
                        ('unique_district_code', 'unique(city_id, code)', 'A district with this code already exists in this city.')]
