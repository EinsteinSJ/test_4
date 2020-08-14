# -*- coding: utf-8 -*-

from . import models
from odoo import api, SUPERUSER_ID

def after_install(cr, registry) :
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('l10n_latam_base.it_vat').write({'active': True})
    env['res.partner'].search([('l10n_latam_identification_type_id','=',env.ref('l10n_pe.it_RUC').id)]).write({'l10n_latam_identification_type_id': env.ref('l10n_latam_base.it_vat').id})

def after_uninstall(cr, registry) :
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('l10n_latam_base.view_partner_latam_form').write({'active': True})
    env.ref('l10n_pe.it_RUC').write({'active': True})
