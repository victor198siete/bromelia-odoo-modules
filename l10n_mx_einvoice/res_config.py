# -*- coding: utf-8 -*-

from openerp import api, fields, models, _, release

class AccountConfigSettings(models.TransientModel):
    if release.major_version in ("9.0", "10.0"):
        _inherit = 'account.config.settings'
    elif release.major_version in ("11.0"):
        _inherit = 'res.config.settings'
    
    pac         = fields.Selection(string="PAC", related='company_id.pac')
    pac_user    = fields.Char(string="Usuario PAC", related='company_id.pac_user')
    pac_password= fields.Char(string="Contraseña PAC", related='company_id.pac_password')
    pac_testing = fields.Boolean(string="Timbrado en Pruebas", related='company_id.pac_testing')
    validate_schema = fields.Boolean(string="Validar Esquema XSD en Servidor Local", related='company_id.validate_schema' )
