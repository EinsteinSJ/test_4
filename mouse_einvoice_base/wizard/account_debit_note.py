# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class AccountDebitNote(models.TransientModel) :
    """
    Add Debit Note wizard: when you want to correct an invoice with a positive amount.
    Opposite of a Credit Note, but different from a regular invoice as you need the link to the original invoice.
    In some cases, also used to cancel Credit Notes
    """
    _inherit = 'account.debit.note'
    
    def _prepare_default_values(self, move) :
        res = super(AccountDebitNote, self)._prepare_default_values(move)
        res.update({'einvoice_journal_id': res['journal_id']})
        return res

    @api.onchange('move_ids')
    def _onchange_move_ids(self) :
        if self.move_ids :
            return {'domain': {'journal_id': [('l10n_latam_document_type_debit_id','in',self.move_ids.journal_id.l10n_latam_document_type_id.ids)]}}
