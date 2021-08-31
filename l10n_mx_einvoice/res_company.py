# -*- encoding: utf-8 -*-

from openerp import api, fields, models, _, release
import time
import openerp

class res_company(models.Model):
    _inherit = 'res.company'

    
    #method_type     = fields.Selection([], string="Acci<C3><B3>n", required=True)
    pac         = fields.Selection([], string="PAC")
    pac_user    = fields.Char(string="Usuario PAC")
    pac_password= fields.Char(string="Contraseña PAC")
    pac_testing = fields.Boolean(string="Testing")
    validate_schema = fields.Boolean(string="Validar Esquema XSD en Servidor Local", default=True )

    address_invoice_parent_company_id = fields.Many2one("res.partner", string='Invoice Company Address Parent', 
                                                        help="In this field should \
        placed the address of the parent company , independently if \
        handled a scheme Multi-company o Multi-Address.",
                                        domain="[('type', 'in', ('invoice','default','contact'))]")
    
    
    if release.major_version == "9.0":
        #### METODOS Y CAMPOS PARA v9
        def _get_address_data(self, cr, uid, ids, field_names, arg, context=None):
            """ Read the 'address' functional fields. """
            result = {}
            part_obj = self.pool.get('res.partner')
            for company in self.browse(cr, uid, ids, context=context):
                result[company.id] = {}.fromkeys(field_names, False)
                if company.partner_id:
                    address_data = part_obj.address_get(cr, openerp.SUPERUSER_ID, [company.partner_id.id], adr_pref=['contact'])
                    if address_data['contact']:
                        address = part_obj.read(cr, openerp.SUPERUSER_ID, [address_data['contact']], field_names, context=context)[0]
                        for field in field_names:
                            result[company.id][field] = address[field] or False
            return result
        
        def _set_address_data(self, cr, uid, company_id, name, value, arg, context=None):
            """ Write the 'address' functional fields. """
            company = self.browse(cr, uid, company_id, context=context)
            if company.partner_id:
                part_obj = self.pool.get('res.partner')
                address_data = part_obj.address_get(cr, uid, [company.partner_id.id], adr_pref=['contact'])
                address = address_data['contact']
                if address:
                    part_obj.write(cr, uid, [address], {name: value or False}, context=context)
                else:
                    part_obj.create(cr, uid, {name: value or False, 'parent_id': company.partner_id.id}, context=context)
            return True        
        
        _columns = {
            'l10n_mx_street3' : openerp.osv.fields.function(_get_address_data, fnct_inv=_set_address_data, size=128, type='char', string="No.Ext.", multi='address'),
            'l10n_mx_street4' : openerp.osv.fields.function(_get_address_data, fnct_inv=_set_address_data, size=128, type='char', string="No.Int.", multi='address'),
            'l10n_mx_city2'   : openerp.osv.fields.function(_get_address_data, fnct_inv=_set_address_data, size=128, type='char', string="Localidad", multi='address'),
            # 'township_sat_id' : openerp.osv.fields.function(_get_address_data, type='many2one', relation='res.country.township.sat.code', string='Municipio', fnct_inv=_set_address_data),
            # 'locality_sat_id' : openerp.osv.fields.function(_get_address_data, type='many2one', relation='res.country.locality.sat.code', string='Localidad', help='Indica el Codigo del Sat para Comercio Exterior.', fnct_inv=_set_address_data),
            # 'zip_sat_id' : openerp.osv.fields.function(_get_address_data, type='many2one', relation='res.country.zip.sat.code', string='CP Sat', help='Indica el Codigo del Sat para Comercio Exterior.', fnct_inv=_set_address_data),
            # 'colonia_sat_id' : openerp.osv.fields.function(_get_address_data, type='many2one', relation='res.colonia.zip.sat.code', string='Colonia Sat', help='Indica el Codigo del Sat para Comercio Exterior.', fnct_inv=_set_address_data),
            'township_sat_id' : openerp.osv.fields.many2one('res.country.township.sat.code', 'Municipio'),
            'locality_sat_id' : openerp.osv.fields.many2one('res.country.locality.sat.code', 'Localidad', help='Indica el Codigo del Sat para Comercio Exterior.'),
            'zip_sat_id' : openerp.osv.fields.many2one('res.country.zip.sat.code', 'CP Sat', help='Indica el Codigo del Sat para Comercio Exterior.'),
            'colonia_sat_id' : openerp.osv.fields.many2one('res.colonia.zip.sat.code', 'Colonia Sat', help='Indica el Codigo del Sat para Comercio Exterior.'),

        }

        def write(self, cr, uid, ids, vals, context=None):
            result = super(res_company,self).write(cr, uid, ids, vals, context)
            self_br = self.browse(cr, uid, ids, context)[0]
            if 'township_sat_id' in vals:
                township_sat_id = vals['township_sat_id']
                if self_br.partner_id:
                    self_br.partner_id.write({'township_sat_id': township_sat_id})
            if 'locality_sat_id' in vals:
                locality_sat_id = vals['locality_sat_id']
                if self_br.partner_id:
                    self_br.partner_id.write({'locality_sat_id': locality_sat_id})
            if 'zip_sat_id' in vals:
                zip_sat_id = vals['zip_sat_id']
                if self_br.partner_id:
                    self_br.partner_id.write({'zip_sat_id': zip_sat_id})
            if 'colonia_sat_id' in vals:
                colonia_sat_id = vals['colonia_sat_id']
                if self_br.partner_id:
                    self_br.partner_id.write({'colonia_sat_id': colonia_sat_id})
            return result
            
    elif release.major_version in ("10.0","11.0"):
        #### METODOS Y CAMPOS PARA v10
        def _compute_address(self):
            for company in self.filtered(lambda company: company.partner_id):
                address_data = company.partner_id.sudo().address_get(adr_pref=['contact'])
                if address_data['contact']:
                    partner = company.partner_id.browse(address_data['contact'])
                    company.street = partner.street
                    # company.street2 = partner.street2
                    # company.city = partner.city
                    # company.zip = partner.zip
                    company.state_id = partner.state_id
                    company.country_id = partner.country_id
                    company.fax = partner.fax
                    company.l10n_mx_street3 = partner.l10n_mx_street3
                    company.l10n_mx_street4 = partner.l10n_mx_street4
                    company.l10n_mx_city2 = partner.l10n_mx_city2
                    company.township_sat_id = partner.township_sat_id.id
                    company.locality_sat_id = partner.locality_sat_id.id
                    company.zip_sat_id = partner.zip_sat_id.id
                    company.colonia_sat_id = partner.colonia_sat_id.id

        def _inverse_l10n_mx_street3(self):
            for company in self:
                company.partner_id.l10n_mx_street3 = company.l10n_mx_street3
                
        def _inverse_l10n_mx_street4(self):
            for company in self:
                company.partner_id.l10n_mx_street4 = company.l10n_mx_street4

        def _inverse_l10n_mx_city2(self):
            for company in self:
                company.partner_id.l10n_mx_city2 = company.l10n_mx_city2                

        def _inverse_township_sat_id(self):
            for company in self:
                company.partner_id.township_sat_id = company.township_sat_id.id

        def _inverse_locality_sat_id(self):
            for company in self:
                company.partner_id.locality_sat_id = company.locality_sat_id.id
        
        def _inverse_zip_sat_id(self):
            for company in self:
                company.partner_id.zip_sat_id = company.zip_sat_id.id
        
        def _inverse_colonia_sat_id(self):
            for company in self:
                company.partner_id.colonia_sat_id = company.colonia_sat_id.id
                            
        l10n_mx_street3 = fields.Char(compute='_compute_address', inverse='_inverse_l10n_mx_street3', string="No. External", help='External number of the partner address')
        l10n_mx_street4 = fields.Char(compute='_compute_address', inverse='_inverse_l10n_mx_street4', string="No. Internal", help='Internal number of the partner address')
        l10n_mx_city2   = fields.Char(compute='_compute_address', inverse='_inverse_l10n_mx_city2',   string="Locality", help='Locality configurated for this partner')
        township_sat_id = fields.Many2one('res.country.township.sat.code', string='Municipio', compute='_compute_address', inverse='_inverse_township_sat_id')
        locality_sat_id = fields.Many2one('res.country.locality.sat.code', string='Localidad', help='Indica el Codigo del Sat para Comercio Exterior.', compute='_compute_address', inverse='_inverse_locality_sat_id')
        zip_sat_id = fields.Many2one('res.country.zip.sat.code', string='CP Sat', help='Indica el Codigo del Sat para Comercio Exterior.', compute='_compute_address', inverse='_inverse_zip_sat_id')
        colonia_sat_id = fields.Many2one('res.colonia.zip.sat.code', string='Colonia Sat', help='Indica el Codigo del Sat para Comercio Exterior.', compute='_compute_address', inverse='_inverse_colonia_sat_id')

    
    @api.one
    def get_address_invoice_parent_company_id(self):
        partner_obj = self.pool.get('res.partner')
        company_id = self
        partner_parent = company_id and company_id.parent_id and company_id.parent_id.partner_id or False
        if partner_parent:
            address_id = partner_parent.address_get(['invoice'])['invoice']
        elif company_id.company_address_main_id:
            address_id = company_id.company_address_main_id.id
        else:
            address_id = self.partner_id.address_get(['invoice'])['invoice']
        return address_id

    @api.onchange('colonia_sat_id')
    def onchange_colonia_sat_id(self):
        if self.colonia_sat_id:
            colonia_name = "[ "+str(self.colonia_sat_id.code)+"] "+str(self.colonia_sat_id.zip_sat_code.code if self.colonia_sat_id.zip_sat_code else "")+"/ "+str(self.colonia_sat_id.name or "")

            self.street2 = colonia_name
            township_name = "[ "+self.colonia_sat_id.zip_sat_code.township_sat_code.code+" ] "+self.colonia_sat_id.zip_sat_code.township_sat_code.name
            self.city = township_name
            self.township_sat_id = self.colonia_sat_id.zip_sat_code.township_sat_code.id
            self.locality_sat_id = self.colonia_sat_id.zip_sat_code.locality_sat_code.id if self.colonia_sat_id.zip_sat_code.locality_sat_code else False
            self.zip_sat_id = self.colonia_sat_id.zip_sat_code.id
            self.zip_sat_id = self.colonia_sat_id.zip_sat_code.id
            
            country_sat_code = self.colonia_sat_id.zip_sat_code.state_sat_code.country_sat_code.id
            country_id = self.env['res.country'].search([('sat_code','=',country_sat_code)])
            self.country_id = country_id[0].id if country_id else False


    @api.onchange('zip_sat_id')
    def onchange_zip_sat_id(self):
        if self.zip_sat_id:
            self.zip = self.zip_sat_id.code
            self.township_sat_id = self.zip_sat_id.township_sat_code.id
            self.locality_sat_id = self.zip_sat_id.locality_sat_code.id

            state_sat_code = self.zip_sat_id.state_sat_code.id
            state_id = self.env['res.country.state'].search([('sat_code','=',state_sat_code)])
            if state_id:
                self.state_id = state_id[0].id
                self.country_id = state_id[0].country_id.id
            colonia_sat_id = self.env['res.colonia.zip.sat.code'].search([('zip_sat_code','=',self.zip_sat_id.id)])
            if colonia_sat_id:
                self.colonia_sat_id = colonia_sat_id[0].id

    @api.onchange('state_id')
    def onchange_domain_sat_list(self):
        domain = {}
        if self.state_id:
            township_obj = self.env['res.country.township.sat.code']
            township_ids = township_obj.search([('state_sat_code.code','=',self.state_id.sat_code.code)])
            if township_ids:
                domain.update(
                    {
                        'township_sat_id':[('id','in',[x.id for x in township_ids])]
                    })
            locality_obj = self.env['res.country.locality.sat.code']
            locality_ids = locality_obj.search([('state_sat_code.code','=',self.state_id.sat_code.code)])
            if locality_ids:
                domain.update(
                    {
                        'locality_sat_id':[('id','in',[x.id for x in locality_ids])]
                    })

        return {'domain': domain}

    
class ResCompanyGetCFDICountWizard(models.TransientModel):
    _name = 'res.company.getcfdicount'
    
    date = fields.Date(string="Desde", default=fields.Date.context_today)
    state    = fields.Selection([('step1','Step 1'), ('step2', 'Step 2')],
                                   default='step1', string="State")
    conteo = fields.Integer("CFDIs consumidos")
    
    
    @api.multi
    def get_cfdi_count(self):
        self.ensure_one()
        invoices = self.env['account.invoice'].search([('type','in',('out_invoice','out_refund')),
                                                       ('cfdi_folio_fiscal','!=',False),
                                                       ('date_invoice','>=',self.date)])
        payments = self.env['account.payment'].search([('payment_type','=','inbound'),
                                                       ('cfdi_folio_fiscal','!=',False),
                                                       ('payment_date','>=',self.date)])
        
        self.write({'state' : 'step2',
                    'conteo' : len(list(invoices)) + len(list(payments))})
    
        return self._reopen_wizard(self.id)

    
    def _reopen_wizard(self, res_id):
        return {'type'      : 'ir.actions.act_window',
                'res_id'    : res_id,
                'view_mode' : 'form',
                'view_type' : 'form',
                'res_model' : 'res.company.getcfdicount',
                'target'    : 'new',
                'name'      : 'Conteo de CFDIs consumidos'}    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:    