# -*- encoding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.osv import expression

class pay_method(models.Model):
    _name = 'pay.method'

    code        = fields.Char(string='Clave SAT', required=True)
    name        = fields.Char(string='Forma de Pago', size=128, required=True)
    description = fields.Text(string='Descripción', required=True)

    bancarizado = fields.Selection([('si','Si'),
                                    ('no','No'),
                                    ('opcional','Opcional'),],
                                    string="Bancarizado", required=True, default='no')
    num_operacion = fields.Selection([('opcional','Opcional'),],
                                    string="No. Operación", required=True, default='opcional')
    
    rfc_del_emisor_cuenta_ordenante = fields.Selection([('no','No'),
                                       ('opcional','Opcional'),],
                                        string="RFC del Emisor de la Cuenta Ordenante", required=True, default='opcional')
    
    cuenta_ordenante = fields.Selection([('no','No'),
                                       ('opcional','Opcional'),],
                                        string="Cuenta Ordenante", required=True, default='opcional')
    patron_cuenta_ordenante = fields.Char(string="Patrón para Cuenta Ordenante")
    
    rfc_del_emisor_cuenta_beneficiario = fields.Selection([('no','No'),
                                                           ('opcional','Opcional'),],
                                        string="RFC del Emisor Cuenta de Beneficiario", required=True, default='opcional')
    
    cuenta_beneficiario = fields.Selection([('no','No'),
                                       ('opcional','Opcional'),],
                                        string="Cuenta Beneficiario", required=True, default='opcional')
    
    patron_cuenta_beneficiario = fields.Char(string="Patrón para Cuenta Beneficiario")
    
    
    tipo_cadena_pago = fields.Selection([('no','No'),
                                       ('opcional','Opcional'),],
                                        string="Tipo Cadena Pago", required=True, default='no')
    
    banco_emisor_obligatorio_extranjero = fields.Boolean(string="Requerir Nombre Banco Emisor",
                                                        help="Nombre del Banco emisor de la cuenta ordenante en caso de extranjero")
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El nombre de la Forma de Pago debe ser único !'),
        ('code_uniq', 'unique(code)', 'La clave de la Forma de Pago debe ser único !'),
    ]    
    
    
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&'] + domain
        accounts = self.search(domain + args, limit=limit)
        return accounts.name_get()
    

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for x in self:
            if x.code and x.name:
                name = '[ '+x.code + ' ] ' + x.name
                result.append((x.id, name))
        return result
