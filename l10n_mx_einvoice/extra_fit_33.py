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
#import amount_to_text_es_MX
import logging
_logger = logging.getLogger(__name__)


class facturae_certificate_library(models.Model):
    _name = 'facturae.certificate.library'
    _auto = False
    
