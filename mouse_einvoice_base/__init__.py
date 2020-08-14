# -*- coding: utf-8 -*-

from . import models
from . import wizard
from odoo import api, SUPERUSER_ID

def after_uninstall(cr, registry) :
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('l10n_latam_invoice_document.report_invoice_document').write({'active': True})
