# -*- encoding: utf-8 -*-

from openerp import api, fields, models, _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        res = super(PurchaseOrder, self).onchange_partner_id()
        if self.partner_id:
            bank_partner_id = self.env['res.partner.bank'].search([('partner_id', '=', self.partner_id.parent_id and self.partner_id.parent_id.id or self.partner_id.id)])
            if bank_partner_id:
                self.acc_payment = bank_partner_id[0].id or False
            self.pay_method_id = (self.partner_id.parent_id and self.partner_id.parent_id.pay_method_id) or \
                                 (self.partner_id.pay_method_id and self.partner_id.pay_method_id) or False
        return res


    acc_payment = fields.Many2one('res.partner.bank', string='Cuenta Bancaria',
                                readonly=True, states={'draft': [('readonly', False)]}, 
                                help='This is the Bank Account used by Vendor to receive Invoice Payments.')
    pay_method_id = fields.Many2one('pay.method', string='Forma de Pago',
                                readonly=True, states={'draft': [('readonly', False)]},
                                help='Indicates the Payment Method to use when Paying Vendor Invoice')


