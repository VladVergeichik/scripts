from sku import SKU
from shipstation import ShipstationBase


class ComputeMarginality(ShipstationBase):

    def get_orders_without_marginality(self):
        cur = self.conn.cursor()
        query = """SELECT so.id,
       so.x_marketplace_name,
       so.x_marketplace_id,
       so.x_customer_delivery_paid,
       array_to_json(array_agg((sol.name, sol.is_delivery, (CASE
						   WHEN sol.is_delivery is TRUE
						   THEN sol.price_total
						   ELSE sol.price_total * (CASE
											   WHEN so.x_marketplace_name = 'Amazon US'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
											   WHEN so.x_marketplace_name = 'Amazon CA'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
											   WHEN so.x_marketplace_name = 'Amazon FBA US' or so.x_marketplace_name = 'Amazon US FBA'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
						                       WHEN so.x_marketplace_name = 'Amazon FBA CA' or so.x_marketplace_name = 'Amazon CA FBA'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
                                               WHEN so.x_marketplace_name = 'Walmart US'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) / 100
												    ELSE 0.85
												    END)
											   ELSE 1
											   END) -
											(CASE
											   WHEN (SELECT price_unit
											   FROM purchase_order_line
											   WHERE write_date <= so.date_order
												 AND product_id = sol.product_id AND price_unit > 0 AND product_uom_qty > 0 ORDER BY write_date DESC LIMIT 1) IS NOT NULL
												THEN (SELECT price_unit
											   FROM purchase_order_line
											   WHERE write_date <= so.date_order
												 AND product_id = sol.product_id AND price_unit > 0 AND product_uom_qty > 0 ORDER BY write_date DESC LIMIT 1)
											   WHEN (SELECT price FROM product_supplierinfo as ps WHERE ps.product_tmpl_id = (SELECT product_tmpl_id FROM product_product WHERE id = sol.product_id) AND min_qty = 1 LIMIT 1) IS NOT NULL
											   THEN (SELECT price FROM product_supplierinfo as ps WHERE ps.product_tmpl_id = (SELECT product_tmpl_id FROM product_product WHERE id = sol.product_id) AND min_qty = 1 LIMIT 1)
											   WHEN (SELECT price FROM product_supplierinfo as ps WHERE ps.product_tmpl_id = (SELECT product_tmpl_id FROM product_product WHERE id = sol.product_id)  LIMIT 1) IS NOT NULL
											   THEN (SELECT price FROM product_supplierinfo as ps WHERE ps.product_tmpl_id = (SELECT product_tmpl_id FROM product_product WHERE id = sol.product_id)  LIMIT 1)
											   ELSE sol.price_unit
											   END) * sol.product_uom_qty END),
						                    (CASE 
						                    WHEN so.x_marketplace_name = 'Amazon US FBA'
						                        THEN (CASE
												    WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
												    ELSE 0
												    END)
											WHEN so.x_marketplace_name = 'Amazon CA FBA'
						                        THEN (CASE
												    WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
												    ELSE 0
												    END)	    
						                        ELSE 0
						                        END), sol.x_order_sku, sol.product_uom_qty))) as sol_data
				FROM sale_order as so
					INNER JOIN sale_order_line sol on so.id = sol.order_id
				WHERE so.x_marginality is NULL 
				AND so.state = 'done'
				GROUP BY so.id"""
        # so.id not in (SELECT order_id FROM sale_order_line WHERE route_id = 6 or price_unit = 1)
        cur.execute(query)
        sales = cur.fetchall()
        all = 0
        minus = 0
        for sale in sales:
            print(sale)
            delivery_price = 0
            sale_order_price = 0
            for data in sale[4]:
                if data['f2'] is True:
                    if data['f3'] == 0:
                        if 'Estimated Cost' in data['f1']:
                            delivery_price += float(data['f1'].split('$')[1].replace(' )', '').strip())
                    else:
                        delivery_price += data['f3']
                else:
                    sale_order_price += data['f3']
            if delivery_price > 0:
                marginality = round(sale_order_price - delivery_price, 2)
                if sale[3] is not None:
                    marginality += float(sale[3])
            else:
                if sale[1] == 'Amazon US FBA' or sale[1] == 'Amazon CA FBA' or sale[
                    1] == 'Amazon FBA CA' or 'Amazon FBA US':
                    print(sale[4][0]['f5'])
                    if sale[4][0]['f4'] != 0:
                        sku_class = SKU()
                        qty = int(sale[4][0]['f6']) \
                            # * int(sku_class.validate_sku(sale[4][0]['f5'])[sale[4][0]['f5']]['case_quantity'])
                        # print(int(sale[4][0]['f6']))
                        # if sale[3] is not null:
                        print(qty, sale_order_price, sale[4][0]['f4'])
                        marginality = round(sale_order_price, 2) - float(sale[4][0]['f4']) * qty
                        if sale[3] is not None:
                            marginality += float(sale[3])
                        marginality = str(round(marginality, 2))
                    else:
                        marginality = sale_order_price
                        if sale[3] is not None:
                            marginality += float(sale[3])
                        marginality = str(round(marginality, 2)) + ' not found FBA Fee'
                else:
                    # marginality = str(round(sale_order_price, 2) + float(sale[3]))+' without delivery'
                    marginality = sale_order_price
                    if sale[3] is not None:
                        marginality += float(sale[3])
                    marginality = str(round(marginality, 2)) + ' without delivery'
            print(sale[1], sale[2], marginality)
            # print(sale[0])

            self.model.execute_kw(self.info["database"], self.uid, self.info["password"], 'sale.order', 'write',
                                  [[sale[0]], {
                                      'x_marginality': marginality
                                  }])
        # with open('marginality.csv', 'a') as f:
        # 	writer = csv.writer(f)
        # 	print(sale)
        # 	writer.writerow((sale[2], sale[1], marginality, sale))
        # if isinstance(marginality, float) or isinstance(marginality, int):
        # 	all += marginality
        # 	if marginality < 0:
        # 		minus += 1
        print(all, minus)

    def get_product_info(self):
        cur = self.conn.cursor()
        query = """SELECT ps.id, ps.default_code, ps.name, p.name as vendor, p.min_qty as vendor_qty, 
					p.price as vendor_price, ps.weight
					FROM product_template as ps INNER JOIN product_supplierinfo p on ps.id = p.product_tmpl_id
					WHERE active is TRUE"""
        cur.execute(query)
        products = cur.fetchall()
        data = list()
        for i in products:
            weight_uom_name = self.model.execute_kw(self.info['database'], self.uid, self.info['password'],
                                                    'product.template', 'search_read',
                                                    [[['id', '=', i[0]],
                                                      ]],
                                                    {"fields": ["weight_uom_name"], "order": "id DESC"})
            data_e = list(i)
            data_e.append(weight_uom_name[0]['weight_uom_name'])
            data.append(data_e)

    def compute_order_margin(self):
        query_orders = """SELECT so.id,
       so.x_marketplace_name,
       so.x_marketplace_id,
       so.x_customer_delivery_paid,
       array_to_json(array_agg((sol.name, sol.product_id, (SELECT product_tmpl_id FROM product_product WHERE id = sol.product_id), sol.is_delivery, (CASE
						   WHEN sol.is_delivery is TRUE
						   THEN sol.price_total
						   ELSE sol.price_total * (CASE
											   WHEN so.x_marketplace_name = 'Amazon US'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
											   WHEN so.x_marketplace_name = 'Amazon CA'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
											   WHEN so.x_marketplace_name = 'Amazon FBA US' or so.x_marketplace_name = 'Amazon US FBA'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
						                       WHEN so.x_marketplace_name = 'Amazon FBA CA' or so.x_marketplace_name = 'Amazon CA FBA'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
                                               WHEN so.x_marketplace_name = 'Walmart US'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) / 100
												    ELSE 0.85
												    END)
											   WHEN so.x_marketplace_name = 'Shopify US'
											   THEN 1
											   WHEN so.x_marketplace_name = 'Ebay US' or so.x_marketplace_name = 'Ebay CA' 
											    THEN 0.88
											   ELSE 1
											   END) END),
						                    (CASE 
						                    WHEN so.x_marketplace_name = 'Amazon US FBA'
						                        THEN (CASE
												    WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
												    ELSE 0
												    END)
											WHEN so.x_marketplace_name = 'Amazon CA FBA'
						                        THEN (CASE
												    WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
												    ELSE 0
												    END)    
						                        ELSE 0
						                        END), sol.x_order_sku, sol.product_uom_qty, (CASE
											   WHEN so.x_marketplace_name = 'Amazon US'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
											   WHEN so.x_marketplace_name = 'Amazon CA'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
											   WHEN so.x_marketplace_name = 'Amazon FBA US' or so.x_marketplace_name = 'Amazon US FBA'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
						                       WHEN so.x_marketplace_name = 'Amazon FBA CA' or so.x_marketplace_name = 'Amazon CA FBA'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
												    ELSE 0.85
												    END)
                                               WHEN so.x_marketplace_name = 'Walmart US'
												THEN (CASE
												    WHEN (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) is not null
												    THEN 1 - (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) / 100
												    ELSE 0.85
												    END)
											   WHEN so.x_marketplace_name = 'Shopify US'
											   THEN 1
											   WHEN so.x_marketplace_name = 'Ebay US' or so.x_marketplace_name = 'Ebay CA' 
											    THEN 0.88
											   ELSE 1
											   END), (CASE 
						                    WHEN so.x_marketplace_name = 'Amazon US FBA'
						                        THEN (CASE
												    WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
												    ELSE 0
												    END)
											WHEN so.x_marketplace_name = 'Amazon CA FBA'
						                        THEN (CASE
												    WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
												    THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
												    ELSE 0
												    END)    
						                        ELSE 0
						                        END), sol.price_total))) as sol_data
				FROM sale_order as so
					INNER JOIN sale_order_line sol on so.id = sol.order_id
				WHERE so.x_marginality is NULL
		AND so.state = 'done'
		AND so.id not in (130132, 132614, 132917, 133401, 133629, 133739, 134201, 134199)
		AND so.id not in (SELECT order_id FROM sale_order_line WHERE route_id = 6 or price_unit = 1)
		GROUP BY so.id"""

        cur = self.conn.cursor()
        cur.execute(query_orders)
        orders = cur.fetchall()
        # url = "http://data.fixer.io/api/latest?access_key=94775f013cd654d9a12cdccf2f4cb33e&symbols=USD,CAD"
        # payload = {}
        # response = requests.request("GET", url)
        # rates = response.json()['rates']['USD'] / response.json()['rates']['CAD']
        # rates_another = response.json()['rates']['CAD'] / response.json()['rates']['USD']

        for order in orders:
            try:
                print(order[0])
                delivery_price = 0
                sale_order_price = 0
                unit_price_order = 0
                # if  order[1] == 'Amazon CA FBA' \
                # 		or order[1] == 'Amazon FBA CA' \
                # 		or order[1] == 'Amazon US FBA' \
                # 		or order[1] == 'Amazon FBA US':
                # if 0 in [product['f10'] for product in order[4]]:
                # 	continue
                for product in order[4]:
                    product_stock_unit_cost = 0
                    qty = self.model.execute_kw(self.info['database'], self.uid, self.info['password'],
                                                'product.template', 'search_read', [[['id', '=', product['f3']]]],
                                                {"fields": ["free_to_use"]})
                    if not qty:
                        qty = 0
                    else:
                        qty = qty[0]['free_to_use']
                    if qty <= 0:
                        cur.execute("""SELECT product_id, price_unit 
						FROM purchase_order_line WHERE product_id = (SELECT id FROM product_product 
						WHERE product_tmpl_id = """ + str(product['f3']) + """ LIMIT 1) and state != 'done' 
						and product_uom_qty > qty_received AND price_unit > 0 ORDER BY write_date DESC LIMIT 1""")
                        stock_unit_cost = cur.fetchall()
                        if len(stock_unit_cost) > 0:
                            product_stock_unit_cost = stock_unit_cost[0][1]
                        else:
                            standard_price = \
                            self.model.execute_kw(self.info['database'], self.uid, self.info['password'],
                                                  'product.template', 'search_read', [[['id', '=', product['f3']]]],
                                                  {"fields": ["standard_price"]})[0]['standard_price']
                            product_stock_unit_cost = round(standard_price, 2)
                    else:
                        cur.execute("""SELECT product_uom_qty, price_unit, date, origin FROM stock_move 
						WHERE product_id = (SELECT id FROM product_product WHERE product_tmpl_id = """ + str(
                            product['f3']) + """ LIMIT 1) 
						AND state = 'done' AND reference LIKE '%IN/%' AND origin LIKE 'P%' AND price_unit != 0 ORDER by date DESC""")
                        stock_move = cur.fetchall()
                        current_stock = []
                        qty_in_stock = 0
                        for move in stock_move:
                            if qty_in_stock + move[0] < qty:
                                qty_in_stock = qty_in_stock + move[0]
                                current_stock.append((int(move[0]), move[1]))
                            else:
                                qty_last = int(qty) - int(qty_in_stock)
                                current_stock.append((qty_last, move[1]))
                                break
                        if sum(i[0] for i in current_stock) < qty:
                            st_price = self.model.execute_kw(self.info['database'], self.uid, self.info['password'],
                                                             'product.template', 'search_read',
                                                             [[['id', '=', product['f3']]]],
                                                             {"fields": ["standard_price"]})[0]['standard_price']
                            st_price = round(st_price, 2)
                            current_stock.append([qty - sum(i[0] for i in current_stock), st_price])
                        current_unit_cost = round(sum(i[0] * i[1] for i in current_stock) / qty, 2)
                        if current_unit_cost == 0:
                            current_unit_cost = \
                            self.model.execute_kw(self.info['database'], self.uid, self.info['password'],
                                                  'product.template', 'search_read', [[['id', '=', product['f3']]]],
                                                  {"fields": ["standard_price"]})[0]['standard_price']
                            current_unit_cost = round(current_unit_cost, 2)
                        product_stock_unit_cost = current_unit_cost
                    if product['f4'] is False:
                        unit_price_order += float(product['f11'])
                    query = 'UPDATE sale_order_line SET x_unit_cost_stock = ' \
                            + str(product_stock_unit_cost) + ', x_fee = ' + str(
                        1 - product['f9']) + ', x_fba_fee = ' + str(product['f10']) + ' WHERE order_id = ' \
                            + str(
                        order[0]) + ' AND product_id = (SELECT id FROM product_product WHERE product_tmpl_id = ' \
                            + str(product['f3']) + ' LIMIT 1)'
                    cur.execute(query)
                    self.conn.commit()
                    if order[1] == 'Ebay US' and product['f4'] is not True or order[1] == 'Ebay CA' and product[
                        'f4'] is not True:
                        sku_class = SKU()
                        data_sku = sku_class.validate_sku(product['f7'])
                        qty = int(product['f8']) / int(data_sku[product['f7']]['case_quantity'])
                        sale_order_price = sale_order_price - 0.3
                    if product['f4'] is True:
                        if product['f5'] == 0:
                            if 'Estimated Cost' in product['f1']:
                                delivery_price += float(product['f1'].split('$')[1].replace(' )', '').strip())
                        else:
                            delivery_price += product['f5']
                    else:
                        sale_order_price += product['f5'] - (float(product_stock_unit_cost) * float(product['f8']))
                    if delivery_price > 0:
                        marginality = round(sale_order_price - delivery_price, 2)
                        if order[3] is not None:
                            marginality += float(order[3])
                        marginality = round(marginality, 2)
                    else:
                        marginality = round(sale_order_price, 2)
                        add_message = False
                        if order[1] == 'Amazon US FBA' or order[1] == 'Amazon FBA US':
                            for product in order[4]:
                                if product['f6'] != 0:
                                    sku_class = SKU()
                                    data_sku = sku_class.validate_sku(product['f7'])
                                    qty = int(product['f8']) / int(data_sku[product['f7']]['case_quantity'])
                                    marginality -= float(product['f6']) * qty
                                    marginality = round(marginality, 2)
                                else:
                                    add_message = True
                            if order[3] is not None:
                                marginality += float(order[3])
                            marginality = round(marginality, 2)
                            if add_message is True:
                                marginality = str(marginality) + ' not found FBA Fee'
                        elif order[1] == 'Amazon CA FBA' or order[1] == 'Amazon FBA CA':
                            for product in order[4]:
                                print(product)
                                if product['f6'] != 0:
                                    sku_class = SKU()
                                    data_sku = sku_class.validate_sku(product['f7'])
                                    qty = int(order[4][0]['f8']) / int(data_sku[order[4][0]['f7']]['case_quantity'])
                                    marginality -= float(product['f6'] * 0.7573690226941399) * qty
                                    marginality = round(marginality, 2)
                                else:
                                    add_message = True
                            if order[3] is not None:
                                marginality += float(order[3])
                            # marginality = round(marginality, 2)
                            if add_message is True:
                                marginality = str(marginality) + ' not found FBA Fee'
                        else:
                            marginality = sale_order_price
                            if order[3] is not None:
                                marginality += float(order[3])
                            marginality = str(round(marginality, 2)) + ' without delivery'
                if isinstance(marginality, str):
                    m_f = float(marginality.split(' ')[0])
                    if unit_price_order > 0:
                        if order[3] is not None:
                            unit_price_order += float(order[3])
                        x_percent_marg = m_f / unit_price_order
                    else:
                        x_percent_marg = 0
                else:
                    m_f = marginality
                    if unit_price_order > 0:
                        if order[3] is not None:
                            unit_price_order += float(order[3])
                        x_percent_marg = m_f / unit_price_order
                    else:
                        x_percent_marg = 0
                print(order[0], marginality, x_percent_marg)
                query = "UPDATE sale_order SET x_marginality = '" + str(marginality) + "', x_percent_marg = " + str(
                    x_percent_marg) + "  WHERE id = " + str(order[0]) + ""
                print(query)
                cur.execute(query)
                self.conn.commit()
            except:
                print('error')
                continue

    def compute_order_margin_dropship(self):
        query_orders = """SELECT so.id,
	   so.x_marketplace_name,
	   so.x_marketplace_id,
	   so.x_customer_delivery_paid,
	   array_to_json(array_agg((sol.name, sol.product_id, (SELECT product_tmpl_id FROM product_product WHERE id = sol.product_id), sol.is_delivery, (CASE
						   WHEN sol.is_delivery is TRUE
						   THEN sol.price_total
						   ELSE sol.price_total * (CASE
											   WHEN so.x_marketplace_name = 'Amazon US'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Amazon CA'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Amazon FBA US' or so.x_marketplace_name = 'Amazon US FBA'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Amazon FBA CA' or so.x_marketplace_name = 'Amazon CA FBA'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Walmart US'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Shopify US'
											   THEN 0.992
											   WHEN so.x_marketplace_name = 'Ebay US' or so.x_marketplace_name = 'Ebay CA' 
												THEN 0.88
											   ELSE 1
											   END) END),
											(CASE 
											WHEN so.x_marketplace_name = 'Amazon US FBA'
												THEN (CASE
													WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
													ELSE 0
													END)
											WHEN so.x_marketplace_name = 'Amazon CA FBA'
												THEN (CASE
													WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
													ELSE 0
													END)    
												ELSE 0
												END), sol.x_order_sku, sol.product_uom_qty, (CASE
											   WHEN so.x_marketplace_name = 'Amazon US'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Amazon CA'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Amazon FBA US' or so.x_marketplace_name = 'Amazon US FBA'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Amazon FBA CA' or so.x_marketplace_name = 'Amazon CA FBA'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Walmart US'
												THEN (CASE
													WHEN (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) is not null
													THEN 1 - (SELECT x_fee FROM x_walmart_sku WHERE x_name = sol.x_order_sku AND x_fee > 0 LIMIT 1) / 100
													ELSE 0.85
													END)
											   WHEN so.x_marketplace_name = 'Shopify US'
											   THEN 0.992
											   WHEN so.x_marketplace_name = 'Ebay US' or so.x_marketplace_name = 'Ebay CA' 
												THEN 0.88
											   ELSE 1
											   END), (CASE 
											WHEN so.x_marketplace_name = 'Amazon US FBA'
												THEN (CASE
													WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
													ELSE 0
													END)
											WHEN so.x_marketplace_name = 'Amazon CA FBA'
												THEN (CASE
													WHEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1) is not null
													THEN (SELECT x_fee_fba FROM x_amazon_sku WHERE x_name = sol.x_order_sku LIMIT 1)
													ELSE 0
													END)    
												ELSE 0
												END), sol.price_total, sol.x_unit_cost_stock))) as sol_data
				FROM sale_order as so
					INNER JOIN sale_order_line sol on so.id = sol.order_id
				WHERE so.x_marginality is NULL
		AND so.state = 'done'
		AND so.id not in (130132, 132614, 132917, 133401, 133629, 133739, 134201, 134199)
		AND so.id in (SELECT order_id FROM sale_order_line WHERE route_id = 6 or price_unit = 1 AND x_unit_cost_stock > 0)
		GROUP BY so.id"""
        cur = self.conn.cursor()
        cur.execute(query_orders)
        orders = cur.fetchall()
        # url = "http://data.fixer.io/api/latest?access_key=94775f013cd654d9a12cdccf2f4cb33e&symbols=USD,CAD"
        # payload = {}
        # response = requests.request("GET", url)
        # rates = response.json()['rates']['USD'] / response.json()['rates']['CAD']
        # rates_another = response.json()['rates']['CAD'] / response.json()['rates']['USD']
        for order in orders:
            try:
                print(order[0])
                delivery_price = 0
                sale_order_price = 0
                unit_price_order = 0
                for product in order[4]:
                    product_stock_unit_cost = product['f12']
                    if product['f4'] is False:
                        unit_price_order += float(product['f11'])
                        query = 'UPDATE sale_order_line SET x_fee = ' + str(
                            1 - product['f9']) + ', x_fba_fee = ' + str(product['f10']) + ' WHERE order_id = ' \
                                + str(
                            order[0]) + ' AND product_id = (SELECT id FROM product_product WHERE product_tmpl_id = ' \
                                + str(product['f3']) + ' LIMIT 1)'
                    cur.execute(query)
                    self.conn.commit()
                    if order[1] == 'Ebay US' and product['f4'] is not True or order[1] == 'Ebay CA' and product[
                        'f4'] is not True:
                        sku_class = SKU()
                        data_sku = sku_class.validate_sku(product['f7'])
                        qty = int(product['f8']) / int(data_sku[product['f7']]['case_quantity'])
                        sale_order_price = sale_order_price - 0.3
                    if product['f4'] is True:
                        if product['f5'] == 0:
                            if 'Estimated Cost' in product['f1']:
                                delivery_price += float(product['f1'].split('$')[1].replace(' )', '').strip())
                        else:
                            delivery_price += product['f5']
                    else:
                        sale_order_price += product['f5'] - (float(product_stock_unit_cost) * float(product['f8']))
                    if delivery_price > 0:
                        marginality = round(sale_order_price - delivery_price, 2)
                        if order[3] is not None:
                            marginality += float(order[3])
                        marginality = round(marginality, 2)
                    else:
                        marginality = round(sale_order_price, 2)
                        add_message = False
                        marginality = sale_order_price
                        if order[3] is not None:
                            marginality += float(order[3])
                        marginality = str(round(marginality, 2))
                if isinstance(marginality, str):
                    m_f = float(marginality.split(' ')[0])
                    if unit_price_order > 0:
                        if order[3] is not None:
                            unit_price_order += float(order[3])
                        x_percent_marg = m_f / unit_price_order
                    else:
                        x_percent_marg = 0
                else:
                    m_f = marginality
                    if unit_price_order > 0:
                        if order[3] is not None:
                            unit_price_order += float(order[3])
                        x_percent_marg = m_f / unit_price_order
                    else:
                        x_percent_marg = 0
                print(order[0], marginality, x_percent_marg)
                query = "UPDATE sale_order SET x_marginality = '" + str(marginality) + "', x_percent_marg = " + str(
                    x_percent_marg) + "  WHERE id = " + str(order[0]) + ""
                print(query)
                cur.execute(query)
                self.conn.commit()

            # self.model.execute_kw(self.info["database"], self.uid, self.info["password"], 'sale.order', 'write',
            # 				  [[order[0]], {'x_marginality': marginality, 'x_percent_marg': x_percent_marg}])

            # self.model.execute_kw(self.info["database"], self.uid, self.info["password"], 'sale.order', 'write',
            # 				  [[order[0]], {'x_percent_marg': x_percent_marg}])
            except:
                print('error')
                continue


def main():
    cm = ComputeMarginality()
    cm.compute_order_margin()
    cm.compute_order_margin_dropship()
    cm.conn.close()


if __name__ == '__main__':
    main()
