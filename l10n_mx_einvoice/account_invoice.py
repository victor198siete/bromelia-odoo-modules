# -*- encoding: utf-8 -*-

from openerp import api, fields, models, _, tools
from openerp.exceptions import UserError
import datetime
from pytz import timezone
import pytz
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import tempfile
import base64
import os
import tempfile
import hashlib
from xml.dom import minidom
from xml.dom.minidom import parse, parseString
import time
import codecs
import traceback
from . import amount_to_text_es_MX
import logging
_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'


    
    @api.one
    @api.depends('cfdi_state','reference','state')
    def _get_uuid_from_attachment(self):
        if self.state not in ('draft','cancel'):
            attachment_xml_ids = self.env['ir.attachment'].search([('res_model', '=', 'account.invoice'), ('res_id', '=', self.id), ('name', 'ilike', '.xml')], limit=1)
            if attachment_xml_ids:
                try:
                    xml_data = base64.b64decode(attachment_xml_ids.datas).replace('http://www.sat.gob.mx/cfd/3 ', '').replace('Rfc=','rfc=').replace('Fecha=','fecha=').replace('Total=','total=').replace('Folio=','folio=').replace('Serie=','serie=')
                    arch_xml = parseString(xml_data)
                    xvalue = arch_xml.getElementsByTagName('tfd:TimbreFiscalDigital')[0]
                    yvalue = arch_xml.getElementsByTagName('cfdi:Comprobante')[0]                    
                    timbre = xvalue.attributes['UUID'].value
                    serie, folio = False, False
                    try:
                        serie = yvalue.attributes['serie'].value
                    except:
                        pass
                    try:
                        folio = yvalue.attributes['folio'].value
                    except:
                        pass
                    res = self.search([('sat_uuid', '=', timbre),('id','!=',self.id)])
                    if res:
                        raise UserError(_("Error ! La factura ya se encuentra registrada en el sistema y no puede tener registro duplicado.\n\nLa factura con Folio Fiscal %s se encuentra registrada en el registro %s - Referencia: %s - ID: %s")%(timbre, res.number, res.reference, res.id))
                    self.sat_uuid = timbre
                    if serie:
                        self.sat_serie = serie
                    if folio:
                        self.sat_folio = folio
                except:
                    pass

       
    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        super(AccountInvoice, self)._compute_amount()
        self.amount_discount = sum(line.amount_discount for line in self.invoice_line_ids) or 0.0
        self.amount_subtotal = sum(line.amount_subtotal for line in self.invoice_line_ids) or 0.0

    
    amount_discount = fields.Monetary(string='Total Descuento', store=True, readonly=True, compute='_compute_amount',
                                      track_visibility='always')
    amount_subtotal = fields.Monetary(string='Total Subtotal', store=True, readonly=True, compute='_compute_amount')
    
    sat_uuid = fields.Char(compute='_get_uuid_from_attachment', string="CFDI UUID", required=False, store=True, index=True)
    sat_folio = fields.Char(compute='_get_uuid_from_attachment', string="CFDI Folio", required=False, store=True, index=True)
    sat_serie = fields.Char(compute='_get_uuid_from_attachment', string="CFDI Serie", required=False, store=True, index=True)
    
    #### Columns ###################
    forma_pago      = fields.Char(string="Forma de Pago", required=False, default="PAGO EN UNA SOLA EXHIBICION")
    fname_invoice   =  fields.Char(compute='_get_fname_invoice', string='File Name Invoice',
                                    help='Name used for the XML of electronic invoice')
    invoice_datetime = fields.Datetime(string='Date Electronic Invoiced ', readonly=True, 
                                       states={'draft': [('readonly', False)]}, copy=False,
                                      help="Keep empty to use the current date")
    date_invoice_tz = fields.Datetime(string='Date Invoiced with TZ', compute='_get_date_invoice_tz',
                                     help='Date of Invoice with Time Zone', copy=False)
    amount_to_text  = fields.Char(compute='_get_amount_to_text', string='Amount to Text', store=True,
                                help='Amount of the invoice in letter')
    #certificate_id = fields.Many2one('res.company.facturae.certificate', compute='_get_invoice_certificate', 
    #                                    string='Invoice Certificate', store=True, copy=False,
    #                                    help='Id of the certificate used for the invoice')

    #invoice_sequence_id = fields.Many2one('ir.sequence', compute='_get_invoice_sequence',
    #                                        string='Invoice Sequence', #        store=True, 
    #                                        help='Sequence used in the invoice')

    # Campos donde se guardara la info de CFDI
    
    no_certificado  = fields.Char(string='No. Certificado', size=64, help='Number of serie of certificate used for the invoice')
    certificado     = fields.Text('Certificado', size=64, help='Certificate used in the invoice')
    sello           = fields.Text('Sello', size=512, help='Digital Stamp')
    cadena_original = fields.Text('String Original', help='Data stream with the information contained in the electronic invoice') #size=512, 
        
    
    
    cfdi_cbb               = fields.Binary(string='Imagen Código Bidimensional', readonly=True, copy=False)
    cfdi_sello             = fields.Text('Sello',  readonly=True, help='Sign assigned by the SAT', copy=False)
    cfdi_no_certificado    = fields.Char('No. Certificado', size=32, readonly=True,
                                       help='Serial Number of the Certificate', copy=False)
    cfdi_cadena_original   = fields.Text(string='Cadena Original', readonly=True,
                                        help='Original String used in the electronic invoice', copy=False)
    cfdi_fecha_timbrado    = fields.Datetime(string='Fecha Timbrado', readonly=True,
                                           help='Date when is stamped the electronic invoice', copy=False)
    cfdi_fecha_cancelacion = fields.Datetime(string='Fecha Cancelación', readonly=True,
                                             help='Fecha cuando la factura es Cancelada', copy=False)
    cfdi_folio_fiscal      = fields.Char(string='Folio Fiscal (UUID)', size=64, readonly=True,
                                     help='Folio Fiscal del Comprobante CFDI, también llamado UUID', copy=False)

    cfdi_state              = fields.Selection([('draft','Pendiente'),
                                                ('xml_unsigned','XML a Timbrar'),
                                                ('xml_signed','Timbrado'),
                                                ('pdf','PDF'),
                                                ('sent', 'Correo enviado'),
                                                ('cancel','Cancelado'),
                                                ], string="Estado CFDI", readonly=True, default='draft',
                                     help='Estado del Proceso para generar el Comprobante Fiscal', copy=False)
    
    
    
    
    # PENDIENTE => Definir el metodo donde se usaran
    #pdf_file_signed         = fields.Binary(string='Archivo PDF Timbrado', readonly=True, help='Archivo XML que se manda a Timbrar al PAC', copy=False)
    #xml_file_no_sign        = fields.Binary(string='Archivo XML a Timbrar', readonly=True, help='Archivo XML que se manda a Timbrar al PAC', copy=False)
    #xml_file_signed         = fields.Binary(string='Archivo XML Timbrado', readonly=True, help='Archivo XML final (después de timbrado y Addendas)', copy=False)
    xml_file_no_sign_index  = fields.Text(string='XML a Timbrar', readonly=True, help='Contenido del Archivo XML que se manda a Timbrar al PAC', copy=False)
    xml_file_signed_index   = fields.Text(string='XML Timbrado', readonly=True, help='Contenido del Archivo XML final (después de timbrado y Addendas)', copy=False)
    cfdi_last_message       = fields.Text(string='Last Message', readonly=True, help='Message generated to upload XML to sign', copy=False)
    xml_acuse_cancelacion   = fields.Text('XML Acuse Cancelacion', readonly=True)
    cfdi_pac                = fields.Selection([], string='PAC', readonly=True, store=True, copy=False)    
    #pac_id                  = fields.Many2one('params.pac', string='Pac', readonly=True, help='Pac usado para Timbrar la Factura')
    
    ##################################
    pay_method_id   = fields.Many2one('pay.method', string='Forma de Pago', readonly=True, 
                                      states={'draft': [('readonly', False)]},
            help='Indicates the way it was paid or will be paid the invoice,\
            where the options could be: check, bank transfer, reservoir in \
            account bank, credit card, cash etc. If not know as will be \
            paid the invoice, leave empty and the XML show “Unidentified”.')
    
    pay_method_ids  = fields.Many2many('pay.method', 'account_invoice_pay_method_rel', 'invoice_id', 'pay_method_id', 
                                       readonly=True, states={'draft': [('readonly', False)]},
                                       string="Formas de Pago")
    
    acc_payment     = fields.Many2one('res.partner.bank', string='Cuenta Bancaria', readonly=True, 
                                      states={'draft': [('readonly', False)]},
            help='Is the account with which the client pays the invoice, \
            if not know which account will used for pay leave empty and \
            the XML will show "“Unidentified”".')


    address_issued_id = fields.Many2one('res.partner', compute='_get_address_issued_invoice', 
                                        string='Dirección Emisión', store=True,
                                        help='This address will be used as address that issued for electronic invoice')
    
    company_emitter_id = fields.Many2one('res.company', compute='_get_address_issued_invoice', store=True,
                                         string='Compañía Emisora', 
                                         help='This company will be used as emitter company in the electronic invoice')
                                         
    invoice_serie = fields.Char('Serie', size=64, related="journal_id.serie_cfdi_invoice", store=True)

    #####################################
    
class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
        'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        super(AccountInvoiceLine, self)._compute_price()
        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        taxes, taxes2 = False, False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
            taxes2 = self.invoice_line_tax_ids.compute_all(self.price_unit, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
        self.amount_subtotal = taxes2['total_excluded'] if taxes2 else self.quantity * price
        self.amount_discount = self.discount and (taxes2 and (taxes2['total_excluded'] - taxes['total_excluded'])) or ((self.price_unit * self.quantity) * ((self.discount or 0.0) / 100.0)   )     
        
        
    amount_discount = fields.Monetary(string='Monto Descuento', store=True, 
                                      readonly=True, compute='_compute_price', copy=False)
    amount_subtotal = fields.Monetary(string='Monto sin Descuento', store=True, 
                                      readonly=True, compute='_compute_price', copy=False)
        