# -*- encoding: utf-8 -*-

from openerp import api, fields, models, _


class stock_picking(models.Model):
    _inherit = 'stock.picking'
    
    
    def _get_invoice_vals(self, cr, uid, key, inv_type, journal_id, move, context=None):
        if context is None:
            context = {}
        res = super(stock_picking, self)._get_invoice_vals(cr, uid, key, inv_type, journal_id, move, context=context)
        if inv_type in ('out_invoice', 'out_refund'):
            acc_payment_id = move.picking_id and move.picking_id.sale_id and \
                             move.picking_id.sale_id.acc_payment and \
                             move.picking_id.sale_id.acc_payment.id or False
            
            payment_method_id = move.picking_id and move.picking_id.sale_id and \
                             move.picking_id.sale_id.pay_method_id and \
                             move.picking_id.sale_id.pay_method_id.id or False
            uso_cfdi_id = move.picking_id and move.picking_id.sale_id and \
                             move.picking_id.sale_id.uso_cfdi_id and \
                             move.picking_id.sale_id.uso_cfdi_id.id or False
        else:
            acc_payment_id = move.purchase_line_id and move.purchase_line_id.order_id and \
                             move.purchase_line_id.order_id.acc_payment and \
                             move.purchase_line_id.order_id.acc_payment.id or False
            
            payment_method_id = move.purchase_line_id and move.purchase_line_id.order_id and \
                             move.purchase_line_id.order_id.pay_method_id and \
                             move.purchase_line_id.order_id.pay_method_id.id or False
            uso_cfdi_id = False
                    
        res.update({'acc_payment'  : acc_payment_id,
                    'pay_method_id': payment_method_id,
                    'uso_cfdi_id'  : uso_cfdi_id})
        
        return res
        
        
