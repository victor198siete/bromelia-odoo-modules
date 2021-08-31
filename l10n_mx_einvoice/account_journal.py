# -*- encoding: utf-8 -*-
from openerp import api, fields, models, _, release
import os
import time
import tempfile
import base64

class account_journal(models.Model):
    _inherit = 'account.journal'

    address_invoice_company_id = fields.Many2one('res.partner', string='Dirección de Emisión', 
                                                 domain="[('type', 'in', ('invoice','default','contact'))]",
        help="Si este campo es capturado, la factura electrónica tomará los datos de la dirección del partner seleccionado para generar el CFDI")
    company2_id = fields.Many2one('res.company', string='Compañía Emisora',
        help="Si este campo es capturado, la factura electrónica tomará los datos de la Compañía seleccionada como Compañía emisora del CFDI")

    use_for_cfdi = fields.Boolean(string="Usar para CFDIs", help="Si activa la casilla entonces se generará Factura Electrónica (CFDI)")
    serie_cfdi_invoice = fields.Char(string="Serie Factura", size=12, help="Indique la Serie a utilizar para el CFDI (Opcional)")
    serie_cfdi_refund  = fields.Char(string="Serie Nota de Crédito", size=12, help="Indique la Serie a utilizar para el CFDI (Opcional)")
    
    if release.major_version in ("9.0", "10.0"):
        report_id   = fields.Many2one('ir.actions.report.xml', 'Reporte', 
                                 help="""Esta plantilla de reporte se usará para la generación de la representación del PDF del CFDI""")
    elif release.major_version in ("11.0"):
        report_id   = fields.Many2one('ir.actions.report', 'Reporte', 
                                 help="""Esta plantilla de reporte se usará para la generación de la representación del PDF del CFDI""")
    report_name = fields.Char(string='Nombre Técnico', related='report_id.report_name',  readonly=True)
    
    certificate_file = fields.Binary(string='Certificado (*.cer)',
                    filters='*.cer,*.certificate,*.cert', 
                    help='Seleccione el archivo del Certificado de Sello Digital (CSD). Archivo con extensión .cer')
    certificate_key_file = fields.Binary(string='Llave del Certificado (*.key)',
                    filters='*.key', 
                    help='Seleccione el archivo de la Llave del Certificado de Sello Digital (CSD). Archivo con extensión .key')
    certificate_password = fields.Char(string='Contraseña Certificado', size=64,
                    invisible=False, 
                    help='Especifique la contraseña de su CSD')
    certificate_file_pem = fields.Binary(string='Certificado (PEM)',
                    filters='*.pem,*.cer,*.certificate,*.cert', 
                    help='Este archivo es generado a partir del CSD (.cer)')
    certificate_key_file_pem = fields.Binary(string='Llave del Certificado (PEM)',
                    filters='*.pem,*.key', help='Este archivo es generado a partir del CSD (.key)')
    certificate_pfx_file = fields.Binary(string='Certificado (PFX)',
                    filters='*.pfx', help='Este archivo es generado a partir del CSD (.cer)')
    date_start  = fields.Date(string='Vigencia de', help='Fecha de inicio de vigencia del CSD')
    date_end    = fields.Date(string='Vigencia hasta',  help='Fecha de fin de vigencia del CSD')
    serial_number = fields.Char(string='Número de Serie', size=64, 
                                help='Number of serie of the certificate')
    fname_xslt  = fields.Char('Path Parser (.xslt)', size=256, 
                             help='Directorio donde encontrar los archivos XSLT. Dejar vacío para que se usen las opciones por defecto')
    
    
    
    @api.onchange('certificate_password')
    def _onchange_certificate_password(self):
        """
        @param cer_der_b64str : File .cer in Base 64
        @param key_der_b64str : File .key in Base 64
        @param password : Password inserted in the certificate configuration
        """
        certificate_lib = self.env['facturae.certificate.library']
        value = {}
        warning = {}
        certificate_file_pem = False
        certificate_key_file_pem = False
        cer_der_b64str = self.certificate_file
        key_der_b64str = self.certificate_key_file
        password=self.certificate_password
        if cer_der_b64str and key_der_b64str and password:
            fname_cer_der = certificate_lib.b64str_to_tempfile(
                cer_der_b64str, file_suffix='.der.cer',
                file_prefix='openerp__' + (False or '') + '__ssl__')
            fname_key_der = certificate_lib.b64str_to_tempfile(
                key_der_b64str, file_suffix='.der.key',
                file_prefix='openerp__' + (False or '') + '__ssl__')
            fname_password = certificate_lib.b64str_to_tempfile(
                base64.encodestring(password), file_suffix='der.txt', 
                file_prefix='openerp__' + (False or '') + '__ssl__')
            fname_tmp = certificate_lib.b64str_to_tempfile(
                '', file_suffix='tmp.txt', file_prefix='openerp__' + (
                False or '') + '__ssl__')

            
            cer_pem = certificate_lib._transform_der_to_pem(fname_cer_der, fname_tmp, type_der='cer')
            cer_pem_b64 = base64.encodestring(cer_pem)
            key_pem = certificate_lib._transform_der_to_pem(fname_key_der, fname_tmp, fname_password, type_der='key')
            key_pem_b64 = base64.encodestring(key_pem)

            fname_cer_pem = certificate_lib.b64str_to_tempfile(
                cer_pem_b64, file_suffix='.cer.pem',
                file_prefix='openerp__' + (False or '') + '__ssl__')
            fname_key_pem = certificate_lib.b64str_to_tempfile(
                key_pem_b64, file_suffix='.key.pem',
                file_prefix='openerp__' + (False or '') + '__ssl__')
            
            fname_pfx = certificate_lib.b64str_to_tempfile(
                '', file_suffix='.pfx',
                file_prefix='openerp__' + (False or '') + '__ssl__')
            
            pfx_file = certificate_lib._transform_pem_to_pfx(fname_cer_pem, fname_key_pem, fname_pfx, password)
            pfx_file_b64 = base64.encodestring(pfx_file)
            # -.-.-.-.-.-.-.-.-.
            
            # date_fmt_return='%Y-%m-%d %H:%M:%S'
            date_fmt_return = '%Y-%m-%d'
            serial = False
            try:
                serial = certificate_lib._get_param_serial(fname_cer_der, fname_tmp, type='DER')
                self.serial_number =  serial
            except:
                pass
            date_start = False
            date_end = False
            # Pendiente revisar porque no trae correcta las fechas
            try:
                dates = certificate_lib._get_param_dates(fname_cer_der, fname_tmp, date_fmt_return=date_fmt_return, type='DER')
                date_start = dates.get('startdate', False)
                date_end = dates.get('enddate', False)
                if ' ' in date_start:
                    date_start = date_start.replace(' ','0')
                if ' ' in date_end:
                    date_end = date_end.replace(' ','0')
            except:
                pass
            try:
                self.date_start = date_start
                self.date_end   = date_end
            except:
                pass
            os.unlink(fname_cer_der)
            os.unlink(fname_key_der)
            os.unlink(fname_password)
            os.unlink(fname_tmp)
            if not key_pem_b64 or not cer_pem_b64 or not pfx_file_b64:
                warning = {
                    'title': _('Advertencia!'),
                    'message': _('Su archivo del Certificado, la Llave o la Contraseña son incorrectas.\nPor favor revise')
                }
                self.certificate_file_pem = False,
                self.certificate_key_file_pem = False,
                self.certificate_pfx_file = False,
            else:
                self.certificate_file_pem       = cer_pem_b64
                self.certificate_key_file_pem   = key_pem_b64
                self.certificate_pfx_file       = pfx_file_b64
                
        return {'value': value, 'warning': warning}