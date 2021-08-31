# -*- encoding: utf-8 -*-
from openerp import release
if release.major_version in ("9.0", "10.0"):
    import sys
    reload(sys)
    sys.setdefaultencoding('utf-8')

if release.major_version == "9.0":
    from openerp import api, fields, models, _, tools, release
    from openerp.exceptions import UserError, RedirectWarning, ValidationError
    from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
elif release.major_version in ("10.0","11.0"):
    from odoo import api, fields, models, _, tools, release
    from odoo.exceptions import UserError
    from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT

import datetime
from pytz import timezone
import pytz
import tempfile
import base64
import os
import tempfile
import hashlib
from xml.dom import minidom
import time
import codecs
import traceback
import re
from . import amount_to_text_es_MX

from lxml import etree
from lxml.objectify import fromstring
from xml.dom.minidom import parse, parseString

CFDI_XSLT_CADENA_TFD = 'l10n_mx_einvoice/SAT/cadenaoriginal_3_3/cadenaoriginal_TFD_1_1.xslt'


import logging
_logger = logging.getLogger(__name__)

msg2 = "Contact you administrator &/or to info@argil.mx"

def conv_ascii(text):
    """
    @param text : text that need convert vowels accented & characters to ASCII
    Converts accented vowels, ñ and ç to their ASCII equivalent characters
    """
    old_chars = [
        'á', 'é', 'í', 'ó', 'ú', 'à', 'è', 'ì', 'ò', 'ù', 'ä', 'ë', 'ï', 'ö',
        'ü', 'â', 'ê', 'î', 'ô', 'û', 'Á', 'É', 'Í', 'Ó', 'Ú', 'À', 'È', 'Ì',
        'Ò', 'Ù', 'Ä', 'Ë', 'Ï', 'Ö', 'Ü', 'Â', 'Ê', 'Î', 'Ô', 'Û',
        'ç', 'Ç', 'ª', 'º', '°', ' ', 'Ã', 'Ø'
    ]
    new_chars = [
        'a', 'e', 'i', 'o', 'u', 'a', 'e', 'i', 'o', 'u', 'a', 'e', 'i', 'o',
        'u', 'a', 'e', 'i', 'o', 'u', 'A', 'E', 'I', 'O', 'U', 'A', 'E', 'I',
        'O', 'U', 'A', 'E', 'I', 'O', 'U', 'A', 'E', 'I', 'O', 'U',
        'c', 'C', 'a', 'o', 'o', ' ', 'A', '0'
    ]
    for old, new in zip(old_chars, new_chars):
        try:
            text = text.replace(unicode(old, 'UTF-8'), new)
        except:
            try:
                text = text.replace(old, new)
            except:
                raise UserError(_("Warning !\nCan't recode the string [%s] in the letter [%s]") % (text, old))
    return text



class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.one
    @api.depends('amount_total','currency_id')
    def _get_amount_to_text(self):
        self.amount_to_text = amount_to_text_es_MX.get_amount_to_text(self, self.amount_total, self.currency_id.name)
        

    @api.one
    def _get_date_invoice_tz(self):
        dt_format = DEFAULT_SERVER_DATETIME_FORMAT
        
        #str(datetime.datetime.now(pytz.timezone(self.env.user.partner_id.tz)))        
        tz = self.env.user.partner_id.tz or 'America/Mexico_City'
        self.date_invoice_tz = self.invoice_datetime and self.server_to_local_timestamp(
                self.invoice_datetime, DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, tz) or False
            
        
    @api.one
    def _get_fname_invoice(self):
        if self.type in ('in_invoice','in_refund'):
            self.fname_invoice = '.'
            return

        fname = ""
        if not self.company_emitter_id.partner_id.vat_split and not self.company_emitter_id.partner_id.vat :
            raise UserError(_("Error!\nLa Compañía Emisora no tiene definido el RFC."))
        fname += (self.company_emitter_id.partner_id.vat_split or self.company_emitter_id.partner_id.vat) + '_' + (self.number or '')
        #if self.type == 'out_invoice' and self.journal_id.sequence_id.prefix:
        #    fname += '_' + self.journal_id.sequence_id.prefix.replace('-', '').replace('/','').replace(' ','') or ''
        #elif self.type == 'out_refund' and self.journal_id.serie_cfdi_refund:
        #    fname += '_' + self.journal_id.refund_sequence_id.prefix.replace('-', '').replace('/','').replace(' ','') or ''
        #else:
        #    fname += '_'
        #fname += '_' + self.number or ''
        self.fname_invoice = fname
        
    @api.one
    @api.depends('journal_id')
    def _get_address_issued_invoice(self):
        self.address_issued_id = self.journal_id.address_invoice_company_id or \
                                (self.journal_id.company2_id and self.journal_id.company2_id.address_invoice_parent_company_id) or \
                                self.journal_id.company_id.address_invoice_parent_company_id or False
        self.company_emitter_id = self.journal_id.company2_id or self.journal_id.company_id or False
        
        
    #### ON_CHANGE 

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        res = super(AccountInvoice, self)._onchange_journal_id()
        self.address_invoice_company_id = self.journal_id.address_invoice_company_id
        self.company2_id = self.journal_id.company2_id

        
    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        res = super(AccountInvoice, self)._onchange_partner_id()
        self.pay_method_ids = self.partner_id and ((self.partner_id.parent_id and [self.partner_id.parent_id.pay_method_id.id]) or
                              (self.partner_id.pay_method_id and [self.partner_id.pay_method_id.id])) or False
        self.uso_cfdi_id = self.partner_id and ((self.partner_id.parent_id and self.partner_id.parent_id.uso_cfdi_id.id) or
                              (self.partner_id.uso_cfdi_id and self.partner_id.uso_cfdi_id.id)) or False

        
    @api.onchange('invoice_line_ids')
    def _onchange_origin(self):
        super(AccountInvoice, self)._onchange_origin()
        purchase_ids = self.invoice_line_ids.mapped('purchase_id')
        if purchase_ids:
            x = 0            
            for line in self.invoice_line_ids:
                if x: break
                self.acc_payment   = line.purchase_id.acc_payment and line.purchase_id.acc_payment.id or False
                self.pay_method_id = line.purchase_id.pay_method_id and line.purchase_id.pay_method_id.id or False
                x += 1
        
    #### ACTIONS

    
    if release.major_version == "9.0":
        @api.multi
        def action_cancel_draft(self):
            for invoice in self:
                if invoice.type in ('out_invoice','out_refund') and invoice.cfdi_folio_fiscal:
                    raise UserError(_('No puede regresar la Factura o Nota de Crédito a borrador porque ya se encuentra timbrada y posteriormente se canceló el Timbre. Duplique la factura para poder timbrarla nuevamente'))
            self.write({'xml_file_no_sign_index': False,'cfdi_last_message': False, 'cfdi_state':'draft'})
            return super(AccountInvoice, self).action_cancel_draft()
    elif release.major_version in ("10.0","11.0"):
        @api.multi
        def action_invoice_draft(self):
            for invoice in self:
                if invoice.type in ('out_invoice','out_refund') and invoice.cfdi_folio_fiscal:
                    raise UserError(_('No puede regresar la Factura o Nota de Crédito a borrador porque ya se encuentra timbrada y posteriormente se canceló el Timbre. Duplique la factura para poder timbrarla nuevamente'))
            self.write({'xml_file_no_sign_index': False,'cfdi_last_message': False, 'cfdi_state':'draft'})
            return (release.major_version == "9.0" and super(AccountInvoice, self).action_cancel_draft()) or (release.major_version in ("10.0","11.0") and super(AccountInvoice, self).action_invoice_draft())
    ####################################
    
    def get_server_timezone(self):
        return "UTC"
    

    def server_to_local_timestamp(self, src_tstamp_str, src_format, dst_format, dst_tz_name,
            tz_offset=True, ignore_unparsable_time=True):

        if not src_tstamp_str:
            return False

        res = src_tstamp_str
        if src_format and dst_format:
            # find out server timezone
            server_tz = self.get_server_timezone()
            try:
                # dt_value needs to be a datetime.datetime object (so no time.struct_time or mx.DateTime.DateTime here!)
                dt_value = datetime.datetime.strptime(src_tstamp_str, src_format)
                if tz_offset and dst_tz_name:
                    try:                        
                        src_tz = pytz.timezone(server_tz)
                        dst_tz = pytz.timezone(dst_tz_name)
                        src_dt = src_tz.localize(dt_value, is_dst=True)
                        dt_value = src_dt.astimezone(dst_tz)
                    except Exception:
                        pass
                res = dt_value.strftime(dst_format)
            except Exception:
                # Normal ways to end up here are if strptime or strftime failed
                if not ignore_unparsable_time:
                    return False
        return res

        
    def _get_time_zone(self):
        userstz = self.env.user.partner_id.tz
        a = 0
        if userstz:
            hours = timezone(userstz)
            fmt = '%Y-%m-%d %H:%M:%S %Z%z'
            today_now = datetime.datetime.now()
            loc_dt = hours.localize(datetime.datetime(today_now.year, today_now.month, today_now.day,
                                             today_now.hour, today_now.minute, today_now.second))
            timezone_loc = (loc_dt.strftime(fmt))
            diff_timezone_original = timezone_loc[-5:-2]
            timezone_original = int(diff_timezone_original)
            s = str(datetime.datetime.now(pytz.timezone(userstz)))
            s = s[-6:-3]
            timezone_present = int(s)*-1
            a = timezone_original + ((
                timezone_present + timezone_original)*-1)
        return a

    

    def assigned_datetime(self, values={}):
        res = {}
        if values.get('date_invoice', False) and not values.get('invoice_datetime', False):
            user_hour = self._get_time_zone()
            time_invoice = datetime.time(abs(user_hour), 0, 0)
            date_invoice = datetime.datetime.strptime(values['date_invoice'], '%Y-%m-%d').date()
            dt_invoice = datetime.datetime.combine(date_invoice, time_invoice).strftime('%Y-%m-%d %H:%M:%S')
            
            xdt_invoice = str(datetime.datetime.now(pytz.timezone(self.env.user.partner_id.tz)))
            if xdt_invoice[0:10] == values['date_invoice']:
                dt_invoice = xdt_invoice = str(datetime.datetime.now())
            ################################
            res.update({'invoice_datetime' : dt_invoice,
                        'date_invoice' :  values['date_invoice']})
        if values.get('invoice_datetime', False) and not values.get('date_invoice', False):
            date_invoice = fields.Datetime.context_timestamp(self, datetime.datetime.strptime(values['invoice_datetime'], DEFAULT_SERVER_DATETIME_FORMAT))
            res.update({'date_invoice'    : date_invoice, 
                       'invoice_datetime' : values['invoice_datetime']})            
        if 'invoice_datetime' in values  and 'date_invoice' in values:
            if values['invoice_datetime'] and values['date_invoice']:
                date_invoice = datetime.datetime.strptime(
                    values['invoice_datetime'],
                    '%Y-%m-%d %H:%M:%S').date().strftime('%Y-%m-%d')
                if date_invoice != values['date_invoice']:
                    groups_obj = self.env['res.groups']
                    group_datetime = self.env['ir.model.data'].get_object_reference('l10n_mx_einvoice', 'group_datetime_invoice_l10n_mx_facturae')
                    group_date = self.env['ir.model.data'].get_object_reference('l10n_mx_einvoice', 'group_date_invoice_l10n_mx_facturae')
                    if group_datetime and group_date:
                        users_datetime = []
                        users_date = []
                        for user in groups_obj.browse([group_datetime[1]])[0].users:
                            users_datetime.append(user.id)
                        for user in groups_obj.browse([group_date[1]])[0].users:
                            users_date.append(user.id)
                        if self._uid in users_datetime:
                            date_invoice = fields.Datetime.context_timestamp(self, 
                                datetime.datetime.strptime(values['invoice_datetime'], DEFAULT_SERVER_DATETIME_FORMAT))
                            res.update({'date_invoice'    : date_invoice, 
                                        'invoice_datetime' : values['invoice_datetime']})
                        elif self._uid in users_date:
                            user_hour = self._get_time_zone()
                            time_invoice = datetime.time(abs(user_hour), 0, 0)

                            date_invoice = datetime.datetime.strptime(
                                values['date_invoice'], '%Y-%m-%d').date()
                                
                            dt_invoice = datetime.datetime.combine(
                                date_invoice, time_invoice).strftime('%Y-%m-%d %H:%M:%S')

                            res.update({'date_invoice'    : values['date_invoice'], 
                                        'invoice_datetime' : dt_invoice})
                        else:
                            raise UserError(_('Invoice dates should be equal'))
                    else:
                        raise UserError(_('Invoice dates should be equal'))
                            
        if  not values.get('invoice_datetime', False) and not values.get('date_invoice', False):
            res['date_invoice'] = fields.Date.context_today(self)
            res['invoice_datetime'] = fields.datetime.now()
        return res
            
    @api.multi
    def action_move_create(self):
        res = super(AccountInvoice, self).action_move_create()
        for inv in self:
            if inv.type in ('out_invoice', 'out_refund'):
                vals_date = self.assigned_datetime({'invoice_datetime': inv.invoice_datetime,
                                                    'date_invoice': inv.date_invoice,
                                                            })
                inv.write(vals_date)
        return res
    
    
    # @api.multi
    # def action_cancel(self):
    #     res = super(AccountInvoice, self).action_cancel()
    #     for invoice in self:
    #         if invoice.type in ('out_invoice', 'out_refund') and invoice.journal_id.use_for_cfdi and invoice.cfdi_folio_fiscal:
    #             type__fc = invoice.get_driver_cfdi_cancel() and invoice.get_driver_cfdi_cancel()[0] or {}
    #             if invoice.cfdi_pac in type__fc.keys():
    #                 res2 = type__fc[invoice.cfdi_pac]()[0]
    #                 invoice.write({'cfdi_fecha_cancelacion':time.strftime('%Y-%m-%d %H:%M:%S'),
    #                                'cfdi_last_message': self.cfdi_last_message + "\n-.-.-.-.-.-.-.-.-.-.-.-.-.\n" + \
    #                             fields.Datetime.to_string(fields.Datetime.context_timestamp(
    #                                                                             self.with_context(tz=(self.env.user.partner_id.tz or 'America/Mexico_City')),
    #                                                                             datetime.datetime.now())
    #                                                                            ) + \
    #                                                             ' => ' + res2['message'] + u'\nCódigo: ' + res2['status_uuid']
    #                         })
            
    #         for cfdi_rel in invoice.type_rel_cfdi_ids:
    #             cfdi_rel.invoice_id.write({'deposit_invoice_used': False, 'deposit_invoice_rel_id': False})
        
    #     return res

    
    def check_partner_data(self, partner, is_company_address=False):
        if partner.parent_id:
            partner = partner.parent_id
        if not is_company_address and partner.company_type == 'person':
            raise UserError(_("La Empresa - (ID: %s) %s - no está definida como Compañía o Persona Fisica, para usarlo en Facturas, es necesario que la defina como Compañía...") % (partner.id,partner.name))
        if not partner.vat:
            raise UserError(_("La Empresa - (ID: %s) %s - no tiene el RFC definido, por favor revise...") % (partner.id,partner.name))
        if partner.country_id.code == 'MX' and not is_company_address:
            if not partner.zip_sat_id:
                raise UserError(_("La Empresa - (ID: %s) %s - no tiene Codigo Postal en su direccion, por favor revise...") % (partner.id,partner.name))
        # if not partner.regimen_fiscal_id:
        #     raise UserError("Error!\nLa Empresa %s no tiene definido un Regimen Fiscal, por lo cual no puede emitir el Recibo CFDI." % partner.name)
        return
    
    
    ##################################
    
    def binary2file(self, binary_data, file_prefix="", file_suffix=""):
        """
        @param binary_data : Field binary with the information of certificate
                of the company
        @param file_prefix : Name to be used for create the file with the
                information of certificate
        @file_suffix : Sufix to be used for the file that create in this function
        """
        (fileno, fname) = tempfile.mkstemp(file_suffix, file_prefix)
        f = open(fname, 'wb')
        f.write(base64.decodestring(binary_data))
        f.close()
        os.close(fileno)
        return fname
    
    
    def _xml2cad_orig(self):
        context = self._context.copy()
        certificate_lib = self.env['facturae.certificate.library']
        fname_tmp = certificate_lib.b64str_to_tempfile(base64.encodestring(
            ''), file_suffix='.txt', file_prefix='odoo__' + (False or '') + \
            '__cadorig__')
        cad_orig = certificate_lib._transform_xml(fname_xml=context['fname_xml'],
            fname_xslt=context['fname_xslt'], fname_out=fname_tmp)
        ### Guardando la Cadena Original ###
        f = open(fname_tmp, 'wb')
        f.write(cad_orig)
        f.close()
        return fname_tmp, cad_orig

    
    def _get_certificate_str(self, fname_cer_pem=""):
        """
        @param fname_cer_pem : Path and name the file .pem
        """
        fcer = open(fname_cer_pem, "r")
        lines = fcer.readlines()
        fcer.close()
        cer_str = ""
        loading = False
        for line in lines:
            if 'END CERTIFICATE' in line:
                loading = False
            if loading:
                cer_str += line
            if 'BEGIN CERTIFICATE' in line:
                loading = True
        return cer_str


    def dict2xml(self, data_dict, node=False, doc=False):
        """
        @param data_dict : Dictionary of attributes for add in the XML 
                    that will be generated
        @param node : Node from XML where will be added data from the dictionary
        @param doc : Document XML generated, where will be working
        """
        parent = False
        if node:
            parent = True
        for element, attribute in self._dict_iteritems_sort(data_dict):
            if not parent:
                doc = minidom.Document()
            # Para lineas que no esten agrupadas podemos usar un diccionario = []
            # donde cada item del list es un diccionario.
            if element == '_value_not_grouped':
                for attr in attribute:
                    self.dict2xml(attr, node, doc)
            elif isinstance(attribute, dict):
                if not parent:
                    node = doc.createElement(element)
                    self.dict2xml(attribute, node, doc)
                else:
                    child = doc.createElement(element)
                    # Creamos el texto dentro de "element", Por ejemplo: <tag>valor</tag>
                    # Recuerde usar un diccionario con un elemento: '_value' : valor
                    if isinstance(attribute, dict) and '_value' in attribute:
                        if len(attribute)==1:
                            xres = doc.createTextNode(attribute['_value'])
                            child.appendChild(xres)
                        else:
                            attribute2 = attribute.copy()
                            attribute2.pop('_value')
                            self.dict2xml(attribute2, child, doc)
                            xres = doc.createTextNode(attribute['_value'])
                            child.appendChild(xres)
                    else:
                        self.dict2xml(attribute, child, doc)
                    node.appendChild(child)
            elif isinstance(attribute, list):
                child = doc.createElement(element)                
                for attr in attribute:
                    if isinstance(attr, dict):
                        if element=='cfdi:InformacionAduanera': #AC
                            child = doc.createElement(element) #AC
                        self.dict2xml(attr, child, doc)
                        if element == 'cfdi:InformacionAduanera': #AC
                            node.appendChild(child) #AC
                node.appendChild(child)
            else:
                if isinstance(attribute, str) or isinstance(attribute, unicode):
                    attribute = conv_ascii(attribute)
                else:
                    attribute = str(attribute)
                node.setAttribute(element, attribute)
        if not parent:
            doc.appendChild(node)
        return doc    
    
    
    # TODO: agregar esta funcionalidad con openssl
    def _get_md5_cad_orig(self, cadorig_str, fname_cadorig_digest):
        """
        @param cadorig_str :
        @fname cadorig_digest :
        """
        cadorig_digest = hashlib.md5(cadorig_str).hexdigest()
        open(fname_cadorig_digest, "w").write(cadorig_digest)
        return cadorig_digest, fname_cadorig_digest
    
    
    def _get_noCertificado(self, fname_cer, pem=True):
        """
        @param fname_cer : Path more name of file created whit information 
                    of certificate with suffix .pem
        @param pem : Boolean that indicate if file is .pem
        """
        certificate_lib = self.env['facturae.certificate.library']
        fname_serial = certificate_lib.b64str_to_tempfile(base64.encodestring(
            ''), file_suffix='.txt', file_prefix='odoo__' + (False or '') + \
            '__serial__')
        result = certificate_lib._get_param_serial(fname_cer, fname_out=fname_serial, type='PEM')
        return result

    
    def _get_sello(self):
        # TODO: Put encrypt date dynamic
        context = self._context.copy() or {}
        fecha = self._context['fecha']
        year = float(time.strftime('%Y', time.strptime(fecha, '%Y-%m-%dT%H:%M:%S')))
        encrypt = "sha256"
        certificate_lib = self.env['facturae.certificate.library']
        result_sello_256 = certificate_lib.with_context(context)._sign_sello()
        return result_sello_256

    
    def _dict_iteritems_sort(self, data_dict):  # cr=False, uid=False, ids=[], context=None):
        """
        @param data_dict : Dictionary with data from invoice
        """
        key_order = [
            'cfdi:CfdiRelacionados',
            'cfdi:Emisor',
            'cfdi:Receptor',
            'cfdi:Conceptos',
            'cfdi:Impuestos',
            'cfdi:Complemento',
            'cfdi:Addenda',
        ]
       
        keys = data_dict.keys()
        key_item_sort = []
        for ko in key_order:
            if ko in keys:
                key_item_sort.append([ko, data_dict[ko]])
                keys.pop(keys.index(ko))
                
        if keys ==['Rfc', 'RegimenFiscal', 'Nombre' ]:
            keys = ['Rfc', 'Nombre', 'RegimenFiscal']
        if keys ==['RegimenFiscal', 'Rfc', 'Nombre' ]:
            keys = ['Rfc', 'Nombre', 'RegimenFiscal']
        if keys ==['Nombre', 'RegimenFiscal', 'Rfc']:
            keys = ['Rfc', 'Nombre', 'RegimenFiscal']
        if keys == ['cfdi:Retenciones', 'cfdi:Traslados']:
            keys = ['cfdi:Traslados','cfdi:Retenciones', ]
        if keys == ['cfdi:Traslados', 'TotalImpuestosTrasladados', 'cfdi:Retenciones', 'TotalImpuestosRetenidos']:
            keys = ['cfdi:Retenciones', 'TotalImpuestosRetenidos','cfdi:Traslados', 'TotalImpuestosTrasladados']

        #TAGS de Complemento de Comercio Exterior
        if 'cce11:Emisor' in keys:
            #print("keys: %s" % keys)
            keys2 = ['Version', 'TipoOperacion', 'ClaveDePedimento', 'CertificadoOrigen', 'NumCertificadoOrigen', 'Incoterm', 'Subdivision', 'Observaciones', 'TipoCambioUSD', 'TotalUSD',  'xmlns:cce11',  'xsi:schemaLocation', 'xmlns:xsi', 'cce11:Emisor', 'cce11:Receptor', 'cce11:Destinatario', 'cce11:Mercancias']
            if not 'NumCertificadoOrigen' in keys:
                keys2.remove('NumCertificadoOrigen')
            if not 'cce11:Destinatario' in keys:
                keys2.remove('cce11:Destinatario')
            keys = keys2  
            
            
        #TAGS de Complemento Detallista -- 1 --
        elif 'xmlns:detallista' in keys:
            # print "keys: %s" % keys
            keys2 = ['xmlns:detallista','xsi:schemaLocation','contentVersion','type','documentStructureVersion','documentStatus',
                     'detallista:requestForPaymentIdentification',
                     'detallista:specialInstruction',
                     'detallista:orderIdentification',
                     'detallista:AdditionalInformation',
                     'detallista:DeliveryNote',
                     'detallista:buyer',
                     'detallista:seller',
                     #'detallista:allowanceCharge',
                     '_value_not_grouped', #'detallista:lineItem',
                     'detallista:totalAmount',
                     'detallista:TotalAllowanceCharge'
                    ]
            for xkey in keys2:
                if not xkey in keys:
                    keys2.remove(xkey)
            keys = keys2
        #TAGS de Complemento Detallista  - Lineas de productos -- 2 --
        elif 'detallista:tradeItemIdentification' in keys:
            #print "keys: %s" % keys
            keys2 = ['detallista:tradeItemIdentification',
                     'detallista:alternateTradeItemIdentification',
                     'detallista:tradeItemDescriptionInformation',
                     'detallista:invoicedQuantity',
                     'detallista:grossPrice',
                     'detallista:netPrice',
                     'detallista:totalLineAmount'
                    ]
            for xkey in keys2:
                if not xkey in keys:
                    keys2.remove(xkey)
            keys = keys2
        #TAGS de Complemento Detallista  - Total en Lineas de productos -- 3 --
        elif 'detallista:grossAmount' in keys:
            #print "keys: %s" % keys
            keys2 = ['detallista:grossAmount', 'detallista:netAmount']
            for xkey in keys2:
                if not xkey in keys:
                    keys2.remove(xkey)
            keys = keys2
            
            
        for key_too in keys:
            key_item_sort.append([key_too, data_dict[key_too]])
        return key_item_sort    
    
    @api.one
    def _get_file_globals(self):
        ctx = self._context.copy()
        file_globals = {}
        invoice = self
        ctx.update({'date_work': invoice.date_invoice_tz})

        if not (invoice.journal_id.date_start <= invoice.date_invoice_tz and invoice.journal_id.date_end >= invoice.date_invoice_tz):
            raise UserError(_("Error !!!\nLa fecha de la factura está fuera del rango de Vigencia del Certificado, por favor revise."))
        
        
        fname_cer_pem = False
        try:
            fname_cer_pem = self.binary2file(
                invoice.journal_id.certificate_file_pem, 'odoo_' + (
                invoice.journal_id.serial_number or '') + '__certificate__',
                '.cer.pem')
        except:
            raise UserError(_("Error !!! \nEl archivo del Certificado no existe en formato PEM"))
        
        file_globals['fname_cer'] = fname_cer_pem
        # - - - - - - - - - - - - - - - - - - - - - - -
        fname_key_pem = False
        try:
            fname_key_pem = self.binary2file(
                invoice.journal_id.certificate_key_file_pem, 'odoo_' + (
                invoice.journal_id.serial_number or '') + '__certificate__',
                '.key.pem')
        except:
            raise UserError(_("Error !!! \nEl archivo de la llave (KEY) del Certificado no existe en formato PEM"))

        file_globals['fname_key'] = fname_key_pem
        # - - - - - - - - - - - - - - - - - - - - - - -
        fname_cer_no_pem = False
        try:
            fname_cer_no_pem = self.binary2file(
                invoice.journal_id.certificate_file, 'odoo_' + (
                invoice.journal_id.serial_number or '') + '__certificate__',
                '.cer')
        except:
            pass
        file_globals['fname_cer_no_pem'] = fname_cer_no_pem
        # - - - - - - - - - - - - - - - - - - - - - - -
        fname_key_no_pem = False
        try:
            fname_key_no_pem = self.binary2file(
                invoice.journal_id.certificate_key_file, 'odoo_' + (
                invoice.journal_id.serial_number or '') + '__certificate__',
                '.key')
        except:
            pass
        file_globals['fname_key_no_pem'] = fname_key_no_pem
        # - - - - - - - - - - - - - - - - - - - - - - -
        fname_pfx = False
        try:
            fname_pfx = self.binary2file(
                invoice.journal_id.certificate_pfx_file, 'odoo_' + (
                invoice.journal_id.serial_number or '') + '__certificate__',
                '.pfx')
        except:
            raise UserError(_("Error !!! \nEl archivo del Certificado no existe en formato PFX"))

        file_globals['fname_pfx'] = fname_pfx
        # - - - - - - - - - - - - - - - - - - - - - - -
        file_globals['password'] = invoice.journal_id.certificate_password
        # - - - - - - - - - - - - - - - - - - - - - - -
        if invoice.journal_id.fname_xslt:
            if (invoice.journal_id.fname_xslt[0] == os.sep or \
                invoice.journal_id.fname_xslt[1] == ':'):
                file_globals['fname_xslt'] = invoice.journal_id.fname_xslt
            else:
                file_globals['fname_xslt'] = os.path.join(
                    tools.config["root_path"], invoice.journal_id.fname_xslt)
        else:
            # Search char "," for addons_path, now is multi-path
            all_paths = tools.config["addons_path"].split(",")
            for my_path in all_paths:
                if os.path.isdir(os.path.join(my_path,
                    'l10n_mx_sat_models', 'SAT')):
                    # If dir is in path, save it on real_path
                    file_globals['fname_xslt'] = my_path and os.path.join(
                        my_path, 'l10n_mx_sat_models', 'SAT', 'cadenaoriginal_3_3',
                        'cadenaoriginal_3_3.xslt') or ''
                    ### TFD CADENA ORIGINAL XSLT ###
                    file_globals['fname_xslt_tfd'] = my_path and os.path.join(
                        my_path, 'l10n_mx_sat_models', 'SAT', 'cadenaoriginal_3_3',
                        'cadenaoriginal_TFD_1_1.xslt') or ''

                    break
        if not file_globals.get('fname_xslt', False):
            raise UserError(_("Advertencia !!! \nNo se tiene definido fname_xslt"))

        if not os.path.isfile(file_globals.get('fname_xslt', ' ')):
            raise UserError(_("Advertencia !!! \nNo existe el archivo [%s]. !") % (file_globals.get('fname_xslt', ' ')))

        file_globals['serial_number'] = invoice.journal_id.serial_number
        # - - - - - - - - - - - - - - - - - - - - - - -

        # Search char "," for addons_path, now is multi-path
        all_paths = tools.config["addons_path"].split(",")
        for my_path in all_paths:
            if os.path.isdir(os.path.join(my_path, 'l10n_mx_sat_models', 'SAT')):
                # If dir is in path, save it on real_path
                file_globals['fname_xslt'] = my_path and os.path.join(
                    my_path, 'l10n_mx_sat_models', 'SAT','cadenaoriginal_3_3',
                    'cadenaoriginal_3_3.xslt') or ''
                ### TFD CADENA ORIGINAL XSLT ###
                file_globals['fname_xslt_tfd'] = my_path and os.path.join(
                    my_path, 'l10n_mx_sat_models', 'SAT', 'cadenaoriginal_3_3',
                    'cadenaoriginal_TFD_1_1.xslt') or ''
        return file_globals
             
    def return_index_floats(self,decimales):
        i = len(decimales) - 1
        indice = 0
        while(i > 0):
            if  decimales[i] != '0':
                indice = i
                i = -1
            else:
                i-=1
        return  indice
    
    @api.one
    def write_cfd_data(self, cfd_datas):
        """
        @param cfd_datas : Dictionary with data that is used in facturae CFD and CFDI
        """
        if not cfd_datas:
            cfd_datas = {}
        # obtener cfd_data con varios ids
        # for id in ids:
        data = {}
        cfd_data = cfd_datas
        NoCertificado = cfd_data.get('Comprobante', {}).get('NoCertificado', '')
        certificado = cfd_data.get('Comprobante', {}).get('Certificado', '')
        sello = cfd_data.get('Comprobante', {}).get('Sello', '')
        cadena_original = cfd_data.get('cadena_original', '')
        data = {
            'no_certificado': NoCertificado,
            'certificado': certificado,
            'sello': sello,
            'cadena_original': cadena_original,
        }
        self.write(data)
        return True

    
    def _get_einvoice_complement_dict(self, comprobante):
        return comprobante

    @api.one
    def _get_facturae_invoice_dict_data(self):
        invoice_datas = []
        invoice_data_parents = []
        invoice = self
        invoice_data_parent = {}
        ## Tipo de Documento ####
        tipoComprobante = invoice.type_document_id.code
        # else:
        #     raise UserError(_("Solo puede Timbrar facturas de Clientes"))
        if invoice.type not in ('out_invoice','out_refund'):
            raise UserError(_("Solo puede Timbrar facturas de Clientes"))

        date_ctx = {'date': invoice.date_invoice_tz and time.strftime(
            '%Y-%m-%d', time.strptime(invoice.date_invoice_tz,
            '%Y-%m-%d %H:%M:%S')) or False}

        # Inicia seccion: Comprobante
        invoice_data_parent['cfdi:Comprobante'] = {}
        # default data
        invoice_data_parent['cfdi:Comprobante'].update(
                    {'xmlns:cfdi'   : "http://www.sat.gob.mx/cfd/3",
                     'xmlns:xs'     : "http://www.w3.org/2001/XMLSchema",
                     'xmlns:xsi'    : "http://www.w3.org/2001/XMLSchema-instance",
                     'xsi:schemaLocation': "http://www.sat.gob.mx/cfd/3 http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv33.xsd",
                     'Version': "3.3", })
        
        xnumber_work = re.findall('\d+', invoice.number)  or False
        number_work = xnumber_work and xnumber_work[0] or xnumber_work
        
        currency = invoice.currency_id
        rate = invoice.currency_id.with_context(date_ctx).rate
        rate = rate != 0 and 1.0/rate or 0.0
        if rate >= 0.99999 and rate <= 1.00001:#rate==1.0:
            rate = 1
        else:            
            rate = '%.4f' % rate or 1
        ## Guardando el Tipo de Cambio ##
        self.write({'tipo_cambio': rate})

        invoice_data_parent['cfdi:Comprobante'].update({
            'Folio': int(number_work),
            'Fecha': invoice.date_invoice_tz and time.strftime('%Y-%m-%dT%H:%M:%S', time.strptime(invoice.date_invoice_tz, '%Y-%m-%d %H:%M:%S')) or '',
            'TipoDeComprobante': tipoComprobante,
            'NoCertificado': '@',
            'Sello': '',
            'Certificado': '@',
            'SubTotal': "%.2f" % (invoice.amount_untaxed or 0.0),
            'Total' : "%.2f" % ((self.amount_total if self.amount_discount == 0.0 else  \
                                 (self.amount_subtotal - self.amount_discount + self.amount_tax)) or 0.0),
            'Serie' : invoice.journal_id.sequence_id.prefix and invoice.journal_id.sequence_id.prefix.replace('/','').replace(' ','').replace('-','') or '',
            'MetodoPago': invoice.metodo_pago_id.code if invoice.metodo_pago_id else "",
            'LugarExpedicion': invoice.address_issued_id.zip_sat_id.code,
            'Moneda': invoice.currency_id.name.upper(),
            'TipoCambio': rate,
            'FormaPago': invoice.pay_method_ids and ','.join([x.code for x in invoice.pay_method_ids]) or "99",
            'CondicionesDePago': invoice.payment_term_id.name if invoice.payment_term_id else '',
        })
        

        ### CondicionesDePago ###
        if invoice_data_parent['cfdi:Comprobante']['CondicionesDePago']  in (False, '', ' '):
            invoice_data_parent['cfdi:Comprobante'].pop('CondicionesDePago')

        if invoice_data_parent['cfdi:Comprobante']['Serie']  in (False, '', ' '):
            invoice_data_parent['cfdi:Comprobante'].pop('Serie')
            
        if self.amount_discount:
            invoice_data_parent['cfdi:Comprobante'].update({
                                                    'Descuento': "%.2f" % (self.amount_discount or 0.0),
                                                    'SubTotal': "%.2f" % self.amount_subtotal,
                                                    })      
        # Termina seccion: Comprobante
        # Inicia seccion: Emisor
        partner_obj = self.partner_id
        address_invoice = invoice.address_issued_id or False
        address_invoice_parent = invoice.company_emitter_id and invoice.company_emitter_id.address_invoice_parent_company_id or False
        if not address_invoice_parent:
            address_invoice_parent = invoice.company_emitter_id.partner_id
        if not address_invoice:
            raise UserError(_('Advertencia !!\nNo ha definido dirección de emisión...'))
        if not address_invoice_parent:
            raise UserError(_('Advertencia !!\nNo ha definido la dirección de la Compañía...'))
        if not address_invoice_parent.vat:
            raise UserError(_('Advertencia !!\nNo ha definido el RFC de la Compañía...'))
        
        self.check_partner_data(invoice.partner_id, True)
        self.check_partner_data(invoice.address_issued_id, True)
        self.check_partner_data(address_invoice_parent, False)
    
        invoice_data = invoice_data_parent['cfdi:Comprobante']


        ### Agregando los CFDI Relacionados ####
        if self.type_rel_cfdi_ids:
            if not self.type_rel_id:
                raise UserError("Error !\nDebes identificar el Tipo de Relacion para los CFDI.")
            cfdi_relacionado_list = []
            for cfdi_rel in self.type_rel_cfdi_ids:
                cfdi_relacionado_list.append({'UUID': cfdi_rel.invoice_id.cfdi_folio_fiscal})

                cfdi_rel.invoice_id.write({'deposit_invoice_used': True, 'deposit_invoice_rel_id': self.id})

            invoice_data['cfdi:CfdiRelacionados'] = {
                                                    'cfdi:CfdiRelacionado': cfdi_relacionado_list,
                                                    'TipoRelacion': self.type_rel_id.code,
                                                    }

                                                    
        invoice_data['cfdi:Emisor'] = {}

        if not address_invoice_parent.regimen_fiscal_id:
            raise UserError("Error!\nLa Compañía %s no tiene definido un Regimen Fiscal, por lo cual no puede emitir el Recibo CFDI." % address_invoice_parent.name)

        invoice_data['cfdi:Emisor'].update({

            'Rfc': address_invoice_parent.vat_split,
            'Nombre': address_invoice_parent.name or '',
            'RegimenFiscal': address_invoice_parent.regimen_fiscal_id.code or '',
            
        })

        # Termina seccion: Emisor
        # Inicia seccion: Receptor
        parent_obj = self.partner_id.commercial_partner_id
        #parent_obj = partner_obj.browse(cr, uid, parent_id, context=context)
        if not parent_obj.vat:
            raise UserError(_('Advertencia !!\nNo ha definido el RFC para la Empresa [%s] !') % (parent_obj.name))
        if parent_obj.vat[0:2].upper() != 'MX':
            rfc = 'XAXX010101000'
        else:
            rfc = parent_obj.vat_split
            #((parent_obj._columns.has_key('vat_split')\
            #    and parent_obj.vat_split or parent_obj.vat)\
            #    or '').replace('-', ' ').replace(' ','').upper()
        address_invoice = self.partner_id
        invoice_data['cfdi:Receptor'] = {}
        invoice_data['cfdi:Receptor'].update({
            'Rfc': rfc.upper(),
            'Nombre': (parent_obj.name or ''),
            'UsoCFDI': invoice.uso_cfdi_id.code,

        })
        
        ### Para Complemento de comercio Exterior ####
        # if address_invoice.country_id.sat_code.code.upper() != 'MEX':
        #     if not address_invoice.num_reg_trib:
        #         raise UserError(_("Error!\nPara clientes con dirección en el extranjero es necesario ingresar el registro de identidad fiscal."))
        #     invoice_data['cfdi:Receptor'].update({
        #         'ResidenciaFiscal': address_invoice.country_id.sat_code.code,
        #         'NumRegIdTrib': address_invoice.num_reg_trib,
        #         })

        # Termina seccion: Receptor
        # Inicia seccion: Conceptos
        total_impuestos_trasladados = 0.0
        total_impuestos_retenidos = 0.0

        invoice_data['cfdi:Conceptos'] = []
        account_tax_obj = self.env['account.tax']
        for line in self.invoice_line_ids:
            sat_product_id = line.product_id.sat_product_id
            if not sat_product_id:
                sat_product_id = line.product_id.categ_id.sat_product_id
            if not sat_product_id:
                raise UserError(_("Error!\nEl producto:\n %s \nNo cuenta con la Clave de Producto/Servicio del SAT." % line.product_id.name))
            sat_uom_id = line.uom_id.sat_uom_id
            if not sat_uom_id:
                raise UserError(_("Error!\nLa Unidad de Medida:\n %s \nNo cuenta con la Clave SAT." % line.uom_id.name))
            ## METODO PARA AÑADIR COMPLEMENTOS ##
            # self.add_complements_with_concept_cfdi(line, line.product_id )

            price_unit = line.quantity != 0 and line.price_subtotal / line.quantity or 0.0

            cantidad = "%.2f" % line.quantity or 0.0
            cantidad_qr = ""
            qr_cantidad_split = cantidad.split('.')
            decimales = qr_cantidad_split[1]
            index_zero = self.return_index_floats(decimales)
            decimales_res = decimales[0:index_zero+1]
            if decimales_res == '0':
                cantidad_qr = qr_cantidad_split[0]
            else:
                cantidad_qr = qr_cantidad_split[0]+"."+decimales_res


            concepto = {
                'ClaveProdServ': sat_product_id.code,
                'Cantidad': cantidad_qr,
                'ClaveUnidad': sat_uom_id.code,
                'Unidad': sat_uom_id.name,
                'Descripcion': line.name or '',
                'ValorUnitario': "%.2f" % (price_unit or 0.0),
                'Importe': "%.2f" % (line.price_subtotal or 0.0),
            # Falta el Descuento #
            }

            if line.discount:
                concepto.update({
                    'ValorUnitario': "%.2f" % ((line.amount_subtotal / line.quantity) or 0.0),
                    'Importe': "%.2f" % (line.amount_subtotal or 0.0),
                    'Descuento': "%.2f" % (line.amount_discount),
                    })

            ### Extension que permitira extender los modulos ###
            concepto = line.update_properties_concept(concepto)

            ### Añadiendo el No de Indentificacion
            product_code = ""
            if line.product_id.no_identity_type:
                if line.product_id.no_identity_type != 'none':
                    if line.product_id.no_identity_type == 'default_code':
                        product_code = line.product_id.default_code 
                    elif line.product_id.no_identity_type == 'barcode':
                        product_code = line.product_id.barcode
                    else:
                        product_code = line.product_id.no_identity_other

            if product_code:
                concepto.update({'NoIdentificacion': product_code})            

            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)

            taxes_line = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']

            ### Si hay impuestos en el Concepto agregamos el nodo, si no se omite
            if taxes_line:
                concepto.update({'cfdi:Impuestos':{}}) 

            for tax in taxes_line:
                tax_id = tax['id']
                tax_name = tax['name']
                tax_amount = tax['amount']
                tax_br = account_tax_obj.browse(tax_id)
                sat_tipo_factor = tax_br.sat_tasa_cuota
                sat_code_tax = tax_br.sat_code_tax
                base_tax = line.price_subtotal
                sat_tasa_cuota = abs(tax_br.amount)
                if not tax_br.sat_tasa_cuota:
                    raise UserError(_("Error no cuentas con el valor Tasa/Custo del Impuesto:\n%s" % tax_name))
                if not tax_br.sat_code_tax:
                    raise UserError(_("Error no cuentas con el valor Clave de Impuesto SAT del Impuesto:\n%s" % tax_name))

                if sat_tasa_cuota > 1.1:
                    sat_tasa_cuota = sat_tasa_cuota/100.0
                ## Definiendo el Tipo de Impuesto #
                ## Montos Positivos Traslados ###
                if tax_amount >= 0:
                    if sat_tipo_factor == 'Exento':
                        impuestos_traslados = concepto['cfdi:Impuestos'].setdefault(
                            'cfdi:Traslados', [])
                        ## Almacenando los Globales ##
                        # total_impuestos_trasladados += abs(tax_amount)

                        ## Comienza por Detalle #
                        impuesto_dict = {'cfdi:Traslado':
                            {
                                'Base': "%.2f" % (base_tax or 0.0),
                                'Impuesto': sat_code_tax,
                                'TipoFactor': sat_tipo_factor,
                                # 'TasaOCuota': "%.6f" % (sat_tasa_cuota),
                                # 'Importe': "%.2f" % (tax_amount),
                            }
                        }

                    else:
                        impuestos_traslados = concepto['cfdi:Impuestos'].setdefault(
                            'cfdi:Traslados', [])
                        ## Almacenando los Globales ##
                        total_impuestos_trasladados += abs(tax_amount)

                        ## Comienza por Detalle #
                        impuesto_dict = {'cfdi:Traslado':
                            {
                                'Base': "%.2f" % (base_tax or 0.0),
                                'Impuesto': sat_code_tax,
                                'TipoFactor': sat_tipo_factor,
                                'TasaOCuota': "%.6f" % (sat_tasa_cuota),
                                'Importe': "%.2f" % (tax_amount),
                            }
                        }

                    impuestos_traslados.append(impuesto_dict)
                else:
                    ## Almacenando los Globales ##
                    total_impuestos_retenidos += abs(tax_amount)
                    ## Comienza por Detalle ##
                    impuestos_retenciones = concepto['cfdi:Impuestos'].setdefault(
                        'cfdi:Retenciones', [])
                    impuesto_dict = {'cfdi:Retencion':
                                {
                                 'Base': "%.2f" % (base_tax or 0.0),
                                 'Impuesto': sat_code_tax,
                                 'TipoFactor': sat_tipo_factor,
                                 'TasaOCuota': "%.6f" % (abs(sat_tasa_cuota)),
                                 'Importe': "%.2f" % (abs(tax_amount)),
                                 }
                                 }

                    impuestos_retenciones.append(impuesto_dict)    

            if 'import_ids' in ((release.major_version == "9.0" and line._columns) or (release.major_version in ("10.0","11.0") and line._fields) or {}) and line.import_ids:
                info_aduanera = []
                if self.cfdi_complemento != 'comercio_exterior':
                    for pedimento in line.import_ids:
                        informacion_aduanera = {
                            'NumeroPedimento': pedimento.name or '',
                            # 'Fecha': pedimento.date or '',
                            # 'Aduana': pedimento.sat_aduana_id.code,
                        }
                        info_aduanera.append(informacion_aduanera)
                    if info_aduanera:
                        concepto.update({'cfdi:InformacionAduanera': info_aduanera})
                        
            if sat_product_id.complemento_que_debe_incluir:
                concepto = line.add_complements_with_concept_cfdi(concepto)
                #invoice_data['cfdi:Conceptos'].append({'cfdi:Concepto': node_with_complement})
                #if not node_with_complement:
                #    raise UserError(_("Error!\nLa clave:\n %s\nDel Producto:\n %s\nDispara un complemento, el cual no esta establecido, desactive esta opción o genere un complemento." % ("[ "+sat_product_id.code+" ] "+sat_product_id.name,line.product_id.name)))

            ### Agregando  el Concepto al listado de Conceptos ####
            invoice_data['cfdi:Conceptos'].append({'cfdi:Concepto': concepto})

            # Termina seccion: Conceptos

        # Inicia seccion: impuestos
        # Si hay impuestos en la Fatura se agrega el nodo de Impuestos
        if invoice.tax_line_ids:
            invoice_data['cfdi:Impuestos'] = {}
            invoice_data['cfdi:Impuestos'].update({
                # 'TotalImpuestosTrasladados': "%.2f"%( total_impuestos_trasladados or 0.0),
            })
            invoice_data['cfdi:Impuestos'].update({
                # 'TotalImpuestosRetenidos': "%.2f"%( total_impuestos_retenidos or 0.0 )
            })

            invoice_data_impuestos = invoice_data['cfdi:Impuestos']
            # invoice_data_impuestos['cfdi:Traslados'] = []
            # invoice_data_impuestos['Retenciones'] = []

        tax_names = []
        TotalImpuestosTrasladados = 0
        TotalImpuestosRetenidos = 0

        # if sat_tipo_factor == 'Exento'
        # for line_tax_id in invoice.tax_line_ids:
        #     sat_tipo_factor = line_tax_id.tax_id.sat_tasa_cuota
        #     sat_code_tax = line_tax_id.tax_id.sat_code_tax
        #     sat_tasa_cuota = line_tax_id.tax_id.amount
        #
        #     tax_name = sat_code_tax
        #     tax_names.append(tax_name)
        #     line_tax_id_amount = abs(line_tax_id.amount or 0.0)
        #     if line_tax_id.amount >= 0:
        #         impuesto_list = invoice_data_impuestos.setdefault(
        #                 'cfdi:Traslados', [])
        #         # impuesto_list = invoice_data_impuestos['cfdi:Traslados']
        #         impuesto_str = 'cfdi:Traslado'
        #         TotalImpuestosTrasladados += line_tax_id_amount
        #         invoice_data['cfdi:Impuestos'].update({
        #                         'TotalImpuestosTrasladados': "%.2f" % (TotalImpuestosTrasladados)
        #                         })
        #     else:
        #         # impuesto_list = invoice_data_impuestos['Retenciones']
        #         impuesto_list = invoice_data_impuestos.setdefault(
        #             'cfdi:Retenciones', [])
        #         impuesto_str = 'cfdi:Retencion'
        #         TotalImpuestosRetenidos += line_tax_id_amount
        #         invoice_data['cfdi:Impuestos'].update({
        #                         'TotalImpuestosRetenidos': "%.2f" % (TotalImpuestosRetenidos)
        #                         })
        #     if abs(sat_tasa_cuota) > 1:
        #         sat_tasa_cuota = abs(sat_tasa_cuota)/100.0
        #     if line_tax_id.amount >= 0:
        #         # print "######## invoice_data['cfdi:Impuestos']",invoice_data['cfdi:Impuestos']
        #         impuesto_dict = {impuesto_str:
        #                         {
        #                         'Impuesto': tax_name,
        #                         'TipoFactor': sat_tipo_factor,
        #                         'TasaOCuota': "%.6f" % (sat_tasa_cuota),
        #                         'Importe': "%.2f" % (line_tax_id_amount),
        #                          }
        #                          }
        #     else:
        #         impuesto_dict = {impuesto_str:
        #                         {
        #                         'Impuesto': tax_name,
        #                         #'TipoFactor': sat_tipo_factor,
        #                         #'TasaOCuota': "%.6f" % (sat_tasa_cuota),
        #                         'Importe': "%.2f" % (line_tax_id_amount),
        #                          }
        #                          }
        #     # if sat_tasa_cuota > 1.1:
        #     #     sat_tasa_cuota = sat_tasa_cuota/100.0
        #     # if line_tax_id.amount >= 0:
        #     #     impuesto_dict = {impuesto_str:
        #     #                     {
        #     #                     'Impuesto': tax_name,
        #     #                     'TipoFactor': sat_tipo_factor,
        #     #                     'TasaOCuota': "%.6f" % (abs(sat_tasa_cuota)),
        #     #                     'Importe': "%.2f" % (line_tax_id_amount),
        #     #                      }
        #     #                      }
        #     # else:
        #     #     impuesto_dict = {impuesto_str:
        #     #                     {
        #     #                     'Impuesto': tax_name,
        #     #                     'Importe': "%.2f" % (line_tax_id_amount),
        #     #                      }
        #     #                      }
        #
        #     impuesto_list.append(impuesto_dict)

        ########### AGRUPACION ###############
        ## Si Termino podemos recorrerlos y agruparlos
        # invoice_data['cfdi:Impuestos']
        if invoice.tax_line_ids:
            self.env.cr.execute("""
                select account_tax.price_include from account_invoice_tax 
                       join account_tax on account_tax.id = account_invoice_tax.tax_id 
                       and account_invoice_tax.invoice_id = %s
                       group by account_tax.price_include;

                """, (invoice.id, ))
            cr_res = self.env.cr.fetchall()
            price_include_list = [x[0] for x in cr_res]
            # print "########## price_include_list >>>> ",price_include_list
            if len(price_include_list) > 1:
                taxes_xml_to_grouped = invoice_data['cfdi:Impuestos']
                if 'cfdi:Traslados' in taxes_xml_to_grouped:
                    taxes_xml_to_grouped_traslados = taxes_xml_to_grouped['cfdi:Traslados']
                    grouped_taxes_traslados = {

                    }
                    for tax_tr in taxes_xml_to_grouped_traslados:
                        tax_base_tasa_name = tax_tr['cfdi:Traslado']['Impuesto']+"_"+tax_tr['cfdi:Traslado']['TasaOCuota']+"_"+tax_tr['cfdi:Traslado']['TipoFactor']
                        if tax_base_tasa_name not in grouped_taxes_traslados:
                            grouped_taxes_traslados[tax_base_tasa_name] = {'cfdi:Traslado': {
                                                'TipoFactor': tax_tr['cfdi:Traslado']['TipoFactor'],
                                                'TasaOCuota':  tax_tr['cfdi:Traslado']['TasaOCuota'],
                                                'Impuesto': tax_tr['cfdi:Traslado']['Impuesto'],
                                                'Importe': tax_tr['cfdi:Traslado']['Importe'],
                                                }

                                                }
                        else:
                            tax_grouped_amount = grouped_taxes_traslados[tax_base_tasa_name]['cfdi:Traslado']['Importe']
                            tax_to_sum_amount = tax_tr['cfdi:Traslado']['Importe']
                            tax_grouped_amount = float(tax_grouped_amount)+float(tax_to_sum_amount)
                            grouped_taxes_traslados[tax_base_tasa_name]['cfdi:Traslado']['Importe'] =  "%.2f" % tax_grouped_amount
                    grouped_taxes_traslados_list = []
                    for tax_group in grouped_taxes_traslados.keys():
                        grouped_taxes_traslados_list.append(grouped_taxes_traslados[tax_group])
                    invoice_data['cfdi:Impuestos']['cfdi:Traslados'] = grouped_taxes_traslados_list

        # if 'cfdi:Retenciones' in taxes_xml_to_grouped:
        #     taxes_xml_to_grouped_retenciones = taxes_xml_to_grouped['cfdi:Retenciones']
        
        # invoice_data['cfdi:Impuestos'].update({
        #     'TotalImpuestosTrasladados': "%.2f" % (TotalImpuestosTrasladados),
        # })
        
        # #### Pensado para CFDI Traslado ######
        # if not invoice.tax_line_ids:
        #     if invoice.type_document_id.code in ('I','E'):
        #         raise UserError(_("La Factura no contiene Impuestos"))
        #     print "###  ????"
        #     print "####### invoice data >>> ",invoice_data
        #     invoice_data.pop('cfdi:Impuestos')
        # print "### invoice_data 2 >>> ",invoice_data
        ##### FIN ######
        # tax_requireds = ['IVA', 'IEPS']
        # for tax_required in tax_requireds:
        #     if tax_required in tax_names:
        #         continue
        #     invoice_data_impuestos['cfdi:Traslados'].append({'cfdi:Traslado': {
        #         'impuesto': tax_required,
        #         'tasa': "%.2f" % (0.0),
        #         'importe': "%.4f" % (0.0),
        #     }})
        # Termina seccion: impuestos
        
        if 'cfdi_complemento' in ((release.major_version == "9.0" and self._columns) or (release.major_version in ("10.0","11.0") and self._fields) or {}) and self.cfdi_complemento:
            invoice_data_parent = invoice._get_einvoice_complement_dict(invoice_data_parent)
        invoice_data_parents.append(invoice_data_parent)
        invoice_data_parent['state'] = invoice.state
        invoice_data_parent['invoice_id'] = invoice.id
        invoice_data_parent['type'] = invoice.type
        invoice_data_parent['invoice_datetime'] = invoice.invoice_datetime
        invoice_data_parent['date_invoice_tz'] = invoice.date_invoice_tz
        invoice_data_parent['currency_id'] = invoice.currency_id.id
        

        date_ctx = {'date': invoice.date_invoice_tz and time.strftime(
            '%Y-%m-%d', time.strptime(invoice.date_invoice_tz,
            '%Y-%m-%d %H:%M:%S')) or False}

        currency = self.currency_id
        rate = self.currency_id.with_context(date_ctx).rate
        rate = rate != 0 and 1.0/rate or 0.0

        invoice_data_parent['rate'] = rate

        invoice_datetime = invoice_data_parents[0].get('invoice_datetime',
            {}) and datetime.datetime.strptime(invoice_data_parents[0].get(
            'invoice_datetime', {}), '%Y-%m-%d %H:%M:%S').strftime(
            '%Y-%m-%d') or False
        if not invoice_datetime:
            raise UserError(_("Fecha de Factura vacía!\nNo es posible obtener la información sin la fecha, asegúrese que el Estado de la factura no es Borrador o que la Fecha Factura se encuentre vacía"))
        #invoice = self.browse(context={'date': invoice_datetime})[0]

        return invoice_data_parents

    ### Permite Añadir Complementos por Conceptos ###
    ############### CFDI 3.3 #################
    @api.multi
    def add_complements_with_concept_cfdi(self, invoice_line, product):
        # invoice_line = linea de la Factura (Browse Record)
        # product = producto de la linea (Browse Record)
        node_with_complement = {

        }
        return node_with_complement
    
    
    def validate_scheme_facturae_xml(self, datas_xmls=[], facturae_version = None, facturae_type="cfdv", scheme_type='xsd'):
        if not datas_xmls:
            datas_xmls = []
        certificate_lib = self.env['facturae.certificate.library']
        for data_xml in datas_xmls:
            (fileno_data_xml, fname_data_xml) = tempfile.mkstemp('.xml', 'odoo_' + (False or '') + '__facturae__' )
            f = open(fname_data_xml, 'wb')
            data_xml = data_xml.replace("&amp;", "Y")#Replace temp for process with xmlstartlet
            f.write( data_xml )
            f.close()
            os.close(fileno_data_xml)
            all_paths = tools.config["addons_path"].split(",")
            for my_path in all_paths:
                if os.path.isdir(os.path.join(my_path, 'l10n_mx_sat_models', 'SAT')):
                    # If dir is in path, save it on real_path
                    fname_scheme = my_path and os.path.join(my_path, 'l10n_mx_sat_models', 'SAT', facturae_type + facturae_version +  '.' + scheme_type) or ''
                    #fname_scheme = os.path.join(tools.config["addons_path"], u'l10n_mx_facturae', u'SAT', facturae_type + facturae_version +  '.' + scheme_type )
                    fname_out = certificate_lib.b64str_to_tempfile(base64.encodestring(''), file_suffix='.txt', file_prefix='odoo__' + (False or '') + '__schema_validation_result__' )
                    result = certificate_lib.check_xml_scheme(fname_data_xml, fname_scheme, fname_out)
                    if result: #Valida el xml mediante el archivo xsd
                        raise UserError(_("Error al validar la estructura del xml !!!\n Validación de XML versión %s:\n%s" % (facturae_version, result)))
        return True                     
    
    
    @api.one
    def _get_facturae_invoice_xml_data(self):
        context = self._context.copy()
        invoice = self
        comprobante = 'cfdi:Comprobante'
        emisor = 'cfdi:Emisor'
        receptor = 'cfdi:Receptor'
        concepto = 'cfdi:Conceptos'
        facturae_version = '3.3'
        data_dict = self._get_facturae_invoice_dict_data()
        data_dict = data_dict[0][0]
        doc_xml = self.dict2xml({comprobante: data_dict.get(comprobante)})

        invoice_number = "sn"
        (fileno_xml, fname_xml) = tempfile.mkstemp(
            '.xml', 'odoo_' + (invoice_number or '') + '__facturae__')
        fname_txt = fname_xml + '.txt'
        f = open(fname_xml, 'w')
        doc_xml.writexml(
            f, indent='    ', addindent='    ', newl='\r\n', encoding='UTF-8')
        f.close()
        os.close(fileno_xml)
        (fileno_sign, fname_sign) = tempfile.mkstemp('.txt', 'odoo_' + (
            invoice_number or '') + '__facturae_txt_md5__')
        os.close(fileno_sign)

        context.update({
            'fname_xml': fname_xml,
            'fname_txt': fname_txt,
            'fname_sign': fname_sign,
        })
        context.update(self._get_file_globals()[0])
        fname_txt, txt_str = self.with_context(context)._xml2cad_orig()
        data_dict['cadena_original'] = txt_str
        msg2=''

        if not txt_str:
            cadena_original_r  = open(fname_txt, "r")
            txt_str = cadena_original_r.read()
            if not txt_str:
                raise UserError(_("Error en la Cadena Original !!!\nNo puedo obtener la Cadena Original del Comprobante. Revise su configuración.\n%s" % (msg2)))

        if not data_dict[comprobante].get('Folio', ''):
            raise UserError(_("Error en Folio !!!\nNo puedo obtener el Folio del Comprobante. Antes de generar poder generar el XML debe tener la factura Abierta.\n%s" % (msg2)))
        

        context.update({'fecha': data_dict[comprobante]['Fecha']})
        
        nodeComprobante = doc_xml.getElementsByTagName(comprobante)[0]

        NoCertificado = self._get_noCertificado(context['fname_cer'])
        if not NoCertificado:
            raise UserError(_("Error en Número de Certiicado !!!\nNo puedo obtener el Número de Certificado del Comprobante. Revise su configuración.\n%s" % (msg2)))
        nodeComprobante.setAttribute("NoCertificado", NoCertificado)
        data_dict[comprobante]['NoCertificado'] = NoCertificado

        cert_str = self._get_certificate_str(context['fname_cer'])
        if not cert_str:
            raise UserError(_("Error en Certiicado !!!\nNo puedo obtener el Certificado del Comprobante. Revise su configuración.\n%s" % (msg2)))

        cert_str = cert_str.replace(' ', '').replace('\n', '')
        nodeComprobante.setAttribute("Certificado", cert_str)
        data_dict[comprobante]['Certificado'] = cert_str
        
        ### SELLO ###
        context['cadena_original'] = txt_str
        context.update({'xml_prev':doc_xml.toxml('UTF-8')})
        sign_str = self.with_context(context)._get_sello()

        ### Guardando la Cadena Original ####
        self.write({'cfdi_cadena_original':txt_str})

        if not sign_str:
            raise UserError(_("Error en Sello !!!\nNo puedo generar el Sello del Comprobante. Revise su configuración.\n%s" % (msg2)))

        nodeComprobante.setAttribute("Sello", sign_str)
        data_dict[comprobante]['Sello'] = sign_str

        #nodeComprobante.removeAttribute('anoAprobacion')
        #nodeComprobante.removeAttribute('noAprobacion')
        x = doc_xml.documentElement
        nodeReceptor = doc_xml.getElementsByTagName(receptor)[0]
        nodeConcepto = doc_xml.getElementsByTagName(concepto)[0]
        x.insertBefore(nodeReceptor, nodeConcepto)

        self.write_cfd_data(data_dict)

        if context.get('type_data') == 'dict':
            return data_dict
        if context.get('type_data') == 'xml_obj':
            return doc_xml
        data_xml = doc_xml.toxml('UTF-8')
        data_xml = codecs.BOM_UTF8 + data_xml

        fname_xml = (data_dict[comprobante][emisor]['Rfc'] or '') + '_' + \
            (data_dict[comprobante].get('Serie', '') or '') + '_' + \
            (str(data_dict[comprobante].get('Folio', '')) or '') + '.xml'
        data_xml = data_xml.replace(
            '<?xml version="1.0" encoding="UTF-8"?>', '<?xml version="1.0" encoding="UTF-8"?>\n')

        if self.company_id.validate_schema:
            self.validate_scheme_facturae_xml([data_xml], facturae_version)

        #data_dict.get('Comprobante',{})
        return fname_xml, data_xml
    
    @api.one
    def get_driver_cfdi_sign(self):
        """function to inherit from module driver of pac and add particular function"""
        return {}

    @api.one
    def get_driver_cfdi_cancel(self):
        """function to inherit from module driver of pac and add particular function"""
        return {}
                                        
                                        
    ####################################
    @api.one
    def do_something_with_xml_attachment(self, attach):
        return True


    @api.model
    def get_cfdi_cadena(self, xslt_path, cfdi_as_tree):
        xslt_root = etree.parse(tools.file_open(xslt_path))
        return str(etree.XSLT(xslt_root)(cfdi_as_tree))

    @api.model
    def _get_einvoice_cadena_tfd(self, cfdi_signed):
        self.ensure_one()
        #get the xslt path
        file_globals = self._get_file_globals()[0]
        if 'fname_xslt_tfd' in file_globals:
            xslt_path = file_globals['fname_xslt_tfd']
        else:
            raise UserError("Errr!\nNo existe en archivo XSLT TFD en la carpeta SAT.")
        #get the cfdi as eTree
        cfdi = str(base64.decodestring(cfdi_signed))
        cfdi = fromstring(cfdi)
        cfdi = self.account_invoice_tfd_node(cfdi)
        #return the cadena
        return self.get_cfdi_cadena(xslt_path, cfdi)

    @api.model
    def account_invoice_tfd_node(self, cfdi):
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    
    @api.multi
    def invoice_validate(self):
        result = True
        if not self._context.get('already_open', False):
            result = super(AccountInvoice, self).invoice_validate()
        if not result:
            return result
        attachment_obj = self.env['ir.attachment']
        for invoice in self:
            if not (invoice.type in ('out_invoice','out_refund')) or not invoice.journal_id.use_for_cfdi:
                continue
            fname_invoice = invoice.fname_invoice
            _logger.info('Iniciando proceso para Timbrar factura: %s', fname_invoice)
            # Obtenemos el contenido del archivo XML a timbrar
            cfdi_state = invoice.cfdi_state
            if cfdi_state =='draft':
                _logger.info('Generando archivo XML a enviar a PAC. - Factura: %s', fname_invoice)
                fname, xml_data = invoice._get_facturae_invoice_xml_data()[0]
                _logger.info('Archivo XML creado. - Factura: %s', fname_invoice)
                invoice.write({
                            'xml_file_no_sign_index': xml_data,
                            'cfdi_state'            : 'xml_unsigned',
                            'cfdi_last_message'     : fields.Datetime.to_string(fields.Datetime.context_timestamp(
                                                                                invoice.with_context(tz=(self.env.user.partner_id.tz or 'America/Mexico_City')),
                                                                                datetime.datetime.now())
                                                                               ) + \
                                                        '=> Archivo XML generado exitosamente'
                    })
                cfdi_state = 'xml_unsigned'
                self.env.cr.commit()

            # Mandamos a Timbrar
            
            #invoice = self
            type = invoice.cfdi_pac
            if cfdi_state =='xml_unsigned' and not invoice.xml_file_signed_index:
                try:
                    index_xml = ''
                    msj = ''        
                    # Instanciamos la clase para la integración con el PAC
                    type__fc = invoice.get_driver_cfdi_sign() and invoice.get_driver_cfdi_sign()[0] or {}
                    #type__fc = type__fc[0] if type__fc else False
                    if type in type__fc.keys():
                        fname_invoice = invoice.fname_invoice and invoice.fname_invoice + \
                            '.xml' or ''
                        if not 'fname' in locals() or not 'xml_data' in locals():
                            """_logger.info('Por alguna razon esta reintentando iniciar el proceso de Timbrado - Factura: %s', fname_invoice)
                            _logger.info('cfdi_stat: %s - Factura: %s' % (cfdi_state, fname_invoice))
                            _logger.info('locals: %s', locals)
                            _logger.info('Saltando factura: %s', fname_invoice)
                            _logger.info('.·/\·.·/\·.·/\·.·/\·.·/\·.·/\·.·/\·.·/\·')
                            _logger.info('.·/\·.·/\·.·/\·.·/\·.·/\·.·/\·.·/\·.·/\·')
                            #continue
                            """
                            _logger.info('Re-intentando generar XML para timbrar - Factura: %s', fname_invoice)
                            fname, xml_data = invoice._get_facturae_invoice_xml_data()[0]
                        else:
                            _logger.info('Listo archivo XML a timbrar en el PAC - Factura: %s', fname_invoice)
                        fdata = base64.encodestring(xml_data)
                        _logger.info('Solicitando a PAC el Timbre para Factura: %s', fname_invoice)
                        res = type__fc[type](fdata)[0] #

                        _logger.info('Timbre entregado por el PAC - Factura: %s', fname_invoice)
                        msj = tools.ustr(res.get('msg', False))
                        index_xml = res.get('cfdi_xml', False)
                        invoice.write({'xml_file_signed_index' : index_xml})
                        ###### Recalculando la Cadena Original ############
                        cfdi_signed = fdata
                        cadena_tfd_signed = ""
                        try:
                            cadena_tfd_signed = invoice._get_einvoice_cadena_tfd(base64.encodestring(index_xml))
                        except:
                            cadena_tfd_signed = invoice.cfdi_cadena_original
                        invoice.cfdi_cadena_original = cadena_tfd_signed
                        ################ FIN ################

                        data_attach = {
                                'name'        : fname_invoice,
                                'datas'       : base64.encodestring(index_xml),
                                'datas_fname' : fname_invoice,
                                'description' : 'Archivo XML del Comprobante Fiscal Digital - Factura: %s' % (invoice.number),
                                'res_model'   : 'account.invoice',
                                'res_id'      : invoice.id,
                                'type'        : 'binary',
                            }
                        attach = attachment_obj.with_context({}).create(data_attach)
                        xres = invoice.do_something_with_xml_attachment(attach)
                        cfdi_state = 'xml_signed'    
                    else:
                        msj += _("No se encontró el Driver del PAC para %s" % (type))
                    invoice.write({'cfdi_last_message': invoice.cfdi_last_message + "\n-.-.-.-.-.-.-.-.-.-.-.-.-.\n" + \
                                fields.Datetime.to_string(fields.Datetime.context_timestamp(
                                                                                invoice.with_context(tz=(self.env.user.partner_id.tz or 'America/Mexico_City')),
                                                                                datetime.datetime.now())
                                                                               ) + \
                                                                ' => ' + msj})
                    self.env.cr.commit()
                except Exception:
                    error = tools.ustr(traceback.format_exc())
                    invoice.write({'cfdi_last_message': invoice.cfdi_last_message + "\n-.-.-.-.-.-.-.-.-.-.-.-.-.\n" + \
                                fields.Datetime.to_string(fields.Datetime.context_timestamp(
                                                                                invoice.with_context(tz=(self.env.user.partner_id.tz or 'America/Mexico_City')),
                                                                                datetime.datetime.now())
                                                                               ) + \
                                                                ' => ' + error})
                    _logger.error(error)
                    self.env.cr.commit()
                    return False

            # Generamos formato de Impresión
            if cfdi_state == 'xml_signed' or invoice.xml_file_signed_index:

                _logger.info('Generando PDF - Factura: %s', fname_invoice)
                cfdi_state = 'pdf'
                
                try:
                    msj = ''
                    #report_multicompany_obj = self.env['report.multicompany']
                    #report_ids = report_multicompany_obj.search([('model', '=', 'account.invoice')], limit=1) or False
                    #report_name = report_ids and report_ids.report_name or "account.report_invoice"
                    #format = 'pdf'
                    #pdf_report = False
                    """
                    if not report_ids.report_id.attachment_use: # report_name != 'account.report_invoice':
                    
                    if release.major_version == "9.0":
                        pdf_report = self.env['report'].get_pdf(invoice, report_name)
                    elif release.major_version == "10.0":
                        result = self.env['report'].get_pdf([invoice.id], report_name)
                            
                        data_attach = {
                                'name'        : fname_invoice + ".pdf",
                                'datas'       : base64.encodestring(result),
                                'datas_fname' : fname_invoice,
                                'description' : 'Archivo XML del Comprobante Fiscal Digital - Factura: %s' % (invoice.number),
                                'res_model'   : 'account.invoice',
                                'res_id'      : invoice.id,
                                'type'        : 'binary',
                            }
                        attach = attachment_obj.create(data_attach)
                    """
                    self.write({
                               'cfdi_last_message': self.cfdi_last_message + "\n-.-.-.-.-.-.-.-.-.-.-.-.-.\n" + \
                                fields.Datetime.to_string(fields.Datetime.context_timestamp(
                                                                                self.with_context(tz=(self.env.user.partner_id.tz or 'America/Mexico_City')),
                                                                                datetime.datetime.now())
                                                                               ) + \
                                                                u' => Archivo PDF generado satisfactoriamente',
                               })
                    cfdi_state = 'pdf'
                    _logger.info('PDF generado - Factura: %s', fname_invoice)
                    
                except Exception:
                    error = tools.ustr(traceback.format_exc())
                    self.write({'cfdi_last_message': self.cfdi_last_message + "\n-.-.-.-.-.-.-.-.-.-.-.-.-.\n" + \
                                fields.Datetime.to_string(fields.Datetime.context_timestamp(
                                                                                self.with_context(tz=(self.env.user.partner_id.tz or 'America/Mexico_City')),
                                                                                datetime.datetime.now())
                                                                               ) + \
                                                                u' => No se pudo generar el formato de Impresión, revise el siguiente Traceback:\n\n' + \
                                                                error})

                    _logger.error(error)
                    
                self.env.cr.commit()
            
            if cfdi_state == 'pdf' and invoice.partner_id.commercial_partner_id.envio_manual_cfdi:
                msj = _('No se enviaron los archivos por correo porque el Partner está marcado para no enviar automáticamente los archivos del CFDI (XML y PDF)')
                cfdi_state == 'sent'
                invoice.write({'cfdi_last_message': invoice.cfdi_last_message + "\n-.-.-.-.-.-.-.-.-.-.-.-.-.\n" + \
                                                fields.Datetime.to_string(fields.Datetime.context_timestamp(
                                                invoice.with_context(tz=(self.env.user.partner_id.tz or 'America/Mexico_City')),
                                                datetime.datetime.now())
                                               ) + \
                                                ' => ' + msj,
                                'cfdi_state': 'sent',
                                })
                self.env.cr.commit()
            # Enviamos al cliente los archivos de la factura
            elif cfdi_state == 'pdf' and not invoice.partner_id.commercial_partner_id.envio_manual_cfdi:
                _logger.info('Intentando enviar XML y PDF por mail al cliente - Factura: %s', fname_invoice)
                msj = ''
                state = ''
                partner_mail = invoice.partner_id.email or False
                user_mail = self.env.user.email or False

                company_id = invoice.company_id.id
                #invoice = self
                address_id = invoice.partner_id.address_get(['invoice'])['invoice']
                partner_invoice_address = address_id
                fname_invoice = invoice.fname_invoice or ''
                adjuntos = attachment_obj.search([('res_model', '=', 'account.invoice'), 
                                                  ('res_id', '=', invoice.id)])
                q = True
                attachments = []
                for attach in adjuntos:
                    if q and attach.name.endswith('.xml'):
                        attachments.append(attach.id)
                        break

                mail_compose_message_pool = self.env['mail.compose.message']
                #report_multicompany_obj = self.env['report.multicompany']
                #report_ids = report_multicompany_obj.search([('model', '=', 'account.invoice')], limit=1) or False            
                report_ids = invoice.journal_id.report_id or False #report_multicompany_obj.search([('model', '=', 'account.invoice')], limit=1) or False
                if report_ids:
                    report_name = report_ids.report_name
                    if report_name:
                        template_id = self.env['mail.template'].search([('model_id.model', '=', 'account.invoice'),
                                                                         ('company_id','=', company_id),
                                                                         ('name','not ilike', '%Portal%'),
                                                                         # ('report_template.report_name', '=',report_name)
                                                                        ], limit=1)                            

                    if template_id:
                        ctx = dict(
                            default_model='account.invoice',
                            default_res_id=invoice.id,
                            default_use_template=bool(template_id),
                            default_template_id=template_id.id,
                            default_composition_mode='comment',
                            mark_invoice_as_sent=True,
                        )
                        ## CHERMAN 
                        context2 = dict(self._context)
                        if 'default_journal_id' in context2:
                            del context2['default_journal_id']
                        if 'default_type' in context2:
                            del context2['default_type']
                        if 'search_default_dashboard' in context2:
                            del context2['search_default_dashboard']

                        xres = mail_compose_message_pool.with_context(context2).onchange_template_id(template_id=template_id.id, composition_mode=None,
                                                                                 model='account.invoice', res_id=invoice.id)
                        try:
                            try:
                                attachments.append(xres['value']['attachment_ids'][0][2][0])
                            except:
                                mail_attachments = (xres['value']['attachment_ids'])
                                for mail_atch in mail_attachments:
                                    if mail_atch[0] == 4:
                                        # attachments.append(mail_atch[1])
                                        attach_br = self.env['ir.attachment'].browse(mail_atch[1])
                                        if attach_br.name != fname_invoice+'.pdf':
                                            attach_br.write({'name': fname_invoice+'.pdf'})
                                        attachments.append(mail_atch[1])
                        except:
                            _logger.error('No se genero el PDF de la Factura, no se enviara al cliente. - Factura: %s', fname_invoice)
                        xres['value'].update({'attachment_ids' : [(6, 0, attachments)]})
                        message = mail_compose_message_pool.with_context(ctx).create(xres['value'])
                        _logger.info('Antes de  enviar XML y PDF por mail al cliente - Factura: %s', fname_invoice)
                        xx = message.send_mail_action()
                        _logger.info('Despues de  enviar XML y PDF por mail al cliente - Factura: %s', fname_invoice)
                        invoice.write({'cfdi_state': 'sent'})
                        msj = _("La factura fue enviada exitosamente por correo electrónico...")
                        cfdi_state == 'sent'
                        self.env.cr.commit()
                    else:
                        msj = _('Advertencia !!!\nRevise que su plantilla de correo esté asignada al Servidor de correo.\nTambién revise que tenga asignado el reporte a usar.\nLa plantilla está asociada a la misma Compañía')
                else:
                    msj = _('No se encontró definido el Reporte de Factura en el Diario Contable !!!\nRevise la configuración')

                
                invoice.write({'cfdi_last_message': invoice.cfdi_last_message + "\n-.-.-.-.-.-.-.-.-.-.-.-.-.\n" + \
                                                fields.Datetime.to_string(fields.Datetime.context_timestamp(
                                                invoice.with_context(tz=(self.env.user.partner_id.tz or 'America/Mexico_City')),
                                                datetime.datetime.now())
                                               ) + \
                                                ' => ' + msj,
                                })
            _logger.info('Fin proceso Timbrado - Factura: %s', fname_invoice)
            
            
            # Se encontraron que los archivos PDF se duplican
            adjuntos2 = attachment_obj.search([('res_model', '=', 'account.invoice'), ('res_id', '=', invoice.id)])
            x = 0
            for attach in adjuntos2:
                if attach.name.endswith('.pdf'):
                    x and attach.unlink()
                    if x: 
                        break
                    x += 1

        return result
        
    
class SaleOrder(models.Model):
    _inherit = "sale.order"    
    '''Inherit sale order to add a new field, Payment Terms'''
    
    
    @api.multi
    def _prepare_invoice(self):        
        res = super(SaleOrder, self)._prepare_invoice()
        res.update({'pay_method_ids':self.pay_method_id and [(6,0, [self.pay_method_id.id])] or False,
                    'acc_payment': self.acc_payment and self.acc_payment.id or False,
                    'uso_cfdi_id': self.uso_cfdi_id and self.uso_cfdi_id.id or False,
                    'metodo_pago_id' : self.payment_term_id and self.payment_term_id.metodo_pago_id and \
                                       self.payment_term_id.metodo_pago_id.id or False,                    
        })
        return res 


    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        super(SaleOrder, self).onchange_partner_id()
        if self.partner_invoice_id:
            self.pay_method_id = (self.partner_invoice_id.parent_id and self.partner_invoice_id.parent_id.pay_method_id.id) or \
                                 (self.partner_invoice_id.pay_method_id and self.partner_invoice_id.pay_method_id.id) or False
            self.uso_cfdi_id   = (self.partner_invoice_id.parent_id and self.partner_invoice_id.parent_id.uso_cfdi_id.id) or \
                                 (self.partner_invoice_id.uso_cfdi_id and self.partner_invoice_id.uso_cfdi_id.id) or False
                
            bank_partner_id = self.env['res.partner.bank'].search([('partner_id', '=', self.partner_invoice_id.parent_id and self.partner_invoice_id.parent_id.id or self.partner_invoice_id.id)])
            if bank_partner_id:
                self.acc_payment = bank_partner_id and bank_partner_id[0].id or False    


class AccountInvoiceLine(models.Model):
    _name = 'account.invoice.line'
    _inherit ='account.invoice.line'

    
    ### Permite Añadir Complementos por Conceptos ###
    ############### CFDI 3.3 #################
    def add_complements_with_concept_cfdi(self, concepto):
        # invoice_line = linea de la Factura (Browse Record)
        # product = producto de la linea (Browse Record)
        return concepto

    
    
    @api.multi
    def update_properties_concept(self, concepto):
        return concepto
