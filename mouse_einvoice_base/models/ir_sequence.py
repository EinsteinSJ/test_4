# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class IrSequence(models.Model) :
    _inherit = 'ir.sequence'
    
    l10n_latam_document_type_id = fields.Many2one(compute='_compute_l10n_latam_document_type_id', store=True, readonly=False)
    l10n_latam_document_type_credit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Credit Note Type', compute='_compute_l10n_latam_document_type_credit_id', store=True, readonly=False)
    l10n_latam_document_type_debit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Debit Note Type', compute='_compute_l10n_latam_document_type_debit_id', store=True, readonly=False)
    
    @api.depends('l10n_latam_journal_id', 'l10n_latam_journal_id.l10n_latam_document_type_id')
    def _compute_l10n_latam_document_type_id(self) :
        for record in self :
            record.l10n_latam_document_type_id = record.l10n_latam_journal_id.l10n_latam_country_code == 'PE' and record.l10n_latam_journal_id.l10n_latam_document_type_id
    
    @api.depends('l10n_latam_journal_id', 'l10n_latam_journal_id.l10n_latam_document_type_credit_id')
    def _compute_l10n_latam_document_type_credit_id(self) :
        for record in self :
            record.l10n_latam_document_type_credit_id = record.l10n_latam_journal_id.l10n_latam_country_code == 'PE' and record.l10n_latam_journal_id.l10n_latam_document_type_credit_id
    
    @api.depends('l10n_latam_journal_id', 'l10n_latam_journal_id.l10n_latam_document_type_debit_id')
    def _compute_l10n_latam_document_type_debit_id(self) :
        for record in self :
            record.l10n_latam_document_type_debit_id = record.l10n_latam_journal_id.l10n_latam_country_code == 'PE' and record.l10n_latam_journal_id.l10n_latam_document_type_debit_id
