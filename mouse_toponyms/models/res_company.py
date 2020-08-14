# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

from lxml import etree

class Company(models.Model) :
    _inherit = 'res.company'
    
    city_id = fields.Many2one(comodel_name='res.city', compute='_compute_address', inverse='_inverse_city_id', string='City')
    l10n_pe_district = fields.Many2one(comodel_name='l10n_pe.res.city.district', compute='_compute_address', inverse='_inverse_l10n_pe_district', string='District')
    type = fields.Selection(related='partner_id.type') #, selection=[('contact','Contact'), ('invoice','Invoice Address'), ('delivery','Delivery Address'), ('other','Other Address'), ('private','Private Address')])
    
    def _fields_view_get_address(self, arch) :
        # consider the country of the company we want to display
        address_view_id = self.country_id.address_view_id or self.env.company.country_id.address_view_id
        if address_view_id and not self._context.get('no_address_format') :
            #render the partner address accordingly to address_view_id
            doc = etree.fromstring(arch)
            for address_node in doc.xpath("//div[hasclass('o_address_format')]") :
                Company = self.env['res.company'].with_context(no_address_format=True)
                sub_view = Company.fields_view_get(view_id=address_view_id.id, view_type='form', toolbar=False, submenu=False)
                sub_view_node = etree.fromstring(sub_view['arch'])
                #if the model is different than res.company, there are chances that the view won't work
                #(e.g fields not present on the model). In that case we just return arch
                if self._name != 'res.company' :
                    try :
                        self.env['ir.ui.view'].postprocess_and_fields(self._name, sub_view_node, None)
                    except ValueError :
                        return arch
                address_node.getparent().replace(address_node, sub_view_node)
            arch = etree.tostring(doc, encoding='unicode')
        return arch
    
    @api.model
    def _fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False) :
        res = super(Company, self)._fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form' :
            res['arch'] = self._fields_view_get_address(res['arch'])
        return res
    
    def _get_company_address_fields(self, partner) :
        address_fields = super(Company, self)._get_company_address_fields(partner)
        address_fields.update({
            'city_id': partner.city_id,
            'l10n_pe_district': partner.l10n_pe_district,
        })
        return address_fields
    
    @api.onchange('country_id')
    def _onchange_country_id_wrapper(self) :
        if self.country_id == self.env.ref('base.pe') :
            if self.state_id :
                self.state_id = False
            else :
                self.zip = False
        return super(Company, self)._onchange_country_id_wrapper()
    
    @api.onchange('state_id')
    def _onchange_state(self) :
        #if self.state_id.country_id :
        #    self.country_id = self.state_id.country_id
        if self.country_id == self.env.ref('base.pe') :
            if self.city_id :
                self.city_id = False
            else :
                self.zip = self.state_id.code
        else :
            super(Company, self)._onchange_state()
    
    @api.onchange('city_id')
    def _onchange_city_id(self) :
        self.city = self.city_id.name
        if self.country_id == self.env.ref('base.pe') :
            if self.l10n_pe_district :
                self.l10n_pe_district = False
            else :
                self.zip = self.city_id.l10n_pe_code or self.state_id.code
    
    @api.onchange('l10n_pe_district')
    def _onchange_l10n_pe_district(self) :
        if self.country_id == self.env.ref('base.pe') :
            self.zip = self.l10n_pe_district.code or self.city_id.l10n_pe_code or self.state_id.code
    
    def _inverse_city_id(self) :
        for company in self :
            company.partner_id.city_id = company.city_id
    
    def _inverse_l10n_pe_district(self) :
        for company in self :
            company.partner_id.l10n_pe_district = company.l10n_pe_district
