import xmlrpc.client
import shipstation_lib as shl
import core
import json
import requests
import math
import psycopg2
from datetime import datetime, timedelta


class ShipstationBase:

    def __init__(self):
        self.model = xmlrpc.client.ServerProxy('http://localhost:8069/xmlrpc/object')
        self.api_key = 'x'
        self.api_secret = 'x'
        self.amazon_access_key = "x"
        self.amazon_merchant_id = "x"
        self.amazon_secret_key = "x"
        self.pricelist_id = 0
        self.region = ""
        self.marketplaceid_us = "x"
        self.marketplaceid_canada = "x"
        self.info = {'user': 'x', 'password': 'x',
                     'host': 'localhost', 'database': 'base'}
        self.uid = 2
        self.location_id = 'x'
        self.conn = psycopg2.connect(host='localhost',
                                     user='x',
                                     password='x',
                                     dbname='x')
        self.certid = 'x'
        self.appid = 'x'
        self.devid = 'x'
        self.token = 'x'

    def login_odoo_api(self):
        common = xmlrpc.client.ServerProxy("http://x:8069/xmlrpc/2/common")
        common.version()
        uid = common.authenticate(self.info["database"],
                                  self.info["user"],
                                  self.info["password"],
                                  {})
        self.uid = uid
        return uid

    @staticmethod
    def validate_ebay_sku(sku):
        implemented_versions = ('PS', 'PS2', 'PS4', 'PS3', 'PS5',
                                'PSF', 'PC', 'PC3', 'PC4', 'PC5',
                                'PC6', 'PC2', 'PSD', 'PSW', 'PCF')
        brand_with_dash = False
        if 'W-R-' in sku:
            brand_with_dash = True
        sku = sku.split('-')
        product_id = ''
        version = ''
        case_quantity = ''
        if sku[0] in implemented_versions:
            version = sku[0]
            sku.remove(sku[0])
        if sku[-1].isdigit():
            product_id = sku[-1]
            sku = sku[:-1]
        supplier_code = sku[-1]
        sku.remove(sku[-1])
        if sku[-1].lower().startswith('q') and len(sku[-1]) <= 4:
            case_quantity = sku[-1].lower().replace('q', '')
            sku.remove(sku[-1])
        if brand_with_dash is False:
            short_brand = sku[0]
            sku.remove(sku[0])
        else:
            short_brand = sku[0] + '-' + sku[1]
            sku.remove(sku[0])
            sku.remove(sku[0])
        partnumber = '-'.join(sku)
        if case_quantity == '':
            case_quantity = 1
        data = {
            'version': version,
            'short_brand': short_brand,
            'part_number': partnumber,
            'qty': case_quantity,
            'short_name': supplier_code,
            'product_id': product_id
        }
        return data

    # select data from odoo db by select info, table name, method ("=", "ilike", "=ilike")
    # and column name
    def get_info_db(self,
                    select_data,
                    table,
                    method="=",
                    column="name",
                    kwargs=None,
                    search_method="search",
                    fields=None):
        if fields is None:
            fields = []
        data = []
        if search_method == "search":
            search_state = [(column, method, select_data)]
            if kwargs is not None:
                search_state.append((kwargs[2], kwargs[1], kwargs[0]))
            data = self.model.execute(self.info['database'],
                                 self.uid,
                                 self.info['password'],
                                 table,
                                 search_method,
                                 search_state)
        elif search_method == "search_read":
            search_state = [[[column, method, select_data]]]
            if kwargs is not None:
                search_state.append((kwargs[2], kwargs[1], kwargs[0]))
            data = self.model.execute_kw(self.info['database'],
                                    self.uid,
                                    self.info['password'],
                                    table,
                                    search_method,
                                    search_state,
                                    {"fields": fields})
        if len(data) == 1:
            data = data[0]
        return data

    def is_chemical(self, product):
        chemical = self.get_info_db(product, 'product.template', '=', 'id', None,
                                    'search_read', ["x_chemical"])["x_chemical"]
        return chemical

    @staticmethod
    def get_marketplace_name(shipstation_store_id):
        marketplace_name = ''
        if shipstation_store_id == 208909:
            marketplace_name = 'Amazon'
        elif shipstation_store_id == 208908:
            marketplace_name = 'Amazon'
        elif shipstation_store_id == 208910:
            marketplace_name = 'Ebay'
        elif shipstation_store_id == 208913:
            marketplace_name = 'Shopify'
        elif shipstation_store_id == 208917:
            marketplace_name = 'Walmart'
        else:
            marketplace_name = 'Error'
        return marketplace_name

    def get_half_delivery_price(self, order_id, delivery_method):
        cur = self.conn.cursor()
        query = """SELECT sol.product_uom_qty,
                       pt.x_length,
                       pt.x_height,
                       pt.x_width,
                       pt.weight,
                       rp.city,
                       rp.zip,
                       rp.country_id,
                       rcs.code
                       FROM sale_order_line AS sol
                    INNER JOIN product_product pp on sol.product_id = pp.id
                    INNER JOIN product_template pt on pp.product_tmpl_id = pt.id
                    INNER JOIN res_partner rp ON sol.order_partner_id = rp.id
                    INNER JOIN res_country_state rcs on rp.state_id = rcs.id
                WHERE sol.order_id = """+str(order_id)+""" AND sol.is_delivery is False"""
        cur.execute(query)
        delivery_line = cur.fetchall()
        for i in delivery_line:
            if i[4] <= 0:
                return False
        if len(delivery_line) == 1:
            if delivery_line[0][0] == 1:
                return False
        length = max([line[1] if line[1] is not None else 0 for line in delivery_line])
        width = max([line[3] if line[2] is not None else 0 for line in delivery_line])
        height = sum([(line[2] if line[2] is not None else 0 * math.ceil(line[0] / 2)) \
                      for line in delivery_line])
        total_weight = sum([(line[4] * math.ceil(line[0] / 2)) for line in delivery_line])
        url = "https://ssapi.shipstation.com/shipments/getrates"
        return_data = []
        for dm in delivery_method:
            query_carrier_code = """SELECT sdc.code, sdcs.service_code
                    FROM shipstation_delivery_carrier as sdc
                        INNER JOIN shipstation_delivery_carrier_service as sdcs ON sdc.id = sdcs.delivery_carrier_id
                        INNER JOIN delivery_carrier as dc ON sdcs.id = dc.shipstation_delivery_carrier_service_id
                    WHERE dc.name = '"""+dm+"""' """
            cur.execute(query_carrier_code)
            exe_data = cur.fetchall()
            carrier_code = exe_data[0][0]
            service_code = exe_data[0][1]
            default_data = {
                'carrierCode': carrier_code,
                'serviceCode': service_code,
                'packageCode': 'package',
                'fromPostalCode': '60061',
                'toState': delivery_line[0][8],
                'toCountry': 'US' if delivery_line[0][7] == 233 else 'CA',
                'toPostalCode': delivery_line[0][6],
                'toCity': delivery_line[0][5],
                "weight": {"value": float(total_weight),  "units": "pounds"},
                "dimensions": {"units": "inches",
                               "length": float(length),
                               "width": float(width),
                               "height": float(height)}
            }
            headers = {
                'Content-Type': 'application/json'
            }
            json_data = json.dumps(default_data, indent=4)
            response = requests.post(url, headers=headers, data=json_data,
                                     auth=('x',
                                           'x'))
            return_data.append(response.json())
        return return_data

    def get_rate(self, order_id, delivery_method):
        self.model.execute_kw(self.info["database"], self.uid, self.info["password"],
                         'sale.order', 'get_delivery_prices', (order_id, delivery_method))
        data = self.model.execute_kw(self.info['database'], self.uid,
                                     self.info['password'], 'delivery.prices',
                                'search_read', [[['sale_id', '=', order_id],
                                                 ['delivery_name', 'in', delivery_method],
                                                 ["delivery_price", '>', 0]]],
                                {"limit": 1, "order": 'delivery_price asc',
                                 "fields": ["delivery_name", "delivery_price"]})
        if not data:
            return False
        # delivery_name = data[0]['delivery_name']
        self.model.execute_kw(self.info["database"], self.uid, self.info["password"],
                         'sale.order', 'set_delivery_line',
                         ((order_id,), data[0]['delivery_name'], data[0]['delivery_price']))
        paid_shipping = self.model.execute_kw(self.info['database'], self.uid,
                                              self.info['password'], 'sale.order',
                                     'search_read',
                                     [[['id', '=', order_id]]],
                                     {"limit": 1,
                                      "fields": ["x_customer_delivery_paid"]})[0]['x_customer_delivery_paid']
        if data[0]['delivery_price'] - paid_shipping < 100:
            half_delivery_price = self.get_half_delivery_price(order_id, delivery_method)
            if half_delivery_price is False:
                try:
                    self.model.execute_kw(self.info["database"], self.uid, self.info["password"],
                                          'sale.order', 'action_confirm', (order_id,))
                except:
                    print('Error nor added')
            else:
                cheaper_delivery = False
                for hdp in half_delivery_price:
                    if hdp[0]['shipmentCost'] * 2 < data[0]['delivery_price']:
                        self.model.execute_kw(self.info["database"], self.uid, self.info["password"], 'sale.order',
                                              'write',
                                              [[order_id], {
                                                  'note': 'It is cheaper to send in two parcels using delivery '
                                                          ''+hdp[0]['serviceName']+', the price will be '+str(hdp[0]['shipmentCost'] * 2)+''
                                              }])
                        cheaper_delivery = True
                if cheaper_delivery is False:
                    try:
                        self.model.execute_kw(self.info["database"], self.uid, self.info["password"],
                                              'sale.order', 'action_confirm', (order_id,))
                    except:
                        print('Error nor added')
        else:
            self.model.execute_kw(self.info["database"], self.uid, self.info["password"], 'sale.order', 'write',
                                  [[order_id], {
                                      'x_reason': 'big_shipping'
                                  }])
        return True

    def stock_unit_price(self, product_id, product_template_id):
        cur = self.conn.cursor()
        qty = 0
        stock_qty = self.get_product_stock_qty(product_id)
        if len(stock_qty) != 0:
            qty_available = 0
            qty_reserved = 0
            for qty_data in stock_qty:
                qty_available += qty_data["quantity"]
                qty_reserved += qty_data["reserved_quantity"]
            qty = qty_available - qty_reserved
        if qty <= 0:
            cur.execute("SELECT price_unit "
                        "FROM purchase_order_line "
                        "WHERE product_id = "+str(product_id)+" and state != 'done' and product_uom_qty > qty_received "
                                                              "ORDER BY write_date DESC LIMIT 1")

            stock_unit_cost = cur.fetchall()
            if len(stock_unit_cost) > 0:
                self.conn.close()
                return stock_unit_cost[0][0]
            else:
                standard_price = self.get_info_db(product_template_id, 'product_tempalte', '=', 'id', None,
                                            'search_read', ["standart_price"])[0]['standard_price']
                self.conn.close()
                return standard_price

        else:
            cur.execute("SELECT product_uom_qty, price_unit, date, origin FROM stock_move "
                        "WHERE product_id = "+product_id+" AND state = 'done' "
                        "AND reference LIKE '%IN/%' AND origin LIKE 'P%' AND price_unit != 0 ORDER by date DESC")
            stock_move = cur.fetchall()
            # print(stock_move)
            current_stock = []
            qty_in_stock = 0
            for move in stock_move:
                if qty_in_stock + move[0] < qty:
                    qty_in_stock = qty_in_stock + move[0]
                    # current_stock.append(move)
                    current_stock.append((int(move[0]), move[1]))
                else:
                    qty_last = int(qty) - int(qty_in_stock)
                    current_stock.append((qty_last, move[1]))
                    break
            print(current_stock)
            current_unit_cost = round(sum(i[0] * i[1] for i in current_stock) / qty, 2)
            self.conn.close()
            return current_unit_cost

    def add_customer_to_odoo(self, data):
        data_customer = dict()
        data_customer['name'] = data['shipTo']['name']

        if data['shipTo']['phone'] is not None:
            data_customer['phone'] = data['shipTo']['phone'].split(' ext.')[0] \
                .replace('+1', ''). \
                replace('-', ''). \
                replace(' ', '')
        # if 'Name' in data['ShippingAddress'].keys():
        #     if data['ShippingAddress']['Name'] != '':
        #         data_customer['name'] = data['ShippingAddress']['Name']['value']
        #     else:
        #         data_customer['name'] = data['BuyerName']['value']
        # else:
        #     data_customer['name'] = data['BuyerName']['value']

        # added by Yan
        if data['customerEmail'] is not None:
            data_customer['email'] = data['customerEmail']
        data_customer['city'] = data['shipTo']['city']
        # print(data['shipTo']['country'])
        if data['shipTo']['country'] == "US":
            data_customer['country_id'] = 233
        elif data['shipTo']['country'] == "CA":
            data_customer['country_id'] = 38
        data_customer['zip'] = data['shipTo']['postalCode'].split('-')[0]
        if data['shipTo']['street1'] != "None" and data['shipTo']['street1'] != "":
            data_customer['street'] = data['shipTo']['street1']
        if data['shipTo']['street2'] != "None" and data['shipTo']['street2'] != "" \
                and data['shipTo']['street2'] != None:
            data_customer['street2'] = data['shipTo']['street2']
        state_id = 0
        # print(data['shipTo']['street2'])
        data['shipTo']['state'] = data['shipTo']['state'].replace('.', '')
        if len(data['shipTo']['state']) == 2:
            state_id = self.get_info_db(data['shipTo']['state'].upper() + '%',
                                        'res.country.state', '=ilike', 'code',
                                        [data_customer['country_id'], '=?', 'country_id'])
        elif len(data['shipTo']['state']) > 2:
            data['shipTo']['state'] = data['shipTo']['state'].replace('.', '')
            state_id = self.get_info_db(data['shipTo']['state'],
                                        'res.country.state', 'ilike', 'name',
                                        [data_customer['country_id'], '=?', 'country_id'])
        if isinstance(state_id, list):
            # print(data['shipTo']['state'].upper())
            data_customer['state_id'] = state_id[0]
        elif isinstance(state_id, int):
            data_customer['state_id'] = state_id
        data_customer['lang'] = "en_US"
        data_customer["active"] = "true"
        data_customer["is_company"] = "false"
        data_customer["customer_rank"] = 1
        # if data['shipTo']['state'] != "" and data['shipTo']['state'] != "None":
        #     data_customer["is_company"] = "true"
        data_customer["type"] = "contact"
        # print(data_customer)
        partner_id = self.create_data_db(data_customer, "res.partner")
        return partner_id

    # insert data to odoo db
    def create_data_db(self, data, table):
        create_id = self.model.execute(self.info["database"],
                                  self.uid,
                                  self.info["password"],
                                  table,
                                  "create",
                                  data)
        return create_id

    def get_product_stock_qty(self, product_id):
        stock_qty = self.model.execute_kw(self.info['database'], self.uid, self.info['password'],
                                          'stock.quant', 'search_read',
                                          [[['product_id', '=', product_id],
                                            ['company_id', '=', 1],
                                            ['location_id', '!=', 1],
                                            ['location_id', '!=', 2],
                                            ['location_id', '!=', 3],
                                            ['location_id', '!=', 4],
                                            ['location_id', '!=', 5],
                                            ['location_id', '!=', 6],
                                            ['location_id', '!=', 9],
                                            ['location_id', '!=', 10],
                                            ['location_id', '!=', 11],
                                            ['location_id', '!=', 12],
                                            ['location_id', '!=', 13],
                                            ['location_id', '!=', 14],
                                            ['location_id', '!=', 15],
                                            ['location_id', '!=', 16],
                                            ['location_id', '!=', 17],
                                            ['location_id', '!=', 18],
                                            ['location_id', '!=', 19],
                                            ['location_id', '!=', 828],
                                            ['location_id', '!=', 4312]
                                            ]],
                                          {"fields": ["reserved_quantity", "quantity"], "order": "id DESC"})
        return stock_qty


class ShipstationAmazon(ShipstationBase):

    def get_shipstation_orders(self, page):
        svc = shl.ShipStationApi(
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        order_filter = {'orderStatus': 'awaiting_shipment', 'storeId': 208908}
        orders = svc.orders.page(order_filter, page_num=page, page_size=500)
        # print(len(orders))
        # Uncomment this code to get one order on ordernumber
        # orders = svc.orders.page({'orderNumber': '112-8454004-9867435'})
        filter_order = []
        for order in orders:
            order_added = False
            for item in order['items']:
                sku = core.SKU(item['sku'])
                if sku.supplier() == 'warehouse':
                    order_added = True
                if sku.version() == 'PS5' and order['tagIds'] == None:
                    order_added = True
            if order_added is True:
                filter_order.append(order)
        return filter_order

    def get_express_state_id_list(self):
        express_state_name_list = ['Pennsylvania', 'Tennessee', 'South Dakota', 'Indiana',
                                   'Illinois', 'Kansas', 'Iowa', 'Kentucky', 'Michigan',
                                   'Minnesota', 'Missouri', 'Nebraska', 'Wisconsin',
                                   'West Virginia', 'Ohio']

        data = self.model.execute_kw(self.info['database'],
                                self.uid,
                                self.info['password'],
                                'res.country.state',
                                'search',
                                [
                                    [
                                        ['name', 'in', express_state_name_list],
                                        ['country_id', '=', 233]
                                    ]
                                ])
        return data

    def get_secondday_state_id_list(self):
        secondday_state_name_list = ['Pennsylvania', 'Tennessee', 'South Dakota', 'Indiana',
                                     'Illinois', 'Kansas', 'Iowa', 'Kentucky', 'Michigan',
                                     'Minnesota', 'Missouri', 'Nebraska', 'Wisconsin',
                                     'West Virginia', 'Ohio']

        data = self.model.execute_kw(self.info['database'],
                                self.uid,
                                self.info['password'],
                                'res.country.state',
                                'search',
                                [
                                    [
                                        ['name', 'in', secondday_state_name_list],
                                        ['country_id', '=', 233]
                                    ]
                                ])
        return data

    def get_expedited_state_id_list(self):
        expedited_state_name_list = ['South Dakota', 'Indiana', 'Illinois', 'Kansas', 'Iowa',
                                     'Michigan', 'Minnesota', 'Missouri', 'Nebraska',
                                     'Wisconsin', 'North Dakota', 'Ohio']
        data = self.model.execute_kw(self.info['database'],
                                self.uid,
                                self.info['password'],
                                'res.country.state',
                                'search',
                                [
                                    [
                                        ['name', 'in', expedited_state_name_list],
                                        ['country_id', '=', 233]
                                    ]
                                ])
        return data

    @staticmethod
    def get_shipping_method_amazon(shipping_code):
        shipping_method = ""
        if "Econ" in shipping_code or "Std" in shipping_code:
            shipping_method = "Standard"
        elif "Exp" in shipping_code:
            shipping_method = "Expedited"
        elif "Second" in shipping_code:
            shipping_method = "SecondDay"
        else:
            shipping_method = "Standard"
        return shipping_method

    def add_shipping_method_amazon(self, odoo_order_id, shipping_service_name, order_shipping_price, order_weight,
                                   order_with_nuc, partner_state_id, order_post_office):
        if shipping_service_name == "SecondDay":
            secondday_state_id_list = self.get_secondday_state_id_list()
        elif shipping_service_name == "Expedited":
            expedited_state_id_list = self.get_expedited_state_id_list()
        if shipping_service_name == "Standard" and order_post_office is False:
            if order_shipping_price >= 200 \
                    and order_weight * 16 >= 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, [
                    # "Amazon Fedex Ground Signature Required",
                                              "Amazon UPS Ground Signature Required",
                                              "Amazon USPS Priority Mail Signature Required"])
            elif order_shipping_price >= 200 \
                    and order_weight * 16 < 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, ["Amazon USPS First Class Mail Signature Required"])
            elif order_shipping_price >= 100 \
                    and order_weight * 16 >= 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, [
                    # "Amazon Fedex Ground",
                                              "Amazon UPS Ground",
                                              "Amazon USPS Priority Mail"])
            elif order_shipping_price >= 100 \
                    and order_weight * 16 < 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, ["Amazon USPS First Class Mail"])
            elif order_shipping_price < 100 \
                    and order_weight * 16 >= 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, [
                    # "Amazon Fedex Ground",
                    "Amazon UPS Ground",
                                              "Amazon USPS Priority Mail"])
            elif order_shipping_price < 100 \
                    and order_weight * 16 < 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, ["Amazon USPS First Class Mail"])
            elif order_with_nuc is True:
                self.get_rate(odoo_order_id, [
                    # "Amazon Fedex Ground",
                    "Amazon UPS Ground"])
        elif shipping_service_name == "Standard" and order_post_office is True:
            if order_shipping_price >= 200 \
                    and order_weight * 16 >= 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, ["Amazon USPS Priority Mail Signature Required"])
            elif order_shipping_price >= 200 \
                    and order_weight * 16 < 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, ["Amazon USPS First Class Mail Signature Required"])
            elif order_shipping_price >= 100 \
                    and order_weight * 16 >= 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, ["Amazon USPS Priority Mail"])
            elif order_shipping_price >= 100 \
                    and order_weight * 16 < 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, ["Amazon USPS First Class Mail"])
            elif order_shipping_price < 100 \
                    and order_weight * 16 >= 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, ["Amazon USPS Priority Mail"])
            elif order_shipping_price < 100 \
                    and order_weight * 16 < 15 \
                    and order_with_nuc is False:
                self.get_rate(odoo_order_id, ["Amazon USPS First Class Mail"])
            elif order_with_nuc is True:
                print('NUC')
                self.get_rate(odoo_order_id, [
                    # "Amazon Fedex Ground",
                                              "Amazon UPS Ground"])
        elif shipping_service_name == "SecondDay":
            if partner_state_id in secondday_state_id_list and order_shipping_price < 300:
                self.get_rate(odoo_order_id, [
                    # "Amazon Fedex Ground",
                    "Amazon UPS Ground"])
            elif partner_state_id in secondday_state_id_list and order_shipping_price >= 300:
                self.get_rate(odoo_order_id, [
                    # "Amazon Fedex Ground Signature Required",
                                              "Amazon UPS Ground Signature Required"])
            else:
                if order_with_nuc is False:
                    if order_shipping_price < 200:
                        self.get_rate(odoo_order_id, ["Amazon UPS 2nd Day Air®"
                                                      # "Amazon Fedex 2nd Day"
                                                      ])
                    elif order_shipping_price >= 200:
                        self.get_rate(odoo_order_id, ["Amazon UPS 2nd Day Air® Signature Required"
                                                      # "Amazon Fedex 2nd Day Signature Required"
                                                      ])
                else:
                    if order_shipping_price < 200:
                        self.get_rate(odoo_order_id, ["Amazon UPS 2nd Day Air®"
                                                      # "Amazon Fedex 2nd Day"
                                                      ])
                    elif order_shipping_price >= 200:
                        self.get_rate(odoo_order_id, [
                            "Amazon UPS 2nd Day Air® Signature Required"
                            # "Amazon Fedex 2nd Day Signature Required"
                        ])
        elif shipping_service_name == "Expedited":
            if partner_state_id in expedited_state_id_list:
                if order_shipping_price < 200:
                    self.get_rate(odoo_order_id, [
                        # "Amazon Fedex Ground",
                                                  "Amazon UPS Ground"])
                elif order_shipping_price >= 200:
                    self.get_rate(odoo_order_id, [
                        # "Amazon Fedex Ground Signature Required",
                                                  "Amazon UPS Ground Signature Required"])
            else:
                if order_with_nuc is False:
                    if order_shipping_price < 200:
                        self.get_rate(odoo_order_id, ["Amazon UPS 2nd Day Air®"
                            # , "Amazon Fedex 2nd Day"
                                                      ])
                    elif order_shipping_price >= 200:
                        self.get_rate(odoo_order_id, ["Amazon UPS 2nd Day Air® Signature Required"
                            # ,"Amazon Fedex 2nd Day Signature Required"
                                                      ])
                else:
                    if order_shipping_price < 200:
                        self.get_rate(odoo_order_id, ["Amazon Fedex 2nd Day"])
                    elif order_shipping_price >= 200:
                        self.get_rate(odoo_order_id, ["Amazon Fedex 2nd Day Signature Required"])

    def add_order_to_odoo(self, order_data):
        for order in order_data:
            product_not_found_array = []
            order_with_nuc = False
            order_weight = 0
            order_not_add = False
            less_quantity = False
            order_post_office = False
            marketplace_name = self.get_marketplace_name(order['advancedOptions']['storeId'])
            if order['orderNumber'] == 'WH/OUT/03723' or order['customerEmail'] is None:
                continue
            if 'PO BOX' in order['shipTo']['street1']:
                order_post_office = True
            elif order['shipTo']['street2'] is not None:
                if 'PO BOX' in order['shipTo']['street1']:
                    order_post_office = True
            # print(order['orderNumber'])
            odoo_order_id = self.get_info_db(order['orderNumber'], 'sale.order', '=?', 'x_marketplace_id')
            if odoo_order_id:
                print("In odoo")
                continue
            partner_id = self.add_customer_to_odoo(order)
            # partner_id = self.get_info_db(order['customerEmail'], 'res.partner', '=?', 'email')
            self.region = order['shipTo']['country']
            # if isinstance(partner_id, list):
            #     partner_id = self.add_customer_to_odoo(order, marketplace_name)
            product_item = []
            purchase_date = datetime.strptime(order['orderDate'].split('.')[0], '%Y-%m-%dT%H:%M:%S')
            if order['shipByDate'] is not None and order['shipByDate'] != 'None':
                ship_date = datetime.strptime(order['shipByDate'].split('.')[0], '%Y-%m-%dT%H:%M:%S')
                ship_by = datetime.strptime(order['shipByDate'].split('.')[0], '%Y-%m-%dT%H:%M:%S')
                delivery_by = datetime.strptime(order['shipByDate'].split('.')[0], '%Y-%m-%dT%H:%M:%S')
            else:
                ship_date = datetime.now() + timedelta(days=2)
                ship_by = datetime.now() + timedelta(days=2)
                delivery_by = datetime.now() + timedelta(days=2)
            for item in order['items']:
                partnumber_list = list()
                try:
                    sku = core.SKU(item['sku'])
                    sb_pn = sku.short_brand() + "-" + sku.part_number()
                    print(sb_pn)
                except:
                    product_not_found_array.append(item['sku'] +
                                                   ' Quantity in order '+str(item['quantity']) +
                                                   ' Total price for product '+str(item['unitPrice']
                                                                                   * item['quantity']))
                    continue
                if sku.version() != 'PS4' \
                        and sku.version() != 'PS3' \
                        and sku.version() != 'PS5' \
                        or order['tagIds'] is not None:
                    order_not_add = True
                    continue
                # if sku.short_brand() == 'NUC' or sku.short_brand() == 'DIV':
                #     order_with_nuc = True
                product_template_id = self.get_info_db(sb_pn, 'product.template', '=?'
                                                       , 'default_code')
                # print(item['sku'])
                if not product_template_id:
                    brand_id = self.get_info_db(sku.short_brand(), 'x_brand_mapping', '=', 'x_name', None,
                                                'search_read', ["x_brand"])
                    # print(brand_id)
                    if brand_id:
                        if isinstance(brand_id, dict):
                            brand_name = self.get_info_db(brand_id['x_brand'][0], 'x_brands', '=', 'id', None,
                                                          'search_read', ["x_short_name"])['x_short_name']
                            sb_pn = brand_name + "-" + sku.part_number()
                            product_template_id = self.get_info_db(sb_pn, 'product.template', '=?', 'default_code')
                        elif isinstance(brand_id, list):
                            brand_name = self.get_info_db(brand_id[0]['x_brand'][0], 'x_brands', '=', 'id', None,
                                                         'search_read', ["x_short_name"])['x_short_name']
                            sb_pn = brand_name + "-" + sku.part_number()
                            product_template_id = self.get_info_db(sb_pn, 'product.template', '=?'
                                                                  , 'default_code')
                if isinstance(product_template_id, list):
                    pn_data = self.get_info_db(sb_pn, 'x_sub_part_number', '=', 'x_name', None,
                                               'search_read', ["x_product_rel"])
                    if len(pn_data) > 0:
                        product_template_id = pn_data["x_product_rel"][0]
                    else:
                        product_not_found_array.append(item['sku'] +
                                                       ' Quantity in order ' + str(item['quantity']) +
                                                       ' Total price for product ' + str(
                            item['unitPrice'] * item['quantity']))
                        continue
                sub_partnumber = self.get_info_db(product_template_id, 'x_sub_part_number', '=',
                                                  'x_product_rel',
                                                  None, 'search_read', ["x_name"])
                if isinstance(sub_partnumber, dict):
                    partnumber_list.append(sub_partnumber['x_name'])
                    if sub_partnumber['x_name'] == sku.part_number():
                        part_number = self.get_info_db(product_template_id, 'product.template', '=', 'id',
                                                       None, 'search_read', ["x_part_number",
                                                                             "weight",
                                                                             "x_oversized"])
                        partnumber_list.append(part_number['x_part_number'])
                    else:
                        partnumber_list.append(sku.part_number())
                elif isinstance(sub_partnumber, list):
                    for sub in sub_partnumber:
                        partnumber_list.append(sub['x_name'])
                    if sku.part_number() in partnumber_list:
                        part_number = self.get_info_db(product_template_id, 'product.template', '=', 'id',
                                                       None, 'search_read', ["x_part_number",
                                                                             "weight",
                                                                             "x_oversized"])
                        partnumber_list.append(part_number['x_part_number'])
                    else:
                        partnumber_list.append(sku.part_number())
                if self.is_chemical(product_template_id) is True:
                    order_with_nuc = True
                product_id = self.get_info_db(product_template_id, 'product.product', '=?',
                                              'product_tmpl_id')
                product_quantity = int(sku.case_quantity()) * int(
                                        item['quantity'])
                order_weight += float(self.get_info_db(product_template_id, 'product.template', '=', 'id', None,
                                                       'search_read', ["weight"])['weight']) * product_quantity

                price_unit = round(float(item['unitPrice']) / product_quantity, 2) * item['quantity']
                delivery_lead_time = (ship_date - purchase_date).days

                add_order_line = True
                # if len(product_item) > 0:
                #     for col in range(len(product_item)):
                #         if product_item[col][2]['product_id'] == product_id:
                #             product_item[col][2]['product_uom_qty'] += int(product_quantity)
                #             add_order_line = False
                if add_order_line is True:
                    if "Amazon" in marketplace_name:
                        product_item.append([0, 0, {
                                'product_id': product_id,
                                'name': item['name'],
                                'customer_lead': delivery_lead_time,
                                'product_uom_qty': int(product_quantity),
                                'route_id': 3,
                                'price_unit': round(price_unit, 2),
                                'x_amazon_order_item_id': item['lineItemKey'],
                                'x_order_sku': item['sku']
                            }])
                    else:
                        product_item.append([0, 0, {
                            'product_id': product_id,
                            'name': item['name'],
                            'customer_lead': delivery_lead_time,
                            'product_uom_qty': int(product_quantity),
                            'route_id': 3,
                            'price_unit': round(price_unit, 2),
                            'x_order_sku': item['sku']
                        }])
            for product in product_item:
                stock_qty = self.get_product_stock_qty(product[2]["product_id"])
                product_quantity = int(product[2]["product_uom_qty"])
                if len(stock_qty) != 0:
                    qty_available = 0
                    qty_reserved = 0
                    for qty_data in stock_qty:
                        qty_available += qty_data["quantity"]
                        qty_reserved += qty_data["reserved_quantity"]
                    if (qty_available - qty_reserved - int(product_quantity)) < 0:
                        less_quantity = True
                else:
                    less_quantity = True
            if order_not_add is True:
                print("Not ps4,ps3,ps5 or Prime")
                continue
            order_vals = {
                'partner_id': partner_id,
                'validity_date': purchase_date.strftime('%Y-%m-%d %H:%M:%S'),
                'expected_date': ship_by.strftime('%Y-%m-%d %H:%M:%S'),
                'commitment_date': delivery_by.strftime('%Y-%m-%d %H:%M:%S'),
                'order_line': product_item,
                'x_marketplace_id': order['orderNumber'],
                'x_marketplace_name': marketplace_name + ' ' + order['shipTo']['country'],
                'x_shipstation_id': order['orderId'],
                'x_customer_delivery_paid': float(order['shippingAmount'])
            }
            if order['requestedShippingService'] != None and order['requestedShippingService'] != "None":
                order_vals['x_shipping_method'] = self.get_shipping_method_amazon(order['requestedShippingService'])
            if order['orderTotal'] >= 200:
                order_vals['x_signature'] = True
            if product_not_found_array or order['shipTo'][
                'addressVerified'] == 'Address validation failed' or isinstance(order['shipTo']['phone'], str) and \
                    order['shipTo']['phone'].isdigit() and len(order['shipTo']['phone']) < 10:
                if product_not_found_array:
                    order_vals['note'] = 'Order not found products: '
                    for i in product_not_found_array:
                        order_vals['note'] += i + ' '
                else:
                    order_vals['note'] = 'Address validation failed'
                    if isinstance(order['shipTo']['phone'], str) and order['shipTo']['phone'].isdigit() and len(
                            order['shipTo']['phone']) < 10:
                        order_vals['note'] += ', invalid phone'
                if order_post_office is True:
                    order_vals['note'] += ' PO BOX'
                self.create_data_db(order_vals, 'sale.order')
            else:
                if order_post_office is True:
                    order_vals['note'] = ' PO BOX'
                odoo_order_id = self.create_data_db(order_vals, 'sale.order')
                if order['requestedShippingService'] != None and order['requestedShippingService'] != "None":
                    if 'Amazon US' == marketplace_name + ' ' + order['shipTo']['country'] \
                        and less_quantity is False and order_post_office is False:
                        print('added')
                        shipping_service_name = self.get_shipping_method_amazon(order['requestedShippingService'])
                        partner_state_id = \
                            self.model.execute_kw(self.info['database'], self.uid, self.info['password'], 'res.partner',
                                             'search_read', [[['id', '=', partner_id]]],
                                             {"limit": 1, "fields": ["state_id"]})[0]['state_id'][0]
                        self.add_shipping_method_amazon(odoo_order_id, shipping_service_name, order['orderTotal'],
                                                        order_weight, order_with_nuc, partner_state_id, order_post_office)

    @staticmethod
    def get_merged_product(product, file):
        part_number = product['part_number']
        brand = product['brand']
        res = list()
        for pn in part_number:
            data_find = [product_file['sku'] for product_file in file if
                         (product_file['sku'].find(brand + '-' + pn) != -1)]
            if len(data_find) > 0:
                for n in data_find:
                    res.append(n)
        if res:
            return res
        return None

def main():
    begin_time = datetime.now()
    shipstation = ShipstationAmazon()
    for page in range(1, 15):
        order_data = shipstation.get_shipstation_orders(page)
        if len(order_data) == 0:
            break
        shipstation.add_order_to_odoo(order_data)
        # time.sleep(60)
    print(datetime.now() - begin_time)


if __name__ == "__main__":
    main()
