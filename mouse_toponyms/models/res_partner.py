# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class Partner(models.Model):
    _inherit = 'res.partner'
    
    def _get_default_street_format(self) :
        return '%(street_number)s/%(street_number2)s %(street_name)s'
    
    def _split_street_format(self, a) :
        if not a or not isinstance(a, str) or '%(' not in a or ')s' not in a or ')s' not in a[a.index('%('):] :
            return generate(self._get_default_street_format())
        else :
            b = a.split('%(')
            c = list(b)
            j = 1
            for d in b[1:] :
                e = d.split(')s', 1)
                if len(e) > 1 :
                    c = c[:j] + e + c[(j+1):]
                    j = j + 1
                j = j + 1
            if len(b) == j :
                return generate(self._get_default_street_format())
            else :
                return c
    
    def _set_street(self) :
        """Updates the street field.
        Writes the `street` field on the partners when one of the sub-fields in STREET_FIELDS
        has been touched"""
        peru = self.filtered(lambda r: r.country_id==self.env.ref('base.pe'))
        super(Partner, self-peru)._set_street()
        street_fields = self.get_street_fields()
        default_street_format = self._get_default_street_format()
        for partner in peru :
            street_format = partner.country_id.street_format or default_street_format
            street_format = self._split_street_format(street_format)
            street_values = list(range(1, len(street_format), 2))
            for field_name in street_fields :
                n = 0
                while n >= 0 :
                    try :
                        n = street_format.index(field_name, n+1)
                        if n % 2 != 0 and n in street_values :
                            street_values.remove(n)
                            street_format[n] = partner[field_name]
                    except ValueError :
                        n = -1
                if not street_values :
                    break
            for position in range(len(street_format)) :
                if position in street_values :
                    #if this triggers, try calling more fields in get_street_fields
                    street_format[position] = '%(' + street_format[position] + ')s'
                if not street_format[position] :
                    street_format[position] = ''
            street_values = list(range(len(street_format)-2, 0, -2))
            for position in street_values :
                if not street_format[position] :
                    street_format.pop(position+1)
                    street_format.pop(position)
                    if position == 1 :
                        street_format.pop(position-1)
            partner.street = ''.join(street_format) or False
    
    @api.depends('street')
    def _split_street(self) :
        """Splits street value into sub-fields.
        Recomputes the fields of STREET_FIELDS when `street` of a partner is updated"""
        peru = self.filtered(lambda r: r.country_id==self.env.ref('base.pe'))
        super(Partner, self-peru)._split_street()
        for partner in peru :
            partner['street_name'] = partner.street
            partner['street_number'] = None
            partner['street_number2'] = None
    
    #See self._onchange_methods without this installed
    @api.onchange('country_id')
    def _onchange_country(self) :
        if self.state_id :
            self.state_id = False
        else :
            self.zip = False
    
    @api.onchange('country_id')
    def _onchange_country_id(self) :
        pass
    
    @api.onchange('state_id')
    def _onchange_state(self) :
        if self.city_id :
            self.city_id = False
        else :
            self.zip = self.state_id.code
    
    @api.onchange('city_id')
    def _onchange_city_id(self) :
        self.city = self.city_id.name
        if self.l10n_pe_district :
            self.l10n_pe_district = False
        else :
            self.zip = self.city_id.l10n_pe_code or self.state_id.code
    
    @api.onchange('l10n_pe_district')
    def _onchange_l10n_pe_district(self) :
        self.zip = self.l10n_pe_district.code or self.city_id.l10n_pe_code or self.state_id.code
    
    def write(self, vals) :
        res = super(Partner, self).write(vals)
        #if 'street' not in vals and ('street_name' in vals or 'street_number' in vals or 'street_number2' in vals) :
        #    self._set_street()
        return res
    
    # New functions for the new fields
    @api.model
    def _get_address_format(self) :
        res = self.country_id.code == 'PE' and '%(street)s\n%(district_name)s - %(city_name)s - %(state_name)s - %(zip)s\n%(country_name)s' or super(Partner, self)._get_address_format()
        return res
    
    def _display_address(self, without_company=False) :
        '''
        The purpose of this function is to build and return an address formatted accordingly to the
        standards of the country where it belongs.
        :param address: browse record of the res.partner to format
        :returns: the address formatted in a display that fit its country habits (or the default ones
            if not country is specified)
        :rtype: string
        '''
        # get the information that will be injected into the display format
        # get the address format (replace the one from l10n_pe)
        address_format = self._get_address_format()
        args = {
            'district_code': self.l10n_pe_district.code or '',
            'district_name': self.l10n_pe_district.name or '',
            'city_code': self.city_id.l10n_pe_code or '',
            'city_name': self.city_id.name or '',
            'state_code': self.state_id.code or '',
            'state_name': self.state_id.name or '',
            'country_code': self.country_id.code or '',
            'country_name': self._get_country_name() or '',
            'company_name': self.commercial_company_name or '',
        }
        for field in self._formatting_address_fields():
            args[field] = getattr(self, field) or ''
        if without_company:
            args['company_name'] = ''
        elif self.mapped('commercial_company_name') :
            address_format = '%(company_name)s\n' + address_format
        return address_format % args
