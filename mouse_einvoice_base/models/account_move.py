# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

from zipfile import ZipFile 
import base64
from io import BytesIO
import requests
from xml.dom.minidom import parse, parseString
import signxml
from lxml import etree
from OpenSSL import crypto
import qrcode

DEFAULT_ZIPCODE = '150101'

def crearqr(ver, box, bor, data) :
    qr = qrcode.QRCode(version=ver, error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=box, border=bor)
    qr.add_data(data)
    if ver is None :
        qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    return img

class AccountMove(models.Model) :
    _inherit = 'account.move'
    
    @api.model
    def _get_default_zipcode(self) :
        return DEFAULT_ZIPCODE
    
    @api.model
    def _get_default_einvoice_journal(self) :
        return self._get_default_journal()
    
    unsigned_xml = fields.Text(string='Unsigned Raw XML', copy=False)
    unsigned_xml_binary = fields.Binary(string='Unsigned XML', help='Unsigned XML representation of the invoice', copy=False)
    unsigned_xml_binary_filename = fields.Char(string='Unsigned XML Filename', copy=False)
    signed_xml = fields.Text(string='Signed Raw XML', copy=False)
    signed_xml_binary = fields.Binary(string='Signed XML', help='Signed XML representation of the invoice', copy=False)
    signed_xml_binary_filename = fields.Char(string='Signed XML Filename', copy=False)
    signed_xml_digest_value = fields.Text(string='Signed XML DigestValue', help='DigestValue of the XML digital signature', copy=False)
    sunat_digest_value = fields.Text(string='SUNAT DigestValue', help='DigestValue of the SUNAT answer', copy=False)
    sunat_answer = fields.Char(string='SUNAT Answer', help='Answer received from SUNAT', copy=False)
    sunat_code = fields.Char(string='SUNAT Response Code', help='Response code received from SUNAT', copy=False)
    sent_sunat = fields.Boolean(string='Sent to SUNAT', copy=False)
    sent_sunat_beta = fields.Boolean(string='Sent to SUNAT Beta', copy=False)
    einvoice_journal_id = fields.Many2one(comodel_name='account.journal', string='Invoice',
                                          required=True, readonly=True, states={'draft': [('readonly', False)]},
                                          domain="[('company_id', '=', company_id)]", default=_get_default_einvoice_journal, store=True)
    
    l10n_latam_document_type_id = fields.Many2one(string='Document Type', related='journal_id.l10n_latam_document_type_id', store=True, auto_join=False, copy=False)
    l10n_latam_document_type_credit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Credit Note Type', related='journal_id.l10n_latam_document_type_credit_id', readonly=False, store=True, copy=False)
    l10n_latam_document_type_debit_id = fields.Many2one(comodel_name='l10n_latam.document.type', string='Debit Note Type', related='journal_id.l10n_latam_document_type_debit_id', readonly=False, store=True, copy=False)
    
    credit_origin_id = fields.Many2one(comodel_name='account.move', string='Credited Invoice', readonly=True, copy=False)
    credit_note_ids = fields.One2many(comodel_name='account.move', inverse_name='credit_origin_id', string='Credit Notes', help='The credit notes created for this invoice')
    credit_note_count = fields.Integer(string='Number of Credit Notes', compute='_compute_credit_count')
    
    qr = fields.Text(string='QR Code Content', copy=False)
    qr_binary = fields.Binary(string='QR Code', copy=False)
    qr_binary_filename = fields.Char(string='QR Code Filename', default='qr.jpg', copy=False)
    
    def _generate_qr_data(self) :
        self.ensure_one()
        data = [self.company_id.partner_id.vat or '', self.journal_id.l10n_latam_document_type_id.code or ''] + self.name.split('-')
        data = data + [format(self.amount_tax or 0, '.2f'), format(self.amount_total or 0, '.2f'), self.invoice_date.strftime('%Y-%m-%d')]
        data = data + [self.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code or '', self.partner_id.vat or '']
        #lxml_doc = etree.fromstring(self.signed_xml.encode('utf-8'), parser=etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8'))
        #data = data + [lxml_doc.xpath('//ds:DigestValue', namespaces={'ds': 'http://www.w3.org/2000/09/xmldsig#'})[0].text, '']
        data = data + [self.signed_xml_digest_value, '']
        data = '|'.join(data)
        return data
    
    def generate_qr_base_64(self, data=False) :
        self.ensure_one()
        data = data or self._generate_qr_data()
        img = crearqr(ver=None, box=4, bor=2, data=data)
        buffered = BytesIO()
        img.save(buffered)
        img_string = base64.b64encode(buffered.getvalue())
        return img_string
    
    @api.depends('credit_note_ids')
    def _compute_credit_count(self) :
        credit_data = self.env['account.move'].read_group([('credit_origin_id', 'in', self.ids)], ['credit_origin_id'], ['credit_origin_id'])
        data_map = {datum['credit_origin_id'][0]: datum['credit_origin_id_count'] for datum in credit_data}
        for inv in self:
            inv.credit_note_count = data_map.get(inv.id, 0)
    
    def action_view_credit_notes(self) :
        self.ensure_one()
        tipo = self.type.split('_')[0] + '_refund'
        action = self.env.ref('account.action_move_' + tipo + '_type').read()[0]
        if self.credit_note_count > 1 :
            action['domain'] = [('credit_origin_id','in',self.ids)]
        else :
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            action['views'] = form_view + [(state, view) for state, view in action.get('views', [('form', 'form')]) if view != 'form']
            action['res_id'] = self.credit_note_ids.id
        return action
    
    def action_view_debit_notes(self) :
        action = super(AccountMove, self).action_view_debit_notes()
        action = self.env.ref('account.action_move_' + self.type + '_type').read()[0]
        if self.debit_note_count > 1 :
            action['domain'] = [('debit_origin_id','in',self.ids)]
        else :
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            action['views'] = form_view + [(state, view) for state, view in action.get('views', [('form', 'form')]) if view != 'form']
            action['res_id'] = self.debit_note_ids.id
        return action
    
    @api.depends('l10n_latam_available_document_type_ids')
    @api.depends_context('internal_type')
    def _compute_l10n_latam_document_type(self) :
        #Evil method that overwrites the document type
        pass
    
    #def _get_sequence_prefix(self) :
    #    """ If we use documents we update sequences only from journal """
    #    if self.l10n_latam_country_code == 'PE' :
    #        return super(models.Model, self)._get_sequence_prefix()
    #    else :
    #        return super(AccountMove, self)._get_sequence_prefix()
    
    @api.onchange('l10n_latam_document_type_id', 'l10n_latam_document_number')
    def _inverse_l10n_latam_document_number(self) :
        super(AccountMove, self)._inverse_l10n_latam_document_number()
        for rec in self.filtered('l10n_latam_document_type_id').filtered(lambda r: r.l10n_latam_document_number and r.l10n_latam_country_code == 'PE') :
            l10n_latam_document_number = len(str(rec.l10n_latam_document_type_id.doc_code_prefix)) + 1 #Support of False prefix
            l10n_latam_document_number = rec.name[l10n_latam_document_number:]
            if rec.journal_id.l10n_latam_document_type_id.code == '07' :
                rec.name = rec.journal_id.l10n_latam_document_type_credit_id.doc_code_prefix + l10n_latam_document_number
            elif rec.journal_id.l10n_latam_document_type_id.code == '08' :
                rec.name = rec.journal_id.l10n_latam_document_type_debit_id.doc_code_prefix + l10n_latam_document_number
            else :
                rec.name = rec.journal_id.l10n_latam_document_type_id.doc_code_prefix + l10n_latam_document_number
    
    def _get_document_type_sequence(self) :
        """ Method to be inherited by different localizations. """
        self.ensure_one()
        if self.l10n_latam_country_code == 'PE' :
            return self.journal_id.sequence_id
        else :
            return super(AccountMove, self)._get_document_type_sequence()
    
    @api.onchange('einvoice_journal_id')
    def onchange_einvoice_journal_id(self) :
        self.journal_id = self.einvoice_journal_id
        self.l10n_latam_document_type_id = self.einvoice_journal_id.l10n_latam_document_type_id
    
    @api.model
    def create(self, vals) :
        #TODO: create_multi
        if vals.get('journal_id') is not None :
            vals.update({'einvoice_journal_id': vals['journal_id']})
        elif vals.get('einvoice_journal_id') is not None :
            vals.update({'journal_id': vals['einvoice_journal_id']})
        current_journal = self.env['account.journal'].browse(vals.get('journal_id'))
        if current_journal.l10n_latam_document_type_id :
            vals['l10n_latam_document_type_id'] = current_journal.l10n_latam_document_type_id.id
        elif vals.get('l10n_latam_document_type_id') is not None :
            del vals['l10n_latam_document_type_id']
        if current_journal.l10n_latam_document_type_id.code == '07' :
            vals['l10n_latam_document_type_credit_id'] = current_journal.l10n_latam_document_type_credit_id.id
        elif vals.get('l10n_latam_document_type_credit_id') is not None :
            del vals['l10n_latam_document_type_credit_id']
        if current_journal.l10n_latam_document_type_id.code == '08' :
            vals['l10n_latam_document_type_debit_id'] = current_journal.l10n_latam_document_type_debit_id.id
        elif vals.get('l10n_latam_document_type_debit_id') is not None :
            del vals['l10n_latam_document_type_debit_id']
        res = super(AccountMove, self).create(vals)
        return res
    
    def write(self, values) :
        #TODO: Multi write (?)
        if values.get('journal_id') is not None :
            values.update({'einvoice_journal_id': values['journal_id']})
        elif values.get('einvoice_journal_id') is not None :
            values.update({'journal_id': values['einvoice_journal_id']})
        if values.get('journal_id') is not None :
            current_journal = self.env['account.journal'].browse(values.get('journal_id'))
            if current_journal.ids :
                if current_journal.l10n_latam_document_type_id :
                    values['l10n_latam_document_type_id'] = current_journal.l10n_latam_document_type_id.id
                elif self.l10n_latam_document_type_id :
                    values['l10n_latam_document_type_id'] = False
                elif values.get('l10n_latam_document_type_id') is not None :
                    del values['l10n_latam_document_type_id']
                if current_journal.l10n_latam_document_type_id.internal_type == 'credit_note' :
                    values['l10n_latam_document_type_credit_id'] = current_journal.l10n_latam_document_type_credit_id.id
                elif self.l10n_latam_document_type_credit_id :
                    values['l10n_latam_document_type_credit_id'] = False
                elif values.get('l10n_latam_document_type_credit_id') is not None :
                    del values['l10n_latam_document_type_credit_id']
                if current_journal.l10n_latam_document_type_id.internal_type == 'debit_note' :
                    values['l10n_latam_document_type_debit_id'] = current_journal.l10n_latam_document_type_debit_id.id
                elif self.l10n_latam_document_type_debit_id :
                    values['l10n_latam_document_type_debit_id'] = False
                elif values.get('l10n_latam_document_type_debit_id') is not None :
                    del values['l10n_latam_document_type_debit_id']
        res = super(AccountMove, self).write(values)
        return res
    
    def cifras_a_letras(self, numero, hay_mas) :
        lista_centena = ['',('CIEN','CIENTO'),'DOSCIENTOS','TRESCIENTOS','CUATROCIENTOS','QUINIENTOS','SEISCIENTOS','SETECIENTOS','OCHOCIENTOS','NOVECIENTOS']
        lista_decena = ['',('DIEZ','ONCE','DOCE','TRECE','CATORCE','QUINCE','DIECISEIS','DIECISIETE','DIECIOCHO','DIECINUEVE'),
                        ('VEINTE','VEINTI'),('TREINTA','TREINTA Y'),('CUARENTA', 'CUARENTA Y'),('CINCUENTA','CINCUENTA Y'),
                        ('SESENTA','SESENTA Y'),('SETENTA','SETENTA Y'),('OCHENTA','OCHENTA Y'),('NOVENTA','NOVENTA Y')]
        lista_unidad = ['',('UN','UNO'),'DOS','TRES','CUATRO','CINCO','SEIS','SIETE','OCHO','NUEVE']
        centena = int(numero / 100)
        decena = int((numero % 100) / 10)
        unidad = int(numero % 10)
        
        texto_centena = lista_centena[centena]
        if centena == 1 :
            texto_centena = texto_centena[int((decena+unidad)>0)]
        
        texto_decena = lista_decena[decena]
        if decena == 1 :
            texto_decena = texto_decena[unidad]
        elif decena > 1 :
            texto_decena = texto_decena[int(unidad>0)]
        
        texto_unidad = lista_unidad[unidad]
        if unidad == 1 :
            texto_unidad = texto_unidad[int(hay_mas)]
        if decena == 1 :
            texto_unidad = ''
        
        if decena > 0 :
            texto_centena = texto_centena + (texto_centena and (' ' + texto_decena) or texto_decena)
        texto_centena = texto_centena + (texto_centena and (' ' + texto_unidad) or texto_unidad)
        return texto_centena
    
    def monto_a_letras(self, numero) :
        #asume no negativo con hasta dos decimales
        indicador = [('',''),('MIL','MIL'),('MILLON','MILLONES'),('MIL','MIL'),('BILLON','BILLONES')]
        entero = int(numero)
        decimal = int((numero * 100) % 100)
        
        contador = 0
        numero_letras = ''
        
        while entero > 0 :
            millar = entero % 1000
            
            en_letras = self.cifras_a_letras(millar,(contador==0)).strip()
            
            #if millar == 0 :
            #    numero_letras = en_letras + (numero_letras and ' '+numero_letras or '')
            #elif millar == 1 :
            #    if contador %2 == 1 :
            #        numero_letras = indicador[contador][0] + (numero_letras and ' '+numero_letras or '')
            #    else :
            #        numero_letras = en_letras + ' ' + indicador[contador][0] + (numero_letras and ' '+numero_letras or '')
            #else :
            #    numero_letras = en_letras + ' ' + indicador[contador][1] + (numero_letras and ' '+numero_letras or '')
            numero_letras = (millar==1 and contador%2==1 and '' or (en_letras and (en_letras+' ') or '')) + (millar==0 and '' or indicador[contador][int(millar!=1)]) + (numero_letras and (' '+numero_letras) or '')
            
            contador = contador + 1
            entero = entero // 1000
        
        if not numero_letras :
            numero_letras = 'CERO'
        
        numero_letras = numero_letras + ' CON ' + str(decimal).rjust(2,'0') + '/100'
        return numero_letras
    
    def crear_xml_factura(self) :
        #Este es un método para Perú
        xml_doc = '''<?xml version="1.0" encoding="utf-8"?>
<Invoice
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ccts="urn:un:unece:uncefact:documentation:2"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
    xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID schemeAgencyName="PE:SUNAT">2.0</cbc:CustomizationID>
    <cbc:ProfileID
        schemeName="Tipo de Operacion"
        schemeAgencyName="PE:SUNAT"
        schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo51">'''
        xml_doc = xml_doc + '0101' #einvoice.51
        xml_doc = xml_doc + '''</cbc:ProfileID>
    <cbc:ID>'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:ID>
    <cbc:IssueDate>'''
        
        if not self.invoice_date :
            raise UserError(_('Please set a date for the invoice.'))
        
        xml_doc = xml_doc + self.invoice_date.strftime('%Y-%m-%d')
        xml_doc = xml_doc + '''</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:DueDate>'''
        xml_doc = xml_doc + self.invoice_date_due.strftime('%Y-%m-%d')
        xml_doc = xml_doc + '''</cbc:DueDate>
    <cbc:InvoiceTypeCode
        listAgencyName="PE:SUNAT"
        listName="Tipo de Documento"
        listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01"
        listID="0101"
        name="Tipo de Operacion"
        listSchemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo51">'''
        xml_doc = xml_doc + self.journal_id.l10n_latam_document_type_id.code #('''01''' if len(invoice.partner_id.vat) == 11 else '''03''')
        xml_doc = xml_doc + '''</cbc:InvoiceTypeCode>
    <cbc:Note
        languageLocaleID="1000">'''
        xml_doc = xml_doc + self.monto_a_letras(self.amount_total)
        xml_doc = xml_doc + '''</cbc:Note>
    <cbc:DocumentCurrencyCode
        listID="ISO 4217 Alpha"
        listName="Currency"
        listAgencyName="United Nations Economic Commission for Europe">'''
        
        moneda_nombre = self.currency_id.name
        
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''</cbc:DocumentCurrencyCode>
    <cbc:LineCountNumeric>'''
        xml_doc = xml_doc + str(len(self.invoice_line_ids))
        xml_doc = xml_doc + '''</cbc:LineCountNumeric>'''
    
    #    if ('''$cabecera["NRO_OTR_COMPROBANTE"]''' != "") :
    #        xml_doc = xml_doc + '''
    #<cac:OrderReference>
    #    <cbc:ID>''' + '''$cabecera["NRO_OTR_COMPROBANTE"]''' + '''</cbc:ID>
    #</cac:OrderReference>'''
    
    #    if ('''$cabecera["NRO_GUIA_REMISION"]''' != "") :
    #        xml_doc = xml_doc + '''
    #<cac:DespatchDocumentReference>
    #    <cbc:ID>''' + '''$cabecera["NRO_GUIA_REMISION"]''' + '''</cbc:ID>
    #    <cbc:IssueDate>''' + '''$cabecera["FECHA_GUIA_REMISION"]''' + '''</cbc:IssueDate>
    #    <cbc:DocumentTypeCode
    #        listAgencyName="PE:SUNAT"
    #        listName="Tipo de Documento"
    #        listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01">''' + '''$cabecera["COD_GUIA_REMISION"]''' + '''</cbc:DocumentTypeCode>
    #</cac:DespatchDocumentReference>'''
    
        xml_doc = xml_doc + '''
    <cac:Signature>
        <cbc:ID>'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>'''
        
        company_partner = self.company_id.partner_id
        vat = company_partner.vat
        l10n_pe_vat_code = company_partner.l10n_latam_identification_type_id
        if not l10n_pe_vat_code :
            raise UserError(_("You must set the identification type of the user's company"))
        l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
        if l10n_pe_vat_code != '6' :
            raise UserError(_("The user's company must have a VAT identification."))
        elif not vat or not vat.strip() :
            raise UserError(_("You must set the VAT identification number of the user's company."))
        elif not company_partner.check_vat_pe(vat.strip()) :
            raise UserError(_("The VAT identification number of the user's company is not valid."))
        if vat != vat.strip() :
            vat = vat.strip()
            company_partner.vat = vat
        registration_name = company_partner.registration_name
        if not registration_name or not registration_name.strip() :
            registration_name = company_partner.name
            if registration_name != registration_name.strip() :
                registration_name = registration_name.strip()
                company_partner.name = registration_name
            company_partner.registration_name = registration_name
        elif registration_name != registration_name.strip() :
            registration_name = registration_name.strip()
            company_partner.registration_name = registration_name
        commercial_name = company_partner.commercial_name
        if not commercial_name or not commercial_name.strip() :
            commercial_name = '-'
            company_partner.commercial_name = commercial_name
        elif commercial_name != commercial_name.strip() :
            commercial_name = commercial_name.strip()
            company_partner.commercial_name = commercial_name
        
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>'''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + '''</cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + commercial_name
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
            <cac:PartyTaxScheme>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cbc:CompanyID
                    schemeID="'''
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:CompanyID>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="'''
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                        schemeName="SUNAT:Identificador de Documento de Identidad"
                        schemeAgencyName="PE:SUNAT"
                        schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
                </cac:TaxScheme>
            </cac:PartyTaxScheme>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:ID
                        schemeName="Ubigeos"
                        schemeAgencyName="PE:INEI"/>
                    <cbc:AddressTypeCode
                        listAgencyName="PE:SUNAT"
                        listName="Establecimientos anexos">0000</cbc:AddressTypeCode>
                    <cbc:CityName><![CDATA['''
        
        default_district = self.env.ref('l10n_pe.district_pe_'+self._get_default_zipcode())
        
        if company_partner.country_id.code != 'PE' :
            company_partner.country_id = self.env.ref('base.pe')
        if not company_partner.state_id and not company_partner.city_id and company_partner.l10n_pe_district :
            company_partner.write({'state_id': default_district.city_id.state_id.id,
                                   'city_id': default_district.city_id.id,
                                   'l10n_pe_district': default_district.id,
                                   'zip': default_district.code})
        if not company_partner.state_id :
            company_partner.state_id = default_district.city_id.state_id
        if not company_partner.city_id :
            company_partner.city_id = (company_partner.state_id == default_district.city_id.state_id and default_district.city_id or self.env['res.city'].search([('state_id','=',company_partner.state_id.id)], order='l10n_pe_code asc', limit=1))
        if not company_partner.l10n_pe_district :
            company_partner.l10n_pe_district = (company_partner.city_id == default_district.city_id and default_district or self.env['l10n_pe.res.city.district'].search([('city_id','=',company_partner.city_id.id)], order='code asc', limit=1))
        if company_partner.zip != company_partner.l10n_pe_district.code :
            company_partner.zip = company_partner.l10n_pe_district.code
        
        xml_doc = xml_doc + company_partner.state_id.name.upper()
        xml_doc = xml_doc + ''']]></cbc:CityName>
                    <cbc:CountrySubentity><![CDATA['''
        xml_doc = xml_doc + company_partner.city_id.name.upper()
        xml_doc = xml_doc + ''']]></cbc:CountrySubentity>
                    <cbc:District><![CDATA['''
        xml_doc = xml_doc + company_partner.l10n_pe_district.name.upper()
        xml_doc = xml_doc + ''']]></cbc:District>
                    <cac:AddressLine>
                        <cbc:Line><![CDATA['''
        
        street = company_partner.street
        if not street or not street.strip() :
            street = '-' #_('Unknown Adress')
            company_partner.street = street
        elif street != street.strip() :
            street = street.strip()
            company_partner.street = street
        
        xml_doc = xml_doc + street.upper()
        xml_doc = xml_doc + ''']]></cbc:Line>
                    </cac:AddressLine>
                    <cac:Country>
                        <cbc:IdentificationCode
                            listID="ISO 3166-1"
                            listAgencyName="United Nations Economic Commission for Europe"
                            listName="Country">'''
        xml_doc = xml_doc + company_partner.country_id.code #'PE'
        xml_doc = xml_doc + '''</cbc:IdentificationCode>
                    </cac:Country>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        
        partner = self.partner_id
        vat = partner.vat
        l10n_pe_vat_code = partner.l10n_latam_identification_type_id
        if not l10n_pe_vat_code :
            if not vat or vat != vat.strip() :
                if not vat or not vat.strip() :
                    vat = '11111111'
                elif vat != vat.strip() :
                    vat = vat.strip()
                l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                partner.write({'l10n_latam_identification_type_id': l10n_pe_vat_code.id,
                               'vat': vat})
            else :
                l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                partner.l10n_latam_identification_type_id = l10n_pe_vat_code
            l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
        else :
            l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
            if not l10n_pe_vat_code :
                if not vat or vat != vat.strip() :
                    if not vat or not vat.strip() :
                        vat = '11111111'
                    elif vat != vat.strip() :
                        vat = vat.strip()
                    l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                    partner.write({'l10n_latam_identification_type_id': l10n_pe_vat_code.id,
                                   'vat': vat})
                else :
                    l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                    partner.l10n_latam_identification_type_id = l10n_pe_vat_code
                l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
            elif l10n_pe_vat_code != '6' :
                if not vat or not vat.strip() :
                    vat = '11111111'
                    partner.vat = vat
                elif vat != vat.strip() :
                    vat = vat.strip()
                    partner.vat = vat
            else :
                if not vat or not vat.strip() :
                    raise UserError(_('You must set the VAT identification number of the client.'))
                elif not partner.check_vat_pe(vat.strip()) :
                    raise UserError(_('The VAT identification number of the client is not valid.'))
                if vat != vat.strip() :
                    vat = vat.strip()
                    partner.vat = vat
        registration_name = partner.registration_name
        if not registration_name or not registration_name.strip() :
            registration_name = partner.name
            if registration_name != registration_name.strip() :
                registration_name = registration_name.strip()
                partner.name = registration_name
            partner.registration_name = registration_name
        elif registration_name != registration_name.strip() :
            registration_name = registration_name.strip()
            partner.registration_name = registration_name
        
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
            <cac:PartyTaxScheme>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cbc:CompanyID
                    schemeID="'''
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:CompanyID>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="'''
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                        schemeName="SUNAT:Identificador de Documento de Identidad"
                        schemeAgencyName="PE:SUNAT"
                        schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
                </cac:TaxScheme>
            </cac:PartyTaxScheme>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:ID
                        schemeName="Ubigeos"
                        schemeAgencyName="PE:INEI">'''
        
        if partner.country_id.code != 'PE' :
            partner.country_id = self.env.ref('base.pe')
        if not partner.state_id and not partner.city_id and partner.l10n_pe_district :
            partner.write({'state_id': default_district.city_id.state_id.id,
                           'city_id': default_district.city_id.id,
                           'l10n_pe_district': default_district.id,
                           'zip': default_district.code})
        if not partner.state_id :
            partner.state_id = default_district.city_id.state_id
        if not partner.city_id :
            partner.city_id = (partner.state_id == default_district.city_id.state_id and default_district.city_id or self.env['res.city'].search([('state_id','=',partner.state_id.id)], order='l10n_pe_code asc', limit=1))
        if not partner.l10n_pe_district :
            partner.l10n_pe_district = (partner.city_id == default_district.city_id and default_district or self.env['l10n_pe.res.city.district'].search([('city_id','=',partner.city_id.id)], order='code asc', limit=1))
        if partner.zip != partner.l10n_pe_district.code :
            partner.zip = partner.l10n_pe_district.code
        
        xml_doc = xml_doc + partner.zip
        xml_doc = xml_doc + '''</cbc:ID>
                    <cbc:CityName><![CDATA['''
        xml_doc = xml_doc + partner.state_id.name.upper()
        xml_doc = xml_doc + ''']]></cbc:CityName>
                    <cbc:CountrySubentity><![CDATA['''
        xml_doc = xml_doc + partner.city_id.name.upper()
        xml_doc = xml_doc + ''']]></cbc:CountrySubentity>
                    <cbc:District><![CDATA['''
        xml_doc = xml_doc + partner.l10n_pe_district.name.upper()
        xml_doc = xml_doc + ''']]></cbc:District>
                    <cac:AddressLine>
                        <cbc:Line><![CDATA['''
        
        street = partner.street
        if not street or not street.strip() :
            street = '-' #_('Unknown Adress')
            partner.street = street
        elif street != street.strip() :
            street = street.strip()
            partner.street = street
        
        xml_doc = xml_doc + street.upper()
        xml_doc = xml_doc + ''']]></cbc:Line>
                    </cac:AddressLine>
                    <cac:Country>
                        <cbc:IdentificationCode
                            listID="ISO 3166-1"
                            listAgencyName="United Nations Economic Commission for Europe"
                            listName="Country">'''
        xml_doc = xml_doc + partner.country_id.code #'PE'
        xml_doc = xml_doc + '''</cbc:IdentificationCode>
                    </cac:Country>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:AllowanceCharge>
        <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
        <cbc:AllowanceChargeReasonCode
            listName="Cargo/descuento"
            listAgencyName="PE:SUNAT"
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo53">'''
        xml_doc = xml_doc + '02' #einvoice.53
        xml_doc = xml_doc + '''</cbc:AllowanceChargeReasonCode>
        <cbc:MultiplierFactorNumeric>'''
        xml_doc = xml_doc + format(0, '.2f')
        xml_doc = xml_doc + '''</cbc:MultiplierFactorNumeric>
        <cbc:Amount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(0, '.2f')
        xml_doc = xml_doc + '''</cbc:Amount>
        <cbc:BaseAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(0, '.2f')
        xml_doc = xml_doc + '''</cbc:BaseAmount>
    </cac:AllowanceCharge>
    <cac:TaxTotal>
        <cbc:TaxAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount
                currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxableAmount>
            <cbc:TaxAmount
                currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxCategory>
                <cbc:ID
                    schemeID="UN/ECE 5305"
                    schemeName="Tax Category Identifier"
                    schemeAgencyName="United Nations Economic Commission for Europe">'''
        xml_doc = xml_doc + 'S'
        xml_doc = xml_doc + '''</cbc:ID>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="UN/ECE 5153"
                        schemeAgencyID="'''
        xml_doc = xml_doc + '6'
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + '1000'
        xml_doc = xml_doc + '''</cbc:ID>
                    <cbc:Name>'''
        xml_doc = xml_doc + 'IGV'
        xml_doc = xml_doc + '''</cbc:Name>
                    <cbc:TaxTypeCode>'''
        xml_doc = xml_doc + 'VAT'
        xml_doc = xml_doc + '''</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>'''
        
        #TOTAL=GRAVADA+IGV+EXONERADA
        #NO ENTRA GRATUITA(INAFECTA) NI DESCUENTO
        #SUB_TOTAL=PRECIO(SIN IGV) * CANTIDAD
        
        xml_doc = xml_doc + '''
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + '''</cbc:LineExtensionAmount>
        <cbc:TaxInclusiveAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxInclusiveAmount>
        <cbc:AllowanceTotalAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(0, '.2f')
        xml_doc = xml_doc + '''</cbc:AllowanceTotalAmount>
        <cbc:ChargeTotalAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(0, '.2f')
        xml_doc = xml_doc + '''</cbc:ChargeTotalAmount>
        <cbc:PayableAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + '''</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>'''
        
        for line in self.invoice_line_ids.filtered(lambda r: r.display_type==False) :
            moneda_name = line.currency_id.name or moneda_nombre
            
            xml_doc = xml_doc + '''
    <cac:InvoiceLine>
        <cbc:ID>'''
            xml_doc = xml_doc + str(line.id)
            xml_doc = xml_doc + '''</cbc:ID>
        <cbc:InvoicedQuantity
            unitCode="'''
            xml_doc = xml_doc + (('uom_id' in line) and line or line.product_id).uom_id.unece_code or 'NIU'
            xml_doc = xml_doc + '''"
            unitCodeListID="UN/ECE rec 20"
            unitCodeListAgencyName="United Nations Economic Commission for Europe">'''
            xml_doc = xml_doc + format(line.quantity, '.2f')
            xml_doc = xml_doc + '''</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount
            currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
                <cbc:PriceTypeCode
                    listName="Tipo de Precio"
                    listAgencyName="PE:SUNAT"
                    listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo16">'''
            xml_doc = xml_doc + '01' #einvoice.16
            xml_doc = xml_doc  + '''</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>
            <cbc:TaxAmount
                currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            
            price_tax = line.price_total - line.price_subtotal
            
            xml_doc = xml_doc + format(price_tax, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxableAmount>
                <cbc:TaxAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(price_tax, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:ID
                        schemeID="UN/ECE 5305"
                        schemeName="Tax Category Identifier"
                        schemeAgencyName="United Nations Economic Commission for Europe">'''
            xml_doc = xml_doc + (line.tax_ids.ids and line.tax_ids.mapped('l10n_pe_edi_unece_category')[0] or 'S')
            xml_doc = xml_doc + '''</cbc:ID>
                    <cbc:Percent>'''
            xml_doc = xml_doc + (line.tax_ids.ids and str(int(line.tax_ids.mapped('amount')[0]+0.5)) or '18')
            xml_doc = xml_doc + '''</cbc:Percent>
                    <cbc:TaxExemptionReasonCode
                        listAgencyName="PE:SUNAT"
                        listName="SUNAT:Codigo de Tipo de Afectación del IGV"
                        listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07">'''
            xml_doc = xml_doc + '10' #einvoice.07
            xml_doc = xml_doc + '''</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID
                            schemeID="UN/ECE 5153"
                            schemeName="Tax Scheme Identifier"
                            schemeAgencyName="United Nations Economic Commission for Europe">'''
            
            unece = (line.tax_ids.ids and line.tax_ids.mapped('l10n_pe_edi_tax_code')[0] or '1000')
            unece = self.env.ref('mouse_einvoice_sunat.einvoice_05_'+unece)
            
            xml_doc = xml_doc + unece.code
            xml_doc = xml_doc + '''</cbc:ID>
                        <cbc:Name>'''
            xml_doc = xml_doc + unece.impuesto #'IGV'
            xml_doc = xml_doc + '''</cbc:Name>
                        <cbc:TaxTypeCode>'''
            xml_doc = xml_doc + unece.un_5153 #'VAT'
            xml_doc = xml_doc + '''</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Description><![CDATA['''
            
            product = line.product_id.name
            if not product or not product.strip() :
                product = _('GENERIC')
                line.product_id.name = product
            elif product != product.strip() :
                product = product.strip()
                line.product_id.name = product
            
            xml_doc = xml_doc + product
            xml_doc = xml_doc + ''']]></cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID><![CDATA['''
            
            product = line.product_id.default_code
            if product and product != product.strip() :
                product = product.strip()
                line.product_id.default_code = product
            
            xml_doc = xml_doc + (product or 'G000')
            xml_doc = xml_doc + ''']]></cbc:ID>
            </cac:SellersItemIdentification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount
                currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
        </cac:Price>
    </cac:InvoiceLine>'''
        
        xml_doc = xml_doc + '''
</Invoice>'''
        
        resp = {'respuesta': 'ok', 'unsigned_xml': xml_doc}
        return resp
    
    def crear_xml_nota_credito(self) :
        #Este es un método para Perú
        xml_doc = '''<?xml version="1.0" encoding="utf-8"?>
<CreditNote
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ccts="urn:un:unece:uncefact:documentation:2"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
    xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"
    xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>2.0</cbc:CustomizationID>
    <cbc:ID>'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:ID>
    <cbc:IssueDate>'''
        xml_doc = xml_doc + self.invoice_date.strftime('%Y-%m-%d')
        xml_doc = xml_doc + '''</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:DocumentCurrencyCode>'''
        
        moneda_nombre = self.currency_id.name
        
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''</cbc:DocumentCurrencyCode>
    <cac:DiscrepancyResponse>
        <cbc:ReferenceID>'''
        xml_doc = xml_doc + self.credit_origin_id.name
        xml_doc = xml_doc + '''</cbc:ReferenceID>
        <cbc:ResponseCode>'''
        xml_doc = xml_doc + '10' #einvoice.07 (?)
        xml_doc = xml_doc + '''</cbc:ResponseCode>
        <cbc:Description><![CDATA['''
        xml_doc = xml_doc + (self.ref or (_('Credit note of %s') % (self.credit_origin_id.name)))
        xml_doc = xml_doc + ''']]></cbc:Description>
    </cac:DiscrepancyResponse>
    <cac:BillingReference>
        <cac:InvoiceDocumentReference>
            <cbc:ID>'''
        xml_doc = xml_doc + self.credit_origin_id.name
        xml_doc = xml_doc + '''</cbc:ID>
            <cbc:DocumentTypeCode>'''
        xml_doc = xml_doc + self.credit_origin_id.journal_id.l10n_latam_document_type_id.code
        xml_doc = xml_doc + '''</cbc:DocumentTypeCode>
        </cac:InvoiceDocumentReference>
    </cac:BillingReference>
    <cac:Signature>
        <cbc:ID>IDSignST</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>'''
        
        company_partner = self.company_id.partner_id
        vat = company_partner.vat
        l10n_pe_vat_code = company_partner.l10n_latam_identification_type_id
        if not l10n_pe_vat_code :
            raise UserError(_("You must set the identification type of the user's company"))
        l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
        if l10n_pe_vat_code != '6' :
            raise UserError(_("The user's company must have a VAT identification."))
        elif not vat or not vat.strip() :
            raise UserError(_("You must set the VAT identification number of the user's company."))
        elif not company_partner.check_vat_pe(vat.strip()) :
            raise UserError(_("The VAT identification number of the user's company is not valid."))
        if vat != vat.strip() :
            vat = vat.strip()
            company_partner.vat = vat
        registration_name = company_partner.registration_name
        if not registration_name or not registration_name.strip() :
            registration_name = company_partner.name
            if registration_name != registration_name.strip() :
                registration_name = registration_name.strip()
                company_partner.name = registration_name
            company_partner.registration_name = registration_name
        elif registration_name != registration_name.strip() :
            registration_name = registration_name.strip()
            company_partner.registration_name = registration_name
        commercial_name = company_partner.commercial_name
        if not commercial_name or not commercial_name.strip() :
            commercial_name = '-'
            company_partner.commercial_name = commercial_name
        elif commercial_name != commercial_name.strip() :
            commercial_name = commercial_name.strip()
            company_partner.commercial_name = commercial_name
        
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#SignatureSP</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + commercial_name
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:AddressTypeCode>'''
        xml_doc = xml_doc + '0001'
        xml_doc = xml_doc + '''</cbc:AddressTypeCode>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        
        partner = self.partner_id
        vat = partner.vat
        l10n_pe_vat_code = partner.l10n_latam_identification_type_id
        if not l10n_pe_vat_code :
            if not vat or vat != vat.strip() :
                if not vat or not vat.strip() :
                    vat = '11111111'
                elif vat != vat.strip() :
                    vat = vat.strip()
                l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                partner.write({'l10n_latam_identification_type_id': l10n_pe_vat_code.id,
                               'vat': vat})
            else :
                l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                partner.l10n_latam_identification_type_id = l10n_pe_vat_code
            l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
        else :
            l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
            if not l10n_pe_vat_code :
                if not vat or vat != vat.strip() :
                    if not vat or not vat.strip() :
                        vat = '11111111'
                    elif vat != vat.strip() :
                        vat = vat.strip()
                    l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                    partner.write({'l10n_latam_identification_type_id': l10n_pe_vat_code.id,
                                   'vat': vat})
                else :
                    l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                    partner.l10n_latam_identification_type_id = l10n_pe_vat_code
                l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
            elif l10n_pe_vat_code != '6' :
                if not vat or not vat.strip() :
                    vat = '11111111'
                    partner.vat = vat
                elif vat != vat.strip() :
                    vat = vat.strip()
                    partner.vat = vat
            else :
                if not vat or not vat.strip() :
                    raise UserError(_('You must set the VAT identification number of the client.'))
                elif not partner.check_vat_pe(vat.strip()) :
                    raise UserError(_('The VAT identification number of the client is not valid.'))
                if vat != vat.strip() :
                    vat = vat.strip()
                    partner.vat = vat
        registration_name = partner.registration_name
        if not registration_name or not registration_name.strip() :
            registration_name = partner.name
            if registration_name != registration_name.strip() :
                registration_name = registration_name.strip()
                partner.name = registration_name
            partner.registration_name = registration_name
        elif registration_name != registration_name.strip() :
            registration_name = registration_name.strip()
            partner.registration_name = registration_name
        
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:TaxTotal>
        <cbc:TaxAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount
                currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxableAmount>
            <cbc:TaxAmount
                currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxCategory>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="UN/ECE 5153"
                        schemeAgencyID="'''
        xml_doc = xml_doc + '6'
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + '1000'
        xml_doc = xml_doc + '''</cbc:ID>
                    <cbc:Name>'''
        xml_doc = xml_doc + 'IGV'
        xml_doc = xml_doc + '''</cbc:Name>
                    <cbc:TaxTypeCode>'''
        xml_doc = xml_doc + 'VAT'
        xml_doc = xml_doc + '''</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:PayableAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + '''</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>'''
        
        for line in self.invoice_line_ids.filtered(lambda r: r.display_type==False) :
            moneda_name = line.currency_id.name or moneda_nombre
            
            xml_doc = xml_doc + '''
    <cac:CreditNoteLine>
        <cbc:ID>'''
            xml_doc = xml_doc + str(line.id)
            xml_doc = xml_doc + '''</cbc:ID>
        <cbc:CreditedQuantity
            unitCode="'''
            xml_doc = xml_doc + (('uom_id' in line) and line or line.product_id).uom_id.unece_code or 'NIU'
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.quantity, '.2f')
            xml_doc = xml_doc + '''</cbc:CreditedQuantity>
        <cbc:LineExtensionAmount
            currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
                <cbc:PriceTypeCode>'''
            xml_doc = xml_doc + '01'
            xml_doc = xml_doc + '''</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>
            <cbc:TaxAmount
                currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            
            price_tax = line.price_total - line.price_subtotal
            
            xml_doc = xml_doc + format(price_tax, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxableAmount>
                <cbc:TaxAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(price_tax, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:Percent>'''
            xml_doc = xml_doc + (line.tax_ids.ids and str(int(line.tax_ids.mapped('amount')[0]+0.5)) or '18')
            xml_doc = xml_doc + '''</cbc:Percent>
                    <cbc:TaxExemptionReasonCode>'''
            xml_doc = xml_doc + '10' #einvoice.07
            xml_doc = xml_doc + '''</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID>'''
            
            unece = (line.tax_ids.ids and line.tax_ids.mapped('l10n_pe_edi_tax_code')[0] or '1000')
            unece = self.env.ref('mouse_einvoice_sunat.einvoice_05_'+unece)
            
            xml_doc = xml_doc + unece.code
            xml_doc = xml_doc + '''</cbc:ID>
                        <cbc:Name>'''
            xml_doc = xml_doc + unece.impuesto #'IGV'
            xml_doc = xml_doc + '''</cbc:Name>
                        <cbc:TaxTypeCode>'''
            xml_doc = xml_doc + unece.un_5153 #'VAT'
            xml_doc = xml_doc + '''</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Description><![CDATA['''
            
            product = line.product_id.name
            if not product or not product.strip() :
                product = _('GENERIC')
                line.product_id.name = product
            elif product != product.strip() :
                product = product.strip()
                line.product_id.name = product
            
            xml_doc = xml_doc + product
            xml_doc = xml_doc + ''']]></cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID><![CDATA['''
            
            product = line.product_id.default_code
            if product and product != product.strip() :
                product = product.strip()
                line.product_id.default_code = product
            
            xml_doc = xml_doc + (product or 'G000')
            xml_doc = xml_doc + ''']]></cbc:ID>
            </cac:SellersItemIdentification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount
                currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
        </cac:Price>
    </cac:CreditNoteLine>'''
        
        xml_doc = xml_doc + '''
</CreditNote>'''
        
        resp = {'respuesta': 'ok', 'unsigned_xml': xml_doc}
        return resp
    
    def crear_xml_nota_debito(self) :
        #Este es un método para Perú
        xml_doc = '''<?xml version="1.0" encoding="UTF-8"?>
<DebitNote
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ccts="urn:un:unece:uncefact:documentation:2"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
    xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"
    xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>2.0</cbc:CustomizationID>
    <cbc:ID>'''
        xml_doc = xml_doc + self.name
        xml_doc = xml_doc + '''</cbc:ID>
    <cbc:IssueDate>'''
        xml_doc = xml_doc + self.invoice_date.strftime('%Y-%m-%d')
        xml_doc = xml_doc + '''</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:DocumentCurrencyCode>'''
        
        moneda_nombre = self.currency_id.name
        
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''</cbc:DocumentCurrencyCode>
    <cac:DiscrepancyResponse>
        <cbc:ReferenceID>'''
        xml_doc = xml_doc + self.debit_origin_id.name
        xml_doc = xml_doc + '''</cbc:ReferenceID>
        <cbc:ResponseCode>'''
        xml_doc = xml_doc + '02' #einvoice.10 (?)
        xml_doc = xml_doc + '''</cbc:ResponseCode>
        <cbc:Description><![CDATA['''
        xml_doc = xml_doc + (self.ref or (_('Debit note of %s') % (self.debit_origin_id.name)))
        xml_doc = xml_doc + ''']]></cbc:Description>
    </cac:DiscrepancyResponse>
    <cac:BillingReference>
        <cac:InvoiceDocumentReference>
            <cbc:ID>'''
        xml_doc = xml_doc + self.debit_origin_id.name
        xml_doc = xml_doc + '''</cbc:ID>
            <cbc:DocumentTypeCode>'''
        xml_doc = xml_doc + self.debit_origin_id.journal_id.l10n_latam_document_type_id.code #self.debit_note_type.code
        xml_doc = xml_doc + '''</cbc:DocumentTypeCode>
        </cac:InvoiceDocumentReference>
    </cac:BillingReference>
    <cac:Signature>
        <cbc:ID>IDSignST</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>'''
        
        company_partner = self.company_id.partner_id
        vat = company_partner.vat
        l10n_pe_vat_code = company_partner.l10n_latam_identification_type_id
        if not l10n_pe_vat_code :
            raise UserError(_("You must set the identification type of the user's company"))
        l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
        if l10n_pe_vat_code != '6' :
            raise UserError(_("The user's company must have a VAT identification."))
        elif not vat or not vat.strip() :
            raise UserError(_("You must set the VAT identification number of the user's company."))
        elif not company_partner.check_vat_pe(vat.strip()) :
            raise UserError(_("The VAT identification number of the user's company is not valid."))
        if vat != vat.strip() :
            vat = vat.strip()
            company_partner.vat = vat
        registration_name = company_partner.registration_name
        if not registration_name or not registration_name.strip() :
            registration_name = company_partner.name
            if registration_name != registration_name.strip() :
                registration_name = registration_name.strip()
                company_partner.name = registration_name
            company_partner.registration_name = registration_name
        elif registration_name != registration_name.strip() :
            registration_name = registration_name.strip()
            company_partner.registration_name = registration_name
        commercial_name = company_partner.commercial_name
        if not commercial_name or not commercial_name.strip() :
            commercial_name = '-'
            company_partner.commercial_name = commercial_name
        elif commercial_name != commercial_name.strip() :
            commercial_name = commercial_name.strip()
            company_partner.commercial_name = commercial_name
        
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#SignatureSP</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA['''
        xml_doc = xml_doc + commercial_name
        xml_doc = xml_doc + ''']]></cbc:Name>
            </cac:PartyName>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:AddressTypeCode>'''
        xml_doc = xml_doc + '0001'
        xml_doc = xml_doc + '''</cbc:AddressTypeCode>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID="'''
        
        partner = self.partner_id
        vat = partner.vat
        l10n_pe_vat_code = partner.l10n_latam_identification_type_id
        if not l10n_pe_vat_code :
            if not vat or vat != vat.strip() :
                if not vat :
                    vat = '11111111'
                elif vat != vat.strip() :
                    vat = vat.strip()
                l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                partner.write({'l10n_latam_identification_type_id': l10n_pe_vat_code.id,
                               'vat': vat})
            else :
                l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                partner.l10n_latam_identification_type_id = l10n_pe_vat_code
            l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
        else :
            l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
            if not l10n_pe_vat_code :
                if not vat or vat != vat.strip() :
                    if not vat or not vat.strip() :
                        vat = '11111111'
                    elif vat != vat.strip() :
                        vat = vat.strip()
                    l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                    partner.write({'l10n_latam_identification_type_id': l10n_pe_vat_code.id,
                                   'vat': vat})
                else :
                    l10n_pe_vat_code = (len(vat) == 8 and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid'))
                    partner.l10n_latam_identification_type_id = l10n_pe_vat_code
                l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
            elif l10n_pe_vat_code != '6' :
                if not vat or not vat.strip() :
                    vat = '11111111'
                    partner.vat = vat
                elif vat != vat.strip() :
                    vat = vat.strip()
                    partner.vat = vat
            else :
                if not vat or not vat.strip() :
                    raise UserError(_('You must set the VAT identification number of the client.'))
                elif not partner.check_vat_pe(vat.strip()) :
                    raise UserError(_('The VAT identification number of the client is not valid.'))
                if vat != vat.strip() :
                    vat = vat.strip()
                    partner.vat = vat
        registration_name = partner.registration_name
        if not registration_name or not registration_name.strip() :
            registration_name = partner.name
            if registration_name != registration_name.strip() :
                registration_name = registration_name.strip()
                partner.name = registration_name
            partner.registration_name = registration_name
        elif registration_name != registration_name.strip() :
            registration_name = registration_name.strip()
            partner.registration_name = registration_name
        
        xml_doc = xml_doc + l10n_pe_vat_code
        xml_doc = xml_doc + '''"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">'''
        xml_doc = xml_doc + vat
        xml_doc = xml_doc + '''</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA['''
        xml_doc = xml_doc + registration_name
        xml_doc = xml_doc + ''']]></cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:TaxTotal>
        <cbc:TaxAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount
                currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxableAmount>
            <cbc:TaxAmount
                currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxCategory>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="UN/ECE 5153"
                        schemeAgencyID="'''
        xml_doc = xml_doc + '6'
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + '1000'
        xml_doc = xml_doc + '''</cbc:ID>
                    <cbc:Name>'''
        xml_doc = xml_doc + 'IGV'
        xml_doc = xml_doc + '''</cbc:Name>
                    <cbc:TaxTypeCode>'''
        xml_doc = xml_doc + 'VAT'
        xml_doc = xml_doc + '''</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:RequestedMonetaryTotal>
        <cbc:PayableAmount
            currencyID="'''
        xml_doc = xml_doc + moneda_nombre
        xml_doc = xml_doc + '''">'''
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + '''</cbc:PayableAmount>
    </cac:RequestedMonetaryTotal>'''
        
        for line in self.invoice_line_ids.filtered(lambda r: r.display_type==False) :
            moneda_name = line.currency_id.name or moneda_nombre
            
            xml_doc = xml_doc + '''
    <cac:DebitNoteLine>
        <cbc:ID>'''
            xml_doc = xml_doc + str(line.id)
            xml_doc = xml_doc + '''</cbc:ID>
        <cbc:DebitedQuantity
            unitCode="'''
            xml_doc = xml_doc + (('uom_id' in line) and line or line.product_id).uom_id.unece_code or 'NIU'
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.quantity, '.2f')
            xml_doc = xml_doc + '''</cbc:DebitedQuantity>
        <cbc:LineExtensionAmount
            currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
                <cbc:PriceTypeCode>'''
            xml_doc = xml_doc + '01'
            xml_doc = xml_doc + '''</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>        
            <cbc:TaxAmount
                currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            
            price_tax = line.price_total - line.price_subtotal
            
            xml_doc = xml_doc + format(price_tax, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxableAmount>
                <cbc:TaxAmount
                    currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(price_tax, '.2f')
            xml_doc = xml_doc + '''</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:Percent>'''
            xml_doc = xml_doc + (line.tax_ids and str(int(line.tax_ids.mapped('amount')[0]+0.5)) or '18')
            xml_doc = xml_doc + '''</cbc:Percent>
                    <cbc:TaxExemptionReasonCode>'''
            xml_doc = xml_doc + '10' #einvoice.07
            xml_doc = xml_doc + '''</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID>'''
            
            unece = (line.tax_ids and line.tax_ids.mapped('l10n_pe_edi_tax_code')[0] or '1000')
            unece = self.env.ref('mouse_einvoice_sunat.einvoice_05_'+unece)
            
            xml_doc = xml_doc + unece.code
            xml_doc = xml_doc + '''</cbc:ID>
                        <cbc:Name>'''
            xml_doc = xml_doc + unece.impuesto #'IGV'
            xml_doc = xml_doc + '''</cbc:Name>
                        <cbc:TaxTypeCode>'''
            xml_doc = xml_doc + unece.un_5153 #'VAT'
            xml_doc = xml_doc + '''</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        
        <cac:Item>
            <cbc:Description><![CDATA['''
            
            product = line.product_id.name
            if not product or not product.strip() :
                product = _('GENERIC')
                line.product_id.name = product
            elif product != product.strip() :
                product = product.strip()
                line.product_id.name = product
            
            xml_doc = xml_doc + product
            xml_doc = xml_doc + ''']]></cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID><![CDATA['''
            
            product = line.product_id.default_code
            if product and product != product.strip() :
                product = product.strip()
                line.product_id.default_code = product
            
            xml_doc = xml_doc + (product or 'G000')
            xml_doc = xml_doc + ''']]></cbc:ID>
            </cac:SellersItemIdentification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount
                currencyID="'''
            xml_doc = xml_doc + moneda_name
            xml_doc = xml_doc + '''">'''
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + '''</cbc:PriceAmount>
        </cac:Price>
    </cac:DebitNoteLine>'''
        
        xml_doc = xml_doc + '''
</DebitNote>'''
    
        #with open(ruta+".XML", "wb") as f:
        #    f.write(xml_doc.encode("utf-8"))
        resp = {'respuesta': 'ok', 'unsigned_xml': xml_doc}
        return resp
    
    def signature_xml(self, path, sign_path, sign_pass) :
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
        path = path.encode('utf-8')
        lxml_doc = etree.fromstring(path, parser=parser)
        
        signer = signxml.XMLSigner(method=signxml.methods.enveloped, signature_algorithm='rsa-sha1', digest_algorithm='sha1', c14n_algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
        
        sign_path_b64 = base64.b64decode(sign_path)
        if sign_path == base64.b64encode(sign_path_b64) :
            sign_path = sign_path_b64[:]
        
        try :
            sign_pkcs12 = crypto.load_pkcs12(sign_path, sign_pass)
        except crypto.SSLError as e :
            raise UserError(_('The digital certificate file is erroneous.\n' + str(e.message)))
        
        sign_cert = sign_pkcs12.get_certificate()
        sign_cert_cryptography = crypto.dump_certificate(crypto.FILETYPE_PEM, sign_cert).decode()
        #sign_cert_cryptography = sign_cert_cryptography.replace("-----END CERTIFICATE-----","").replace("-----BEGIN CERTIFICATE-----", "").replace("\n","")
        #sign_cert  s_cryptography = [sign_cert]
        
        sign_privatekey = sign_pkcs12.get_privatekey()
        sign_privatekey_cryptography = sign_privatekey.to_cryptography_key()
        
        signed_xml = signer.sign(lxml_doc, key=sign_privatekey_cryptography, cert=sign_cert_cryptography, passphrase=sign_pass)
        
        signed_string = etree.tostring(signed_xml).decode()
        ze = signed_string.find('<ds:Sign')
        ko = signed_string.rfind('</ds:Sign') + len('</ds:Signature>')
        signature_string = signed_string[ze:ko].replace('\n', '')
        
        doc = path.decode('utf-8') #etree.tostring(lxml_doc).decode()
        chu = doc.find('</ext:ExtensionContent>')
        xml_doc = doc[:chu] + signature_string + doc[chu:]
        if 'xml version' not in xml_doc :
            xml_doc = '<?xml version="1.0" encoding="utf-8"?>\n' + xml_doc
        ze = signature_string.find('<ds:DigestValue>')
        chu = len('<ds:DigestValue>')
        ko = signature_string.find('</ds:DigestValue>')
        digest_value = signature_string[ze+chu:ko]
        
        resp= {'respuesta': 'ok', 'hash_cpe': digest_value, 'signed_xml': xml_doc}
        
        return resp
    
    def enviar_documento(self, ruc, user_sol, pass_sol, file, filepath, path_ws) :
        soapURL = path_ws
        soapUser = user_sol
        soapPass = pass_sol
        xml_doc = '''<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
    xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ser="http://service.sunat.gob.pe" 
    xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
    <soapenv:Header>
        <wsse:Security>
            <wsse:UsernameToken>
                <wsse:Username>'''
        xml_doc = xml_doc + ruc + soapUser
        xml_doc = xml_doc + '''</wsse:Username>
                <wsse:Password>'''
        xml_doc = xml_doc + soapPass
        xml_doc = xml_doc + '''</wsse:Password>
            </wsse:UsernameToken>
        </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
        <ser:sendBill>
            <fileName>'''
        xml_doc = xml_doc + filepath
        xml_doc = xml_doc + '''.zip</fileName>
            <contentFile>'''
        
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'a') as zip_file:
            zip_file.writestr(filepath+'.XML', file.encode())
        zip_buffer.seek(0)
        xml_doc = xml_doc + base64.b64encode(zip_buffer.read()).decode('latin-1')
        
        xml_doc = xml_doc + '''</contentFile>
        </ser:sendBill>
    </soapenv:Body>
</soapenv:Envelope>'''
        headers = {'Content-type': '''text/xml;charset="utf-8"''',
                    'Accept': 'text/xml',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'SOAPAction': '',
                    'Content-length': str(len(xml_doc))}
        resp_code = requests.post(soapURL, data=xml_doc, headers=headers)
        content = parseString(resp_code.text)
        if len(content.getElementsByTagNameNS('*', 'applicationResponse')) > 0 :
            content = content.getElementsByTagNameNS('*', 'applicationResponse')[0].childNodes[0].nodeValue.strip()
            with ZipFile(BytesIO(base64.b64decode(content))) as thezip :
                for zipinfo in thezip.infolist() :
                    with thezip.open(zipinfo) as thefile:
                        respuesta_xml = thefile.read().decode()
            #Hash CDR
            content = parseString(respuesta_xml)
            mensaje = {'sunat_code': content.getElementsByTagNameNS('*', 'ResponseCode')[0].childNodes[0].nodeValue,
                        'msj_sunat': content.getElementsByTagNameNS('*', 'Description')[0].childNodes[0].nodeValue,
                        'hash_cdr': content.getElementsByTagNameNS('*', 'DigestValue')[0].childNodes[0].nodeValue}
        else :
            mensaje = {'sunat_code': content.getElementsByTagNameNS('*', 'faultcode')[0].childNodes[0].nodeValue,
                        'msj_sunat': content.getElementsByTagNameNS('*', 'faultstring')[0].childNodes[0].nodeValue,
                        'hash_cdr': ''}
        return mensaje
    
    def action_sign_xml(self) :
        for record in self.filtered(lambda r: r.l10n_latam_country_code == 'PE' and r.unsigned_xml and r.is_sale_document()) :
            invoice_company = record.company_id
            sign_path = invoice_company._get_default_digital_certificate()
            sign_pass = '123456'
            if (not invoice_company.beta_service) and invoice_company.user_sol != 'MODDATOS' and invoice_company.pass_sol != 'MODDATOS' :
                sign_path = invoice_company.digital_certificate
                sign_pass = invoice_company.digital_password
            signed_invoice_dictionary = record.signature_xml(record.unsigned_xml, sign_path, sign_pass)
            name_no_extension = record.unsigned_xml_binary_filename[:-4]
            record.write({'signed_xml': signed_invoice_dictionary['signed_xml'],
                          'signed_xml_binary': base64.b64encode(signed_invoice_dictionary['signed_xml'].encode()),
                          'signed_xml_binary_filename': name_no_extension + (invoice_company.beta_service and ' - BETA' or '') + '.xml',
                          'signed_xml_digest_value': signed_invoice_dictionary['hash_cpe']})
    
    def action_create_xml(self, name_no_extension=False) :
        for record in self.filtered(lambda r: r.l10n_latam_country_code == 'PE' and r.is_sale_document()) :
            unsigned_invoice_dictionary = {}
            tipo_veri = record.journal_id.l10n_latam_document_type_id.code
            if tipo_veri in ['01', '03'] :
                unsigned_invoice_dictionary = record.crear_xml_factura()
            elif tipo_veri == '07' :
                unsigned_invoice_dictionary = record.crear_xml_nota_credito()
            elif tipo_veri == '08' :
                unsigned_invoice_dictionary = record.crear_xml_nota_debito()
            if not name_no_extension :
                name_no_extension = record.company_id.partner_id.vat + '-' + tipo_veri + '-' + record.name
            if unsigned_invoice_dictionary :
                record.write({'unsigned_xml': unsigned_invoice_dictionary['unsigned_xml'],
                              'unsigned_xml_binary': base64.b64encode(unsigned_invoice_dictionary['unsigned_xml'].encode()),
                              'unsigned_xml_binary_filename': name_no_extension + '.xml'})
    
    def generate_qr(self) :
        for record in self.filtered(lambda r: r.l10n_latam_country_code == 'PE' and r.state=='posted' and r.is_sale_document()) :
            if not record.unsigned_xml :
                record.action_create_xml()
            if not record.signed_xml :
                record.action_sign_xml()
            elif record.company_id.beta_service :
                if 'BETA' not in record.signed_xml_binary_filename :
                    record.action_sign_xml()
            else :
                if 'BETA' in record.signed_xml_binary_filename :
                    record.action_sign_xml()
            data = record._generate_qr_data()
            img_string = record.generate_qr_base_64(data=data)
            record.write({'qr': data, 'qr_binary': img_string, 'qr_binary_filename': 'qr.jpg'})
    
    def post(self) :
        peru = self.filtered(lambda r: r.l10n_latam_country_code == 'PE' and r.is_sale_document())
        for record in peru :
            tipo_veri = record.journal_id.l10n_latam_document_type_id.code
            name_veri = record.journal_id.l10n_latam_document_type_id.name
            l10n_pe_vat_code = record.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code
            vat = record.partner_id.vat
            if tipo_veri == '07' :
                tipo_veri = record.journal_id.l10n_latam_document_type_credit_id.code
                name_veri = record.journal_id.l10n_latam_document_type_credit_id.name
            elif tipo_veri == '08' :
                tipo_veri = record.journal_id.l10n_latam_document_type_debit_id.code
                name_veri = record.journal_id.l10n_latam_document_type_debit_id.name
            
            if tipo_veri == '01' and (l10n_pe_vat_code != '6' or not vat or not vat.strip() or not record.partner_id.check_vat_pe(vat.strip())) :
                #Factura con DNI
                if len(self) == 1 :
                    raise UserError(_("You can't post an invoice of type %s for a client without a VAT identification number") % (name_veri))
                else :
                    raise UserError(_("You can't post the invoices because the client of an invoice of type %s doesn't have a VAT identification number") % (name_veri))
            elif tipo_veri == '03' :
                if l10n_pe_vat_code == '6' :
                    if len(self) == 1 :
                        raise UserError(_("You can't post an invoice of type %s for a client that has a VAT identification number") % (name_veri))
                    else :
                        raise UserError(_("You can't post the invoices because the client of an invoice of type %s has a VAT identification number") % (name_veri))
                elif not l10n_pe_vat_code :
                    name_veri = {}
                    if not vat or not vat.strip() :
                        vat = '11111111'
                        name_veri.update({'vat': vat})
                    elif vat != vat.strip() :
                        vat = vat.strip()
                        name_veri.update({'vat': vat})
                    l10n_pe_vat_code = (len(vat) == 8) and vat.isnumeric() and self.env.ref('l10n_pe.it_DNI') or self.env.ref('l10n_latam_base.it_fid')
                    name_veri.update({'l10n_latam_identification_type_id': l10n_pe_vat_code.id})
                    l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
                    record.partner_id.write(name_veri)
                else :
                    name_veri = {}
                    if not vat or not vat.strip() :
                        vat = '11111111'
                        name_veri.update({'vat': vat})
                        if l10n_pe_vat_code != '1' :
                            l10n_pe_vat_code = self.env.ref('l10n_pe.it_DNI')
                            name_veri.update({'l10n_latam_identification_type_id': l10n_pe_vat_code.id})
                            l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
                    elif vat != vat.strip() :
                        vat = vat.strip()
                        name_veri.update({'vat': vat})
                    if l10n_pe_vat_code == '1' and (len(vat) != 8 or not vat.isnumeric()) :
                        l10n_pe_vat_code = self.env.ref('l10n_latam_base.it_fid')
                        name_veri.update({'l10n_latam_identification_type_id': l10n_pe_vat_code.id})
                        l10n_pe_vat_code = l10n_pe_vat_code.l10n_pe_vat_code
                    if name_veri :
                        record.partner_id.write(name_veri)
        res = super(AccountMove, self).post()
        peru.action_create_xml()
        peru.generate_qr()
        return res
    
    def action_send_sunat(self) :
        if self.filtered(lambda r: r.state != 'posted') :
            if len(self) == 1 :
                raise UserError(_('You can only send a posted invoice to SUNAT.'))
            else :
                raise UserError(_('All invoices sent to SUNAT must be posted.\nPlease select only posted invoices.'))
        for record in self.filtered(lambda r: r.l10n_latam_country_code == 'PE' and r.is_sale_document()) :
            if not record.signed_xml :
                if not record.unsigned_xml :
                    record.action_create_xml()
                record.action_sign_xml()
            invoice_company = record.company_id
            user_sol = 'MODDATOS'
            pass_sol = 'MODDATOS'
            path_ws = 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService'
            if invoice_company.beta_service :
                if 'BETA' not in record.signed_xml_binary_filename :
                    record.action_sign_xml()
            else :
                if 'BETA' in record.signed_xml_binary_filename :
                    record.action_sign_xml()
                user_sol = invoice_company.user_sol
                pass_sol = invoice_company.pass_sol
                if user_sol != 'MODDATOS' and pass_sol != 'MODDATOS' :
                    path_ws = 'https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService?wsdl'
            ruc = invoice_company.partner_id.vat
            filepath = record.unsigned_xml_binary_filename[:-4]
            respuesta = record.enviar_documento(ruc, user_sol, pass_sol, record.signed_xml, filepath, path_ws)
            if respuesta['sunat_code'] == '0' :
                filepath = {'sunat_answer': respuesta['msj_sunat'],
                            'sunat_digest_value': respuesta['hash_cdr'],
                            'sunat_code' : respuesta['sunat_code']}
                if path_ws == 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService' :
                    filepath.update({'sent_sunat_beta': True})
                else :
                    filepath.update({'sent_sunat': True})
                record.write(filepath)
            else :
                filepath = {'sunat_answer': respuesta['sunat_code'] + ' - ' + respuesta['msj_sunat'],
                            'sunat_code' : respuesta['sunat_code']}
                if path_ws != 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService' :
                    filepath.update({'sent_sunat': False})
                record.write(filepath)
            self.env.cr.commit()
        return True
