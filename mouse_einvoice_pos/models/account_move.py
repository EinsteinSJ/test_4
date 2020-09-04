# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, Warning

class AccountMove(models.Model) :
    _inherit = 'account.move'
    
    def post(self) :
        for record in self.filtered(lambda r: r.l10n_latam_country_code == 'PE') :
            if record.pos_order_ids.ids :
                vat = record.partner_id.vat
                if not vat :
                    vat = '11111111'
                    record.partner_id.vat = vat
                elif vat != vat.strip() :
                    vat = vat.strip()
                    record.partner_id.vat = vat
                if vat.isnumeric() and len(vat) == 11 and record.partner_id.check_vat_pe(vat) :
                    record.partner_id.l10n_latam_identification_type_id = self.env.ref('l10n_latam_base.it_vat')
                    diario = self.env['account.journal'].search([('company_id','=',record.company_id.id),
                                                                 ('type','=','sale'),
                                                                 ('l10n_latam_use_documents','!=',False),
                                                                 ('l10n_latam_document_type_id','=',self.env.ref('mouse_einvoice_base.l10n_pe_document_01').id)], limit=1)
                    if diario :
                        record.einvoice_journal_id = diario
                else :
                    if vat.isnumeric() and len(vat) == 8 :
                        record.partner_id.l10n_latam_identification_type_id = self.env.ref('l10n_pe.it_DNI')
                    else :
                        record.partner_id.l10n_latam_identification_type_id = self.env.ref('l10n_latam_base.it_fid')
                    diario = self.env['account.journal'].search([('company_id','=',record.company_id.id),
                                                                 ('type','=','sale'),
                                                                 ('l10n_latam_use_documents','!=',False),
                                                                 ('l10n_latam_document_type_id','=',self.env.ref('mouse_einvoice_base.l10n_pe_document_03').id)], limit=1)
                    if diario :
                        record.einvoice_journal_id = diario
        res = super(AccountMove, self).post()
        return res
