# -*- encoding: utf-8 -*-

from openerp import api, fields, models, _, release


class res_partner(models.Model):
    _inherit = 'res.partner'
    
    if release.major_version == "9.0":
        #### METODOS Y CAMPOS PARA v9
        @api.v7
        def _address_fields(self, cr, uid, context=None):
            "Returns the list of the address fields that synchronizes from the parent when the flag is set use_parent_address."
            #res = super(res_partner, self)._address_fields(self)
            #res.extend(['l10n_mx_street3', 'l10n_mx_street4', 'l10n_mx_city2'])
            return list(('street', 'street2', 'zip', 'city', 'state_id', 'country_id','l10n_mx_street3', 'l10n_mx_street4', 'l10n_mx_city2'))

    elif release.major_version in ("10.0","11.0"):
        #### METODOS Y CAMPOS PARA v9
        @api.model
        def _address_fields(self):
            """Returns the list of address fields that are synced from the parent."""
            return list(('street', 'street2', 'zip', 'city', 'state_id', 'country_id','l10n_mx_street3', 'l10n_mx_street4', 'l10n_mx_city2'))
    
    def _get_default_country_id(self):
        country_obj = self.env['res.country']
        country = country_obj.search([('code', '=', 'MX'), ], limit=1)
        return country and country.id or False
    
    @api.one
    def _get_base_vat_split(self):
        self.vat_split = self.vat and self.vat[2:] or False
    
    l10n_mx_street3 = fields.Char(string='No. External', size=128, help='External number of the partner address')
    l10n_mx_street4 = fields.Char(string='No. Internal', size=128, help='Internal number of the partner address')
    l10n_mx_city2   = fields.Char(string='Locality', size=128, help='Locality configurated for this partner')
    country_id      = fields.Many2one('res.country', string='Country', ondelete='restrict', default=_get_default_country_id)
    envio_manual_cfdi = fields.Boolean(string="Envío manual del CFDI", help="Si marca la casilla entonces las facturas que genere a este cliente NO serán enviadas automáticamente al validar la factura, sino que manualmente tendrá que presionar el Botón de Envío correspondiente. Esto es útil si maneja Addendas o si el CFDI debe ser subido a algún portal del Cliente.")
    
    regimen_fiscal_id = fields.Many2one('sat.regimen.fiscal', string="Régimen Fiscal",
        help="The fiscal position will determine taxes and accounts used for the partner.")

    vat_split =  fields.Char(compute='_get_base_vat_split', string='VAT Split', #store=True,
                    help='Remove the prefix of the country of the VAT')    
    pay_method_id   = fields.Many2one('pay.method', string='Forma de Pago',
            help='Indicates the way it was paid or will be paid the invoice, \
            where the options could be: check, wire transfer, reservoir in \
            account bank, credit card, cash etc. If you do not know how it will be \
            paid, leave it empty and the XML show “Unidentified”.')
"""    
    def fields_view_get(self, cr, user, view_id=None, view_type='form',
        context=None, toolbar=False, submenu=False):
        if (not view_id) and (view_type == 'form') and context and context.get('force_email', False):
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, user, 'base', 'view_partner_simple_form')[1]
        res = super(res_partner, self).fields_view_get(cr, user, view_id, view_type, context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            fields_get = self.fields_get(cr, user, ['l10n_mx_street3', 'l10n_mx_street4', 'l10n_mx_city2'], context)
            res['fields'].update(fields_get)
        return res
"""



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:    