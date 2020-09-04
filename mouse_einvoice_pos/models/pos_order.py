# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, Warning

class PosOrder(models.Model) :
    _inherit = 'pos.order'
    
    def invoice_data_get(self) :
        invoice = self.sudo().account_move
        invoice_data = invoice.read(['partner_id', 'l10n_latam_document_type_id', 'name', 'amount_tax', 'amount_untaxed', 'amount_total', 'company_id'])
        if invoice :
            invoice_data = invoice_data[0]
            invoice_data['partner_id'] = invoice.partner_id.read(['l10n_latam_identification_type_id', 'name', 'registration_name', 'vat', 'commercial_name'])[0]
            invoice_data['company_id'] = invoice.company_id.partner_id.read(['name', 'registration_name', 'vat', 'commercial_name'])[0]
            invoice_data['partner_id']['l10n_latam_identification_type_id'] = invoice.partner_id.l10n_latam_identification_type_id.read(['l10n_pe_vat_code', 'name'])[0]
            invoice_data['l10n_latam_document_type_id'] = invoice.journal_id.l10n_latam_document_type_id.read(['code', 'name'])[0]
            try :
                #invoice_data['qr_code'] = invoice.generate_qr_base_64()
                invoice_data['qr_code'] = invoice.qr_binary
            except :
                invoice_data['qr_code'] = False
            invoice_data = [{'account_move': [invoice.ids[0], invoice_data]}]
        return invoice_data
