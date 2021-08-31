# -*- encoding: utf-8 -*-
from openerp import api, fields, models, _


class res_partner_bank(models.Model):
    _inherit = 'res.partner.bank'

    @api.one
    def _get_take_digits(self):        
        self.last_acc_number = self.acc_number and len(self.acc_number) >=4 and self.acc_number[-4:] or False
        
    clabe           = fields.Char(string='Clabe Interbancaria', size=64, required=False)
    last_acc_number = fields.Char(compute='_get_take_digits', string="Ultimos 4 digitos")
    currency2_id    = fields.Many2one('res.currency', string='Currency2')
    reference       = fields.Char(string='Reference', size=64, help='Reference used in this bank')


    _sql_constraints = [
        ('unique_number', 'CHECK(1=1)', 'Account Number must be unique'),
    ]

### Datos Bancarios en XML  Ger ###
class ResBank(models.Model):
    _name = 'res.bank'
    _inherit ='res.bank'

    vat = fields.Char('RFC', size=64)

### FIN  Ger ###