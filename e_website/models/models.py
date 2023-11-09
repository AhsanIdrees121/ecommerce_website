# -*- coding: utf-8 -*-

from odoo import models, fields, api


class e_website(models.Model):
    _inherit = 'product.public.category'

    is_department = fields.Boolean('Is Department', default=False)
