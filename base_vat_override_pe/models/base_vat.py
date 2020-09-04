# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, Warning

class Partner(models.Model) :
    _inherit = 'res.partner'
    
    def check_vat_pe(self, vat) :
        res = super(Partner, self).check_vat_pe(vat)
        if not res and vat.isdigit() and (len(vat) != 11 or (self and len(self) == 1 and self.l10n_latam_identification_type_id.l10n_vat_pe_code != '6')) :
            res = True
        return res
