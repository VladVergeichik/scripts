import time
import multiprocessing
import compute_order_marginality
import shipstation_amazon_canada
import shipstation
import shipstation_dropship
import shipstation_prime
import shipstation_ebay
import shipstation_shopify
import shipstation_walmart
import sys
import update_qty
from send_email_order import send_email

start_time = time.time()
try:
	shipstation_prime.main()
except:
	send_email('Error in shipstation prime ' + str(sys.exc_info()[0]))
try:
	shipstation_walmart.main()
except:
	send_email('Error in shipstation walmart' + str(sys.exc_info()[0]))
try:
	shipstation.main()
except:
	send_email('Error in shipstation amazon' + str(sys.exc_info()[0]))
try:
	shipstation_ebay.main()
except:
	send_email('Error in shipstation ebay' + str(sys.exc_info()[0]))
try:
	shipstation_shopify.main()
except:
	send_email('Error in shipstation shopify' + str(sys.exc_info()[0]))
try:
	shipstation_dropship.main()
except:
	send_email('Error in shipstation dropship' + str(sys.exc_info()[0]))
try:
	shipstation_amazon_canada.main()
except:
	send_email('Error in shipstation amazon canada' + str(sys.exc_info()[0]))
try:
	compute_order_marginality.main()
except:
	send_email('Error in marginality' + str(sys.exc_info()[0]))
marketplace_list = ['amazon', 'ebay', 'shopify', 'walmart', 'amazon_canada']
try:
	for marketplace in marketplace_list:
		p = multiprocessing.Process(target=update_qty.main, args=(marketplace,))
		p.start()
	p.join()
except:
	send_email('Error in update qty' + str(sys.exc_info()[0]))
print("--- %s seconds ---" % (time.time() - start_time))

