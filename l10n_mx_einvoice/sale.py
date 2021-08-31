# -*- encoding: utf-8 -*-

from openerp import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"    
    '''Inherit sale order to add a new field, Payment Terms'''
    
    acc_payment = fields.Many2one('res.partner.bank', string='Cuenta Bancaria', readonly=True, 
                                  states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, 
                                  help='Is \
            the account with which the client pays the invoice, if not know \
            which account will used for pay leave empty and the XML will show \
            "Unidentified".')
    
    pay_method_id = fields.Many2one('pay.method', string='Forma de Pago', readonly=True, 
                                  states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, 
                                  help='Indicates the way it was paid or will be paid the invoice, \
            where the options could be: check, bank transfer, reservoir in \
            account bank, credit card, cash etc. If not know as will be paid \
            the invoice, leave empty and the XML show “Unidentified”.')

    uso_cfdi_id = fields.Many2one('sat.uso.cfdi', 'Uso CFDI', readonly=True, 
                                  states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, 
                                  required=False, help='Define el motivo de la compra.', ) 
    
