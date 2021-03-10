# coding: utf-8
from flask import Flask, render_template, send_from_directory, request, send_file, flash, request, redirect, url_for, Blueprint, jsonify
from flask import current_app
from __init__ import db, render_template, send_file
import shopify
import sys
import xmlrpc.client
import csv
import os
import psycopg2
import logging
import requests
from requests.auth import HTTPBasicAuth
from flask_login import login_user, login_required
from werkzeug.utils import secure_filename
from ebaysdk.trading import Connection as Trading


# sys.path.append('/micro/libs')
# import Shopify
import walmart
import uuid
import xlrd
import xlsxwriter
import json
from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.io import show
from bokeh.models import (CDSView, ColorBar, ColumnDataSource,
						  CustomJS, CustomJSFilter,
						  GeoJSONDataSource, HoverTool,
						  LinearColorMapper, Slider)
from bokeh.layouts import column, row, widgetbox
from bokeh.palettes import brewer
from bokeh.embed import file_html
from bokeh.plotting import figure  # Input GeoJSON source that contains features for plotting
import pandas as pd
from bokeh.plotting import figure, output_file, save
# import geopandas as gpd  # Read in shapefile and examine data

ALLOWED_EXTENSIONS = {'xls', 'xlsx', 'csv'}

basic = Blueprint('index', __name__)


@basic.route('/micro/')
@login_required
def index():
	data = {'hello': 3}
	return render_template('index.html', value=data)


@basic.route('/micro/static/<path:path>')
def send_js(path):
	return send_from_directory('static', path)


@basic.route('/micro/data_states/', methods=['GET'])
@login_required
def get_data_state_info():
	conn = psycopg2.connect(host='localhost', user='odoo', password='odooserver', dbname='odooproducts')
	cur = conn.cursor()

	cur.execute("""SELECT round(sum(sol.price_total)), rcs.name  FROM sale_order_line as sol
    INNER JOIN sale_order so on sol.order_id = so.id
INNER JOIN res_partner rp on so.partner_id = rp.id
INNER JOIN res_country_state rcs on rp.state_id = rcs.id
WHERE rcs.name NOT IN ('CALIFORNIA', 'IOWA') AND sol.is_delivery is FALSE	 GROUP BY rcs.name""")
	data_db = cur.fetchall()
	with open('/micro/data_map/states_sales.csv', 'w') as f:
		writer = csv.writer(f)
		writer.writerow(('NAME', 'Sales'))
		for i in data_db:
			writer.writerow((i[1], i[0]))

	state_pop = pd.read_csv('/micro/data_map/states_sales.csv')

	contiguous_usa = gpd.read_file('/micro/data_map/cb_2018_us_state_20m.shp')
	contiguous_usa.head()
	# Merge shapefile with population data
	# pop_states = contiguous_usa.merge(state_pop, left_on = 'NAME', right_on = 'NAME')# Drop Alaska and Hawaii
	# pop_states = pop_states.loc[~pop_states['NAME'].isin(['Alaska', 'Hawaii'])]
	state_pop.head()
	pop_states = contiguous_usa.merge(state_pop, left_on='NAME', right_on='NAME')  # Drop Alaska and Hawaii
	# pop_states = pop_states.loc[~pop_states['NAME'].isin(['Alaska'])]
	m = pop_states.NAME == "Alaska"
	pop_states[m] = pop_states[m].set_geometry(pop_states[m].scale(.2, .2, .2).translate(-80, -40))
	# print(max(state_pop['Sales']))
	geosource = GeoJSONDataSource(geojson=pop_states.to_json())

	# Define color palettes
	palette = brewer['BuGn'][8]
	palette = palette[
			  ::-1]  # reverse order of colors so higher values have darker colors# Instantiate LinearColorMapper that linearly maps numbers in a range, into a sequence of colors.
	color_mapper = LinearColorMapper(palette=palette, low=0,
									 high=max(state_pop['Sales']))  # Define custom tick labels for color bar.
	tick_labels = {'0': '0', '5000': '5,000',
				   '10000': '10,000', '15000': '15,000',
				   '20000': '20,000', '25000': '25,000',
				   '30000': '30,000', '35000': '35,000',
				   '40000': '40,000',
				   '50000': '50,000',
				   '60000': '60,000',
				   '70000': '70,000',
				   '80000': '80,000',
				   '90000': '90,000',
				   '100000': '100,000',
				   '150000': '150,000',
				   '200000': '200,000',
				   '250000': '250,000',
				   '300000': '300,000',
				   '350000': '350,000',
				   '400000': '400,000',
				   '450000': '450,000',
				   '500000': '500,000'
				   }
	color_bar = ColorBar(color_mapper=color_mapper,
						 label_standoff=8,
						 width=500, height=20,
						 border_line_color=None,
						 location=(0, 0),
						 orientation='horizontal',
						 major_label_overrides=tick_labels)  # Create figure object.
	p = figure(title='Sales per states',
			   plot_height=600, plot_width=1350,
			   toolbar_location='below',
			   tools="pan, wheel_zoom, box_zoom, reset")
	p.xgrid.grid_line_color = None
	p.ygrid.grid_line_color = None  # Add patch renderer to figure.
	states = p.patches('xs', 'ys', source=geosource,
					   fill_color={'field': 'Sales',
								   'transform': color_mapper},
					   line_color='gray',
					   line_width=0.25,
					   fill_alpha=1.2)  # Create hover tool
	p.add_tools(HoverTool(renderers=[states],
						  tooltips=[('State', '@NAME'),
									('Sales', '@Sales')]))  # Specify layout
	output_file("/micro/templates/pilot.html")
	save(p)
	return render_template('map_states.html')

@basic.route('/micro/get_amazon_us_info/', methods=['GET'])
@login_required
def get_amazon_us_info():
	return send_file('/odoo_13/odoo/custom/inventory.tsv', as_attachment=True)


@basic.route('/micro/get_amazon_ca_info/', methods=['GET'])
@login_required
def get_amazon_ca_info():
	return send_file('/odoo_13/odoo/custom/inventory_amazon_canada.tsv', as_attachment=True)

@basic.route('/micro/get_ebay_info/', methods=['GET'])
@login_required
def get_ebay_info():
	return send_file('/odoo_13/odoo/custom/ebay_inv.csv', as_attachment=True)


@basic.route('/micro/get_vendor_price_template/', methods=['GET'])
@login_required
def get_vendor_price_template():
	return send_file('vendor_price.xlsx', as_attachment=True)


@basic.route('/micro/get_shopify_price_template/', methods=['GET'])
@login_required
def get_shopify_price_template():
	return send_file('/micro/shopify_price.xlsx', as_attachment=True)


@basic.route('/micro/get_walmart_info/', methods=['GET'])
@login_required
def get_walmart_info():
	return send_file('/odoo_13/odoo/custom/walmart_inventory.csv', as_attachment=True)

@basic.route('/micro/map_states/', methods=['GET'])
@login_required
def get_map_states():
	return render_template('map_states.html')


def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@basic.route('/micro/upload_vendor_price/', methods=['POST'])
@login_required
def upload_vendor_price():
	if request.method == 'POST':
		# check if the post request has the file part
		if 'file' not in request.files:
			flash('No file part')
			return redirect(request.url)
		file = request.files['file']
		# if user does not select file, browser also
		# submit an empty part without filename
		if file.filename == '':
			flash('No selected file')
			return redirect('/micro/')
		if file and allowed_file(file.filename):
			model = xmlrpc.client.ServerProxy('http://localhost:8069/xmlrpc/object')
			info = {'user': 'x', 'password': 'x',
						 'host': 'http://localhost', 'database': 'x'}
			uid = 2
			filename = secure_filename(file.filename)
			file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
			rb = xlrd.open_workbook('/micro/upload/'+filename)
			sheet = rb.sheets()[0]
			data_price = {}
			conn = psycopg2.connect(host='localhost', user='odoo', password='x', dbname='x')
			cur = conn.cursor()
			for data in enumerate(sheet.get_rows()):
				if data[0] == 0:
					continue
				query = """SELECT pt.id, pt.x_map_price, array_to_json(array_agg((ps.id, rp.name, ps.x_vendor_status)))
							FROM product_template pt
							INNER JOIN product_supplierinfo ps on pt.id = ps.product_tmpl_id
							INNER JOIN res_partner rp on ps.name = rp.id
							WHERE pt.default_code = concat((SELECT x_short_name FROM x_brands WHERE x_name = '"""+str(data[1][1].value)+"""'), '-', '"""+str(data[1][2].value).split('.')[0]+"""')
							AND pt.active = True
							GROUP BY pt.id"""
				cur.execute(query)
				data_db = cur.fetchall()
				# current_app.logger.error(str(data[1][2]).split('.')[0])
				# current_app.logger.error(str(data_db))
				# current_app.logger.error(str(data[1][8].value))
				if not data_db:
					continue
				if data[1][9].value != '':
					for i in data_db[0][2]:
						if i['f2'] == data[1][0].value and i['f3'] == 'primary':
							query_swo = "UPDATE stock_warehouse_orderpoint SET qty_multiple = "+str(data[1][9].value)+" WHERE id = (SELECT id FROM stock_warehouse_orderpoint WHERE product_id = (SELECT id FROM product_product WHERE product_tmpl_id = "+str(data_db[0][0])+") LIMIT 1)"
							cur.execute(query_swo)
							conn.commit()

			# 	# current_app.logger.error(str(product_id))
				dict_update_product = {}
				if data[1][3].value != '':
					dict_update_product['name'] = data[1][3].value
				if data[1][11].value != '':
					dict_update_product['x_map_price'] = data[1][11].value
				if data[1][4].value != '':
					dict_update_product['weight'] = data[1][4].value
				if data[1][5].value != '':
					dict_update_product['x_length'] = data[1][5].value
				if data[1][6].value != '':
					dict_update_product['x_width'] = data[1][6].value
				if data[1][7].value != '':
					dict_update_product['x_height'] = data[1][7].value
				if data[1][14].value != '':
					dict_update_product['x_upc'] = data[1][14].value
				# if data[1][13].value != '':
				# 	dict_update_product['product_code'] = data[1][7].value
				# current_app.logger.error(str(data[1][3].value))
				# print(1/0)
				if data[1][10].value != '':
					for supplier in data_db[0][2]:
						if supplier['f2'] == data[1][0].value:
							query_update = "UPDATE product_supplierinfo SET price = "+str(data[1][10].value)+" WHERE id = "+str(supplier['f1'])+""
							cur.execute(query_update)
							conn.commit()
							if supplier['f3'] == 'primary':
								model.execute_kw(info["database"], uid, info["password"], 'product.template',
												'write', [[data_db[0][0]], {'standard_price': data[1][10].value}])
				if data[1][8].value != '':
					for supplier in data_db[0][2]:
						if supplier['f2'] == data[1][0].value:
							query_update = "UPDATE product_supplierinfo SET delay = "+str(data[1][8].value)+" WHERE id = "+str(supplier['f1'])+""
							cur.execute(query_update)
							conn.commit()
			# 			# current_app.logger.error(str(query_update))
				if data[1][12].value != '':
					for supplier in data_db[0][2]:
						if supplier['f2'] == data[1][0].value:
							query_update = "UPDATE product_supplierinfo SET product_name = '"+str(data[1][12].value).replace("'", ' ').replace('"', ' ')+"' WHERE id = "+str(supplier['f1'])+""
							current_app.logger.error(str(query_update))
							cur.execute(query_update)
							conn.commit()
				if data[1][13].value != '':
					for supplier in data_db[0][2]:
						if supplier['f2'] == data[1][0].value:
							query_update = "UPDATE product_supplierinfo SET product_code = '"+str(data[1][13].value)+"' WHERE id = "+str(supplier['f1'])+""
							cur.execute(query_update)
							conn.commit()
				if dict_update_product != {}:
					model.execute_kw(info["database"], uid, info["password"], 'product.template',
									 'write', [[data_db[0][0]], dict_update_product])
			conn.close
			return redirect('/micro/')
		return redirect('/micro/')


def login_odoo_api(self):
	common = xmlrpc.client.ServerProxy("http://localhost:8069/xmlrpc/2/common")
	common.version()
	uid = common.authenticate(self.info["database"], self.info["user"], self.info["password"], {})
	self.uid = uid
	return uid

@basic.route('/micro/update_config/', methods=['POST'])
@login_required
def update_config():
	pass

@basic.route('/micro/update_package_qty/', methods=['POST'])
@login_required
def update_package_qty():
	if request.method == 'POST':
		# check if the post request has the file part
		if 'file' not in request.files:
			flash('No file part')
			return redirect(request.url)
		file = request.files['file']
		# if user does not select file, browser also
		# submit an empty part without filename
		if file.filename == '':
			flash('No selected file')
			return redirect('/micro/')
		if file and allowed_file(file.filename):
			conn = psycopg2.connect(host='localhost', user='x', password='x', dbname='x')
			cur = conn.cursor()
			filename = secure_filename(file.filename)
			file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
			rb = xlrd.open_workbook('upload/'+filename)
			sheet = rb.sheets()[0]
			for data in enumerate(sheet.get_rows()):
				if data[0] == 0:
					continue
				query = "UPDATE stock_warehouse_orderpoint SET qty_multiple = "+str(int(data[1][1].value))+" WHERE name = '"+str(data[1][0].value)+"'"
				cur.execute(query)
				conn.commit()
	return redirect('/micro/')

@basic.route('/micro/add_product/', methods=['POST'])
@login_required
def add_product_odoo():
	if request.method == 'POST':
		# check if the post request has the file part
		if 'file' not in request.files:
			flash('No file part')
			return redirect(request.url)
		file = request.files['file']
		# if user does not select file, browser also
		# submit an empty part without filename
		if file.filename == '':
			flash('No selected file')
			return redirect('/micro/')
		if file and allowed_file(file.filename):
			conn = psycopg2.connect(host='localhost', user='x', password='x', dbname='x')
			cur = conn.cursor()
			model = xmlrpc.client.ServerProxy('http://localhost:8069/xmlrpc/object')
			info = {'user': 'x', 'password': 'x',
						 'host': 'localhost', 'database': 'x'}
			uid = 2
			filename = secure_filename(file.filename)
			file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
			rb = xlrd.open_workbook('upload/'+filename)
			sheet = rb.sheets()[0]
			for data in enumerate(sheet.get_rows()):
				if data[0] == 0:
					continue
				query = """SELECT pt.id, pt.x_map_price, array_to_json(array_agg((ps.id, rp.name, ps.x_vendor_status)))
							FROM product_template pt
							INNER JOIN product_supplierinfo ps on pt.id = ps.product_tmpl_id
							INNER JOIN res_partner rp on ps.name = rp.id
							WHERE pt.default_code = concat((SELECT x_short_name FROM x_brands WHERE x_name = '"""+str(data[1][1].value)+"""'), '-', '"""+str(data[1][2].value).split('.')[0]+"""')
							AND pt.active = True
							GROUP BY pt.id"""
				cur.execute(query)
				data_db = cur.fetchall()
				if data_db:
					continue
				dict_update_product = {}
				dict_update_product_vendor = {}
				if data[1][3].value != '':
					dict_update_product['name'] = data[1][3].value
				if data[1][2].value != '':
					dict_update_product['x_part_number'] = data[1][2].value
				if data[1][11].value != '':
					dict_update_product_vendor['price'] = data[1][11].value
				if data[1][10].value != '':
					dict_update_product_vendor['qty_box'] = data[1][10].value
				if data[1][12].value != '':
					dict_update_product['x_map_price'] = data[1][12].value
				if data[1][4].value != '':
					dict_update_product['weight'] = data[1][4].value
				if data[1][5].value != '':
					dict_update_product['x_length'] = data[1][5].value
				if data[1][6].value != '':
					dict_update_product['x_width'] = data[1][6].value
				if data[1][7].value != '':
					dict_update_product['x_height'] = data[1][7].value
				if data[1][14].value != '':
					dict_update_product['barcode'] = data[1][14].value
				query_brand = """SELECT id FROM x_brands WHERE x_name = '""" + str(data[1][1].value) + """'"""
				cur.execute(query_brand)
				brand = cur.fetchall()
				if brand:
					dict_update_product['x_brand'] = brand[0][0]
				else:
					continue
				dict_update_product['type'] = 'product'
				dict_update_product['route_ids'] = [6]
				product_id = model.execute_kw(info["database"], uid, info["password"], 'product.template',
									 'create', [dict_update_product])
				dict_update_product_vendor['product_tmpl_id'] = product_id
				query_vendor = """SELECT id FROM res_partner WHERE name = '""" + str(data[1][0].value) + """'"""
				cur.execute(query_vendor)
				vendor = cur.fetchall()
				if vendor:
					dict_update_product_vendor['name'] = vendor[0][0]
					model.execute_kw(info["database"], uid, info["password"], 'product.supplierinfo',
											  'create', [dict_update_product_vendor])
			conn.close
			return redirect('/micro/')
		return redirect('/micro/')


@basic.route('/micro/get_purchase_info/', methods=['GET'])
@login_required
def get_purchase_info():
	conn = psycopg2.connect(host='localhost', user='odoo', password='odooserver', dbname='odooproducts')
	cur = conn.cursor()
	model = xmlrpc.client.ServerProxy('http://localhost:8069/xmlrpc/object')
	info = {'user': 'x', 'password': 'x',
			'host': 'http://locahost', 'database': 'x'}
	uid = 2
	products = model.execute_kw(info['database'],
								uid,
								info['password'],
								'product.template',
								'search_read',
								[
									[
										('route_ids', '=', 5),
										('company_id', '=', 1),
										('active', '=', True),
										('default_code', '!=', False)
										# ,
										# ('id', '=', 5752)
									]
								], {"fields": ["id", "default_code", 'x_brand', 'x_part_number', 'purchased_product_qty']})
	workbook = xlsxwriter.Workbook('/micro/purchase.xlsx')
	worksheet = workbook.add_worksheet()
	headers = ['Vendor', 'Brand', 'Internal Reference', 'Partnumber', 'Free to use',
			   'On Open Purchase Orders', 'Minimum Quantity', 'Maximum Quantity', 'Qty Multiple',
			   'Cost of Item', '2 months ago Sales', '1 month ago Sales', 'Current Month sales',
			   'Last years next months total', 'Last years 2 months ahead sales', 'Location']
	for head in enumerate(headers):
		worksheet.write(0, head[0], head[1])
	row = 1
	col = 0
	step = 1
	query = """SELECT id, product_tmpl_id FROM product_product WHERE product_tmpl_id in ("""+','.join([str(i['id']) for i in products])+""") """

	cur.execute(query)
	product_product_ids = cur.fetchall()
	for i in product_product_ids:
		for g in products:
			if g['id'] == i[1]:
				g['product_product_id'] = i[0]

	query = """SELECT product_min_qty, product_max_qty, qty_multiple, product_id FROM stock_warehouse_orderpoint
						WHERE product_id in ("""+','.join([str(i['product_product_id']) for i in products])+""") 
						AND active = TRUE"""
	cur.execute(query)
	stock_warehouse_orderpoints = cur.fetchall()
	for i in stock_warehouse_orderpoints:
		for g in products:
			if g['product_product_id'] == i[3]:
				g['min_qty'] = float(i[0])
				g['max_qty'] = float(i[1])
				g['qty_multi'] = float(i[2])

	query = """SELECT sum(product_uom_qty), product_id 
FROM sale_order_line WHERE product_id in ("""+','.join([str(i['product_product_id']) for i in products])+""")
					AND create_date >= date_trunc('month', current_date - interval '2' month)
  					and create_date < date_trunc('month', current_date - interval '1' month) GROUP BY product_id"""
	cur.execute(query)
	sales_last_2_month = cur.fetchall()
	for i in sales_last_2_month:
		for g in products:
			if g['product_product_id'] == i[1]:
				g['last_month_2'] = float(i[0])

	query = """SELECT sum(product_uom_qty), product_id 
	FROM sale_order_line WHERE product_id in (""" + ','.join([str(i['product_product_id']) for i in products]) + """)
						AND create_date >= date_trunc('month', current_date - interval '1' month)
	  					and create_date < date_trunc('month', current_date) GROUP BY product_id"""
	cur.execute(query)
	sales_last_month = cur.fetchall()
	for i in sales_last_month:
		for g in products:
			if g['product_product_id'] == i[1]:
				g['last_month'] = float(i[0])

	query = """SELECT sum(product_uom_qty), product_id 
	FROM sale_order_line WHERE product_id in (""" + ','.join([str(i['product_product_id']) for i in products]) + """)
						AND create_date >= date_trunc('month', current_date) GROUP BY product_id"""
	cur.execute(query)
	sales_cur_month = cur.fetchall()
	for i in sales_cur_month:
		for g in products:
			if g['product_product_id'] == i[1]:
				g['cur_month'] = float(i[0])
	for product in products:
		current_app.logger.error(str(len(products) - step))
		step += 1
		if 'min_qty' not in product.keys():
			product['min_qty'] = 0
			product['max_qty'] = 0
			product['qty_multi'] = 0
		if 'last_month_2' not in product.keys():
			product['last_month_2'] = ''
		if 'last_month' not in product.keys():
			product['last_month'] = ''
		if 'cur_month' not in product.keys():
			product['cur_month'] = ''
		query = """SELECT rp.name, ps.x_vendor_status , price
				FROM product_supplierinfo ps INNER JOIN res_partner rp on ps.name = rp.id
				WHERE ps.product_tmpl_id = """+str(product['id'])+""" """
		cur.execute(query)
		supplier_info = cur.fetchall()
		product['vendor'] = ''
		product['cost'] = 0
		if supplier_info:
			for i in supplier_info:
				if i[1] == 'primary':
					product['vendor'] = i[0]
					product['cost'] = i[2]
					break
		if product['vendor'] == '' and product['cost'] == 0 and supplier_info:
			product['vendor'] = supplier_info[0][0]
			product['cost'] = supplier_info[0][2]
		query = """SELECT sl.name, sq.quantity - sq.reserved_quantity
					FROM stock_quant sq
						INNER JOIN stock_location sl on sq.location_id = sl.id
					WHERE sq.product_id = (SELECT id FROM product_product WHERE product_tmpl_id = """+str(product['id'])+""" LIMIT 1)
					  AND sq.location_id not in (1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 828, 4312, 4342)
					AND sq.company_id = 1"""
		cur.execute(query)
		locations = cur.fetchall()
		for i in locations:
			worksheet.write(row, 0, product['vendor'])
			worksheet.write(row, 1, product['x_brand'][1])
			worksheet.write(row, 2, product['default_code'])
			worksheet.write(row, 3, product['x_part_number'])
			worksheet.write(row, 4, i[1])
			worksheet.write(row, 5, product['purchased_product_qty'])
			worksheet.write(row, 6, product['min_qty'])
			worksheet.write(row, 7, product['max_qty'])
			worksheet.write(row, 8, product['qty_multi'])
			worksheet.write(row, 9, product['cost'])
			worksheet.write(row, 10, product['last_month_2'])
			worksheet.write(row, 11, product['last_month'])
			worksheet.write(row, 12, product['cur_month'])
			worksheet.write(row, 13, '')
			worksheet.write(row, 14, '')
			worksheet.write(row, 15, i[0])
			row += 1
	workbook.close()
	conn.close()
	return send_file('/micro/purchase.xlsx', as_attachment=True)


@basic.route('/micro/upload_ebay_price/', methods=['POST'])
@login_required
def upload_ebay_price():
	if request.method == 'POST':
		info = {'user': 'x', 'password': 'x',
				'host': 'x', 'database': 'x'}
		uid = 2
		model = xmlrpc.client.ServerProxy('http://x:8069/xmlrpc/object')
		if 'file' not in request.files:
			flash('No file part')
			return redirect(request.url)
		file = request.files['file']
		if file.filename == '':
			flash('No selected file')
			return redirect('/micro/')
		if file and allowed_file(file.filename):
			filename = secure_filename(file.filename)
			# current_app.logger.error(str(filename))
			file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
			rb = xlrd.open_workbook('/micro/upload/' + filename)
			sheet = rb.sheets()[0]
			for data in enumerate(sheet.get_rows()):
				if data[0] == 0:
					continue
				product = model.execute_kw(info['database'], uid, info['password'], 'x_ebay_sku', 'search_read',
											[[('x_name', '=', data[1][0].value)]], {"fields": ["x_item_id"]})
				if product:
					current_app.logger.error(str(data[1][0].value))
					current_app.logger.error(str(product[0]["x_item_id"]))
					current_app.logger.error(str(data[1][1].value))
					api = Trading(appid="x",
								  devid="x",
								  certid="x",
								  token="x",
								  debug=False, config_file=None)
					response = api.execute('ReviseFixedPriceItem', {'item': {'ItemID': product[0]["x_item_id"],
																				 'StartPrice': data[1][1].value}})
	return redirect('http://localhost:8015/micro/')


@basic.route('/micro/upload_walmart_price/', methods=['POST'])
@login_required
def upload_walmart_price():
	if request.method == 'POST':
		api = walmart.Walmart(client_id="x",
							  client_secret="x")
		url = "https://marketplace.walmartapis.com/v3/price"
		if 'file' not in request.files:
			flash('No file part')
			return redirect(request.url)
		file = request.files['file']
		if file.filename == '':
			flash('No selected file')
			return redirect('http://localhost:8015/micro/')
		if file and allowed_file(file.filename):
			filename = secure_filename(file.filename)
			# current_app.logger.error(str(filename))
			file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
			rb = xlrd.open_workbook('/micro/upload/' + filename)
			sheet = rb.sheets()[0]
			for data in enumerate(sheet.get_rows()):
				if data[0] == 0:
					continue
				body = {
					"sku": data[1][0].value,
					"pricing": [
						{"currentPriceType": "BASE", "currentPrice": {"currency": "USD", "amount": data[1][1].value}}]}
				current_app.logger.error(str(body))
				headers = {
					'Content-Type': 'application/json',
					'WM_SEC.ACCESS_TOKEN': api.token,
					'WM_SVC.NAME': 'Walmart Marketplace',
					'WM_QOS.CORRELATION_ID': uuid.uuid4().hex,
				}
				requests.request("PUT", url, headers=headers, data=json.dumps(body),
								 auth=HTTPBasicAuth("x",
													"x"))
	return redirect('/micro/')

@basic.route('/micro/api/v1/odoo_brands', methods=['GET'])
def get_brands():
	conn = psycopg2.connect(host='localhost', user='x', password='x', dbname='x')
	cur = conn.cursor()
	query = "SELECT br.x_name, br.x_short_name, array(SELECT x_name FROM x_brand_mapping WHERE x_brand = br.id) FROM x_brands as br"
	name = ''
	if 'name' in request.args:
		name = request.args['name']
	if name != '':
		query = query + " WHERE x_name = '"+name+"'"
	cur.execute(query)
	data = cur.fetchall()
	result = {}
	for i in data:
		result.update({i[0]: []})
		result[i[0]].append(i[1])
		for map in i[2]:
			result[i[0]].append(map)
	current_app.logger.error(data)
	return jsonify(result)

# if __name__ == '__basic__':
# 	app.run(host='0.0.0.0', port='8015')
