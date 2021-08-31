# -*- encoding: utf-8 -*-

from openerp import api, fields, models, _, tools
from openerp.exceptions import UserError


class report_multicompany(models.Model):
    _name = 'report.multicompany'
    _order = 'sequence, id desc'

    company_id  = fields.Many2one('res.company', string='Company',change_default=True,
                                 default=lambda self: self.env['res.company']._company_default_get('report.multicompany'))
    report_id   = fields.Many2one('ir.actions.report.xml', 'Report Template', required=True,
                                 help="""This report template will be assigned for electronic invoicing in your company""")
    report_name = fields.Char(string='Report Name', related='report_id.report_name',  readonly=True)
    sequence    = fields.Integer(string='Sequence', default=10)
    model       = fields.Many2one('ir.model', string='Model', required=True)


    @api.onchange('report_id')
    def onchange_report_model(self):
        #actions_obj = self.env['ir.actions.report.xml']
        ir_model_obj = self.env['ir.model']
        model_id = False
        if self.report_id:
            model_ids = ir_model_obj.search([('model', '=', self.report_id.model)], limit=1)
            model_id = model_ids.id or False
        self.model = model_id


