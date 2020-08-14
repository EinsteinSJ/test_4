# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class AccountTaxTemplate(models.Model) :
    _inherit = 'account.tax.template'
    
    l10n_pe_edi_tax_code = fields.Selection(selection_add=[('3000', 'IR - Income Tax'),
                                                           ('7152', 'ICBPER - Plastic Bag Consumption Tax')])
