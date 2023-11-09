# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import QueryURL
from odoo import fields, http, SUPERUSER_ID, tools, _
from odoo.osv import expression
from datetime import datetime
from odoo.addons.http_routing.models.ir_http import slug

class TableCompute(object):

    def __init__(self):
        self.table = {}

    def _check_place(self, posx, posy, sizex, sizey, ppr):
        res = True
        for y in range(sizey):
            for x in range(sizex):
                if posx + x >= ppr:
                    res = False
                    break
                row = self.table.setdefault(posy + y, {})
                if row.setdefault(posx + x) is not None:
                    res = False
                    break
            for x in range(ppr):
                self.table[posy + y].setdefault(x, None)
        return res

    def process(self, products, ppg=20, ppr=4):
        # Compute products positions on the grid
        minpos = 0
        index = 0
        maxy = 0
        x = 0
        for p in products:
            x = min(max(p.website_size_x, 1), ppr)
            y = min(max(p.website_size_y, 1), ppr)
            if index >= ppg:
                x = y = 1

            pos = minpos
            while not self._check_place(pos % ppr, pos // ppr, x, y, ppr):
                pos += 1
            # if 21st products (index 20) and the last line is full (ppr products in it), break
            # (pos + 1.0) / ppr is the line where the product would be inserted
            # maxy is the number of existing lines
            # + 1.0 is because pos begins at 0, thus pos 20 is actually the 21st block
            # and to force python to not round the division operation
            if index >= ppg and ((pos + 1.0) // ppr) > maxy:
                break

            if x == 1 and y == 1:  # simple heuristic for CPU optimization
                minpos = pos // ppr

            for y2 in range(y):
                for x2 in range(x):
                    self.table[(pos // ppr) + y2][(pos % ppr) + x2] = False
            self.table[pos // ppr][pos % ppr] = {
                'product': p, 'x': x, 'y': y,
                'ribbon': p._get_website_ribbon(),
            }
            if index <= ppg:
                maxy = max(maxy, y + (pos // ppr))
            index += 1

        # Format table according to HTML needs
        rows = sorted(self.table.items())
        rows = [r[1] for r in rows]
        for col in range(len(rows)):
            cols = sorted(rows[col].items())
            x += len(cols)
            rows[col] = [r[1] for r in cols if r[1]]

        return rows


class EWebsite(http.Controller):
    @http.route('/', auth='public', type='http', website=True)
    def index(self, **kw):
        product_ids = request.env['product.template'].search([('image_1920', '!=', False)])
        department_ids = request.env['product.public.category'].search([('parent_id', '=', False)])
        values = {'hot_products': product_ids[:4],
                  'look_product': product_ids[4:5],
                  'look_products': product_ids[5:9],
                  'all_departments': department_ids}
        return http.request.render('e_website.home', values)

    def _product_get_query_url_kwargs(self, category, search, attrib=None, **kwargs):
        return {
            'category': category,
            'search': search,
            'attrib': attrib,
            'min_price': kwargs.get('min_price'),
            'max_price': kwargs.get('max_price'),
        }

    def _get_search_domain(self, search, category, attrib_values, search_in_description=True):
        domains = [request.website.sale_product_domain()]
        if search:
            for srch in search.split(" "):
                subdomains = [
                    [('name', 'ilike', srch)],
                    [('product_variant_ids.default_code', 'ilike', srch)]
                ]
                if search_in_description:
                    subdomains.append([('website_description', 'ilike', srch)])
                    subdomains.append([('description_sale', 'ilike', srch)])
                domains.append(expression.OR(subdomains))

        if category:
            domains.append([('public_categ_ids', 'child_of', int(category))])

        if attrib_values:
            attrib = None
            ids = []
            for value in attrib_values:
                if not attrib:
                    attrib = value[0]
                    ids.append(value[1])
                elif value[0] == attrib:
                    ids.append(value[1])
                else:
                    domains.append([('attribute_line_ids.value_ids', 'in', ids)])
                    attrib = value[0]
                    ids = [value[1]]
            if attrib:
                domains.append([('attribute_line_ids.value_ids', 'in', ids)])

        return expression.AND(domains)

    def _prepare_product_values(self, product, category, search, **kwargs):
        ProductCategory = request.env['product.public.category']

        if category:
            category = ProductCategory.browse(int(category)).exists()

        attrib_list = request.httprequest.args.getlist('attrib')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attrib_set = {v[1] for v in attrib_values}

        keep = QueryURL(
            '/shop',
            **self._product_get_query_url_kwargs(
                category=category and category.id,
                search=search,
                **kwargs,
            ),
        )

        # Needed to trigger the recently viewed product rpc
        view_track = request.website.viewref("website_sale.product").track
        return {
            'search': search,
            'category': category,
            'pricelist': request.website.get_current_pricelist(),
            'attrib_values': attrib_values,
            'attrib_set': attrib_set,
            'keep': keep,
            'categories': ProductCategory.search([('parent_id', '=', False)]),
            'main_object': product,
            'product': product,
            'add_qty': 1,
            'view_track': view_track,
        }

    @http.route('/department', auth='public', type='http', website=True)
    def department(self, **kw):
        return http.request.render('e_website.department')

    @http.route(['/category',
                 '/category/<int:category_id>'],
                type='http', auth="public", website=True)
    def category(self, category_id, search='', min_price=0.0, max_price=0.0, **post):
        try:
            min_price = float(min_price)
        except ValueError:
            min_price = 0
        try:
            max_price = float(max_price)
        except ValueError:
            max_price = 0
        attrib_list = request.httprequest.args.getlist('attrib')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attributes_ids = {v[0] for v in attrib_values}
        attrib_set = {v[1] for v in attrib_values}
        department_ids = request.env['product.public.category']
        category = department_ids.search([('id', '=', category_id)])
        department_ids = request.env['product.public.category'].search([('parent_id', '=', False)])
        website = request.env['website'].get_current_website()
        if department_ids.search([('id', '=', category_id)]).is_department:
            department = request.env['product.public.category'].sudo().browse(category_id)
            categ_ids = request.env['product.public.category'].search([('parent_id', '=', department.id)])
            return http.request.render('e_website.department',
                                       {'department': department,
                                        'categ_ids': categ_ids,
                                        'parents': category.parents_and_self,
                                        'all_departments': department_ids})
        else:
            now = datetime.timestamp(datetime.now())
            pricelist = request.env['product.pricelist'].browse(request.session.get('website_sale_current_pl'))
            if not pricelist or request.session.get('website_sale_pricelist_time',
                                                    0) < now - 60 * 60:  # test: 1 hour in session
                pricelist = website.get_current_pricelist()
                request.session['website_sale_pricelist_time'] = now
                request.session['website_sale_current_pl'] = pricelist.id
            request.update_context(pricelist=pricelist.id, partner=request.env.user.partner_id)
            filter_by_price_enabled = website.is_view_active('website_sale.filter_products_price')
            if filter_by_price_enabled:
                company_currency = website.company_id.currency_id
                conversion_rate = request.env['res.currency']._get_conversion_rate(
                    company_currency, pricelist.currency_id, request.website.company_id, fields.Date.today())
                Product = request.env['product.template'].with_context(bin_size=True)
                domain = self._get_search_domain(search, category, attrib_values)

                # This is ~4 times more efficient than a search for the cheapest and most expensive products
                from_clause, where_clause, where_params = Product._where_calc(domain).get_sql()
                query = f"""
                                SELECT COALESCE(MIN(list_price), 0) * {conversion_rate}, COALESCE(MAX(list_price), 0) * {conversion_rate}
                                  FROM {from_clause}
                                 WHERE {where_clause}
                            """
                request.env.cr.execute(query, where_params)
                available_min_price, available_max_price = request.env.cr.fetchone()

                if min_price or max_price:
                    # The if/else condition in the min_price / max_price value assignment
                    # tackles the case where we switch to a list of products with different
                    # available min / max prices than the ones set in the previous page.
                    # In order to have logical results and not yield empty product lists, the
                    # price filter is set to their respective available prices when the specified
                    # min exceeds the max, and / or the specified max is lower than the available min.
                    if min_price:
                        min_price = min_price if min_price <= available_max_price else available_min_price
                        post['min_price'] = min_price
                    if max_price:
                        max_price = max_price if max_price >= available_min_price else available_max_price
                        post['max_price'] = max_price
            else:
                conversion_rate = 1
            if not max_price:
                max_pr = available_max_price
            else:
                max_pr = max_price
            product_ids = request.env['product.template'].search([('public_categ_ids', '=', category_id),
                                                                  ('list_price', '>=', min_price),
                                                                  ('list_price', '<=', max_pr)])
            return http.request.render('e_website.category', {'products': product_ids,
                                                              'category': category,
                                                              'pricelist': pricelist,
                                                              'min_price': min_price or available_min_price,
                                                              'max_price': max_price or available_max_price,
                                                              'available_min_price': tools.float_round(
                                                                  available_min_price, 2),
                                                              'available_max_price': tools.float_round(
                                                                  available_max_price, 2),
                                                              'sub_categories': department_ids.search(
                                                                  [('parent_id', '=', category_id)]),
                                                              'all_departments': department_ids,
                                                              'parents': category.parents_and_self})

    @http.route(['/shop/<model("product.template"):product>'], type='http', auth="public", website=True, sitemap=True)
    def product(self, product, category='', search='', **kwargs):
        return request.render("website_sale.product", self._prepare_product_values(product, category, search, **kwargs))

    @http.route('/department/<int:department_id>', type='http', website=True)
    def department_details(self, department_id, **kwargs):
        department = request.env['product.public.category'].sudo().browse(department_id)
        department_ids = request.env['product.public.category'].search([('parent_id', '=', False)])
        categ_ids = request.env['product.public.category'].search([('parent_id', '=', department.id)])
        product_ids = request.env['product.template'].search([('public_categ_ids', '=', department.id)], limit=1)
        return http.request.render('e_website.department',
                                   {'products': product_ids,
                                    'department': department,
                                    'categ_ids': categ_ids,
                                    'all_departments': department_ids})
#     @http.route('/e_website/e_website/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('e_website.listing', {
#             'root': '/e_website/e_website',
#             'objects': http.request.env['e_website.e_website'].search([]),
#         })

#     @http.route('/e_website/e_website/objects/<model("e_website.e_website"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('e_website.object', {
#             'object': obj
#         })
