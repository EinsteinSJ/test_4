# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class AccountMoveReversal(models.TransientModel) :
    _inherit = 'account.move.reversal'
    
    #l10n_latam_document_type_id = fields.Many2one(related='journal_id.l10n_latam_document_type_id')
    #journal_id = fields.Many2one(required=True)
    
    def _prepare_default_reversal(self, move) :
        res = super(AccountMoveReversal, self)._prepare_default_reversal(move)
        if move.type in ('out_invoice', 'in_invoice') :
            res.update({'credit_origin_id': move.id, 'einvoice_journal_id': res['journal_id']})
        return res
    
    @api.onchange('move_id')
    def _onchange_move_id(self) :
        if self.move_id.l10n_latam_use_documents :
            res = super(AccountMoveReversal, self)._onchange_move_id()
            if self.move_id.l10n_latam_country_code == 'PE' :
                l10n_latam_document_type_ids = self.move_id.l10n_latam_document_type_id.ids
                if l10n_latam_document_type_ids :
                    res['domain'].update({'journal_id': [('l10n_latam_document_type_credit_id','in',l10n_latam_document_type_ids), ('company_id','=',self.move_id.company_id.id)]})
            return res
