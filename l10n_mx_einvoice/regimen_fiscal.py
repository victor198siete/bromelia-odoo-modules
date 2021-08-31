# -*- encoding: utf-8 -*-

from openerp import api, fields, models, _


class AccountRegimenFiscal(models.Model):
    _name = 'regimen.fiscal'
    _description = 'Regimen Fiscal'
    _order = 'name'


    name        = fields.Char(string='Regimen Fiscal', size=128, required=True)
    description = fields.Text('Descripcion')
