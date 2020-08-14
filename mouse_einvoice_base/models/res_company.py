# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

DEFAULT_CERTIFICATE = b'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'

class Company(models.Model) :
    _inherit = 'res.company'
    
    @api.model
    def _get_default_digital_certificate(self) :
        return DEFAULT_CERTIFICATE
    
    beta_service = fields.Boolean(string='Beta Server', default=True)
    user_sol = fields.Char(string='SOL User', default='MODDATOS')
    pass_sol = fields.Char(string='SOL Password', default='MODDATOS')
    digital_certificate = fields.Binary(string='Digital Certificate', default=_get_default_digital_certificate)
    digital_certificate_filename = fields.Char(string='Digital Certificate Filename', default='123456.p12')
    digital_password = fields.Char(string='Digital Certificate Password', default='123456')
    
    def _localization_use_documents(self) :
        """ This method is to be inherited by localizations and return True if localization use documents """
        self.ensure_one()
        if self.country_id.code == 'PE' :
            return True
        else :
            return super(Company, self)._localization_use_documents()