# -*- encoding: utf-8 -*-
{
    "name"      : "México e-Invoice (Base)",
    "version"   : "1.0",
    "Summary"   : "Base for Mexican e-Invoice",
    "sequence"  : 50,
    "author"    : "Argil Consulting",
    "category"  : "Localization",
    "description" : """
México e-Invoice (Base)
=======================

    This module extends Odoo for Mexican e-Invoice to work
    
Requires the following programs:

  xsltproc
    Ubuntu insall with:
        sudo apt-get install xsltproc

  openssl
      Ubuntu insall with:
        sudo apt-get install openssl

  libxml2-utils
      Ubuntu insall with:
        sudo apt-get install libxml2-utils

    """,
    "website" : "http://www.argil.mx",
    'license' : 'OEEL-1',
    "depends" : ["account",
                 #"account_move_line_base_tax",
                 "base_vat",
                 "purchase",
                 "sale_stock",
                 "document",
                 "email_template_multicompany",
                 'l10n_mx_sat_models',
                ],
    "data" : ['menu_view.xml',
              'security/l10n_mx_facturae_security_groups.xml',
              #'security/l10n_mx_facturae_cer_security.xml',
              'security/l10n_mx_facturae_security_groups.xml',
              'security/l10n_mx_facturae_security_groups_date.xml',
              #'security/params_pac_security.xml',
              # 'country_data.xml',
              'regimen_fiscal_view.xml',
              'regimen_fiscal_data.xml',
              'payment_method_view.xml',
              'payment_method_data.xml',
              'res_company_view.xml',
              'res_config_view_10.xml',
              'res_partner_view.xml',
              'res_partner_bank_view.xml',
              #'ir_sequence_view.xml',
              'account_invoice_view.xml',
              #'params_pac_view.xml',
              'sale_view.xml',
              'purchase_view.xml',
              'account_journal_view.xml',
              #'account_invoice_workflow.xml',
              #'report_multicompany_view.xml',
              #'security/report_multicompany_security.xml',
    ],
    'installable'   : True,
    'application'   : False,
    'auto_install'  : False,
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: