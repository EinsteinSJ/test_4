# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning
import requests

def buscarruc(ruc) :
    url = 'http://services.wijoata.com/consultar-ruc/api/ruc/%s' % (ruc)
    headers = {'Content-Type':'application/json'}
    res = {'error':True, 'message':None, 'data':{}}
    try :
        response = requests.post(url, timeout=10)
    except :
        res['message'] = 'Error en la conexion'
    if not res['message'] :
        if response.status_code == 200 :
            try :
                res['data'] = response.json()
            except :
                res['message'] = 'Error en el servicio'
            if not res['message'] :
                if res['data']['status'] == 1 :
                    res['error'] = False
                else :
                    res['message'] = 'Error en los datos'
        else :
            res['message'] = 'Error en la respuesta'
    return res

def buscardni(dni) :
    url = 'http://luisrojas.hol.es/2ren/tutorialesexcel.php'
    headers = {'Content-Type':'application/x-www-form-urlencoded'}
    data = 'dni=%s&token=tutorialesexcel.com' % (dni)
    res = {'error':True, 'message':None, 'data':{}}
    try :
        response = requests.post(url, headers=headers, data=data, timeout=10)
    except :
        res['message'] = 'Error en la conexion'
    if not res['message'] :
        if response.status_code == 200 :
            if '|' in response.text :
                datos = response.text.split('|')
                if len(datos) == 5 :
                    res['data'] = {'dni': datos[0],
                                   'digito': datos[1],
                                   'ape_paterno': datos[2],
                                   'ape_materno': datos[3],
                                   'nombres': datos[4]}
                    res['error'] = False
                else :
                    res['message'] = 'Error en los datos'
            else :
                res['message'] = 'Error en el servicio'
        else :
            res['message'] = 'Error en la respuesta'
    return res

class Partner(models.Model) :
    _inherit = 'res.partner'
    
    def _get_default_pe_zip(self) :
        return '150101'
    
    def _get_default_l10n_latam_identification_type_id(self, module=False, xml_id=False) :
        if not module or not xml_id :
            module = 'l10n_latam_base'
            xml_id = 'it_vat'
        return self.env.ref('.'.join([module, xml_id]))
    
    commercial_name = fields.Char(string='Commercial name')
    registration_name = fields.Char(string='Registration name')
    #l10n_latam_identification_type_id = fields.Many2one('_get_default_l10n_latam_identification_type_id')
    #vat = fields.Char(string='Nro. Doc. Id.')
    sunat_state = fields.Selection(string='SUNAT state', selection=[('known','Known'),('unknown','Unknown')])
    first_surname = fields.Char(string='First surname')
    second_surname = fields.Char(string='Second surname')
    given_names = fields.Char(string='Given name(s)')
    
    @api.onchange('name')
    def _cambio_nombre_razon_social(self) :
        self.registration_name = self.name
        self.first_surname = False
        self.second_surname = False
        self.given_names = False
    
    def _get_name(self) :
        name = super(Partner, self)._get_name()
        #if self.vat :
        #    if self._context.get('show_vat') :
        #        name = name[:-(len(self.vat) + 3)]
        #    name = '%s ‒ %s' % (self.vat, name) #uncommon hyphen
        #if self.commercial_name :
        #    name = '%s ‒ %s' % (name, self.commercial_name) #uncommon hyphen
        return name
    
    def name_get(self) :
        res = super(Partner, self).name_get()
        #new_res = res[:]
        #for old_name in res :
        #    new_res.remove(old_name)
        #    new_name = list(old_name)
        #    if isinstance(new_name[0], int) and self.search([('id','=',new_name[0])]) :
        #        new_name.append(self.browse(new_name[0]).vat)
        #        if new_name[2] and (' ‒ ' + new_name[2]) not in new_name[1] :
        #            new_name[1] = new_name[1] + ' ‒ ' + new_name[2] #uncommon hyphen
        #        new_name = new_name[:2]
        #    new_res.append(tuple(new_name))
        #return new_res
        return res
    
    @api.onchange('l10n_latam_identification_type_id','vat')
    def vat_change(self) :
        self._update_l10n_latam_vat()
    
    def _update_l10n_latam_vat(self) :
        if self.vat and self.vat.strip() and self.l10n_latam_identification_type_id :
            cif = self.vat.strip()
            district_id_default = self.env.ref('l10n_pe.district_pe_' + self._get_default_pe_zip())
            if self.l10n_latam_identification_type_id.l10n_pe_vat_code == '1' :
                self.first_surname = False
                self.second_surname = False
                self.given_names = False
                if len(cif) == 8 and cif.isdigit() :
                    #cif = 'El DNI' + (len(cif) != 8 and ' debe tener 8 caracteres' or '') + ((len(cif) != 8 and not cif.isdigit()) and ' y' or '') + ((not cif.isdigit()) and ' solo debe poseer caracteres numéricos' or '')
                    #raise Warning(cif)
                    d = buscardni(cif)
                    if not d['error'] :
                        d = d['data']
                        self.name = '%s %s %s' % (d['ape_paterno'], d['ape_materno'], d['nombres'])
                        self.first_surname = d['ape_paterno'] or False
                        self.second_surname = d['ape_materno'] or False
                        self.given_names = d['nombres'] or False
                        self.registration_name = '%s %s %s' % (d['ape_paterno'], d['ape_materno'], d['nombres'])
                        self.commercial_name = False
                        #self.street_name = False
                        self.is_company = False
                        self.country_id = district_id_default.city_id.country_id
                        self.state_id = district_id_default.city_id.state_id
                        self.city_id = district_id_default.city_id
                        self.l10n_pe_district = district_id_default
                        self.zip = district_id_default.code
            elif self.l10n_latam_identification_type_id.l10n_pe_vat_code == '6' :
                self.first_surname = False
                self.second_surname = False
                self.given_names = False
                if len(cif) == 11 and cif.isdigit() :
                    #cif = 'El RUC' + (len(cif) != 11 and ' debe tener 11 caracteres' or '') + ((len(cif) != 11 and not cif.isdigit()) and ' y' or '') + ((not cif.isdigit()) and ' solo debe poseer caracteres numéricos' or '')
                    #raise Warning(cif)
                    if not self.check_vat_pe(cif) :
                        #raise Warning('El RUC ingresado no es válido')
                        d = buscarruc(cif)
                        if not d['error'] :
                            d = d['data']
                            if d['ubigeo'] and len(d['ubigeo']) == 6 :
                                d['ubigeo'] = district_id_default.search([('code','=',d['ubigeo'])], limit=1)
                                if d['ubigeo'] :
                                    district_id_default = d['ubigeo']
                            self.name = d['razonSocial']
                            self.registration_name = d['razonSocial']
                            self.commercial_name = False
                            self.street_name = d['direccion'] or '-'
                            self.is_company = True
                            self.country_id = district_id_default.city_id.country_id
                            self.state_id = district_id_default.city_id.state_id
                            self.city_id = district_id_default.city_id
                            self.l10n_pe_district = district_id_default
                            self.zip = district_id_default.code
    
    def update_l10n_latam_vat(self) :
        for record in self.filtered(lambda r: r.vat and r.vat.strip() and r.l10n_latam_identification_type_id) :
            record._update_l10n_latam_vat()
        return True
