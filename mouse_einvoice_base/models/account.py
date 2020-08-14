# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class AccountJournal(models.Model) :
    _inherit = 'account.journal'
    
    l10n_latam_document_type_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Document Type')
    l10n_latam_document_type_code = fields.Selection(related='l10n_latam_document_type_id.internal_type')
    l10n_latam_document_type_credit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Credit Note Type')
    l10n_latam_document_type_debit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Debit Note Type')
    
    @api.model
    def _create_sequence(self, vals, refund=False) :
        #issue with l10n_pe
        peru = self.env.ref('base.pe')
        peru_company = False
        vals_type = False
        if not vals.get('l10n_latam_use_documents') and self.env.company.country_id == peru :
            self.env.company.sudo().write({'country_id': False})
            peru_company = True
            if vals.get('type') in ['sale', 'purchase'] :
                vals_type = vals.get('type')
                vals.update({'type': 'general'})
        res = super(AccountJournal, self)._create_sequence(vals, refund=refund)
        if peru_company :
            self.env.company.sudo().write({'country_id': peru.id})
        if vals_type :
            vals.update({'type': vals_type})
        return res
    
    @api.onchange('l10n_latam_document_type_id')
    def _onchange_l10n_latam_document_type_id(self) :
        if not self.l10n_latam_document_type_id :
            self.l10n_latam_document_type_credit_id = False
            self.l10n_latam_document_type_debit_id = False
        elif self.l10n_latam_document_type_id.internal_type != 'credit_note' :
            self.l10n_latam_document_type_credit_id = False
        elif self.l10n_latam_document_type_id.internal_type != 'debit_note' :
            self.l10n_latam_document_type_debit_id = False
    
    @api.model
    def create(self, vals) :
        res = super(AccountJournal, self).create(vals)
        for record in res.filtered(lambda r: r.type in ['sale', 'purchase'] and r.l10n_latam_use_documents and r.l10n_latam_country_code == 'PE') :
            record.sequence = 5
            record.sequence_id.write({'padding': 8, 'l10n_latam_journal_id': record.id})
        return res

class AccountTax(models.Model) :
    _inherit = 'account.tax'
    
    l10n_pe_edi_tax_code = fields.Selection(selection_add=[('3000', 'IR - Income Tax'),
                                                           ('7152', 'ICBPER - Plastic Bag Consumption Tax')])
