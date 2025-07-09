import frappe

def execute():
	try:
		# Update cumulative_revenue (uncancelled orders)
		frappe.db.sql("""
			UPDATE `tabCustomer` AS c
			JOIN (
				SELECT customer, SUM(grand_total) AS cumulative_revenue
				FROM `tabSales Order`
				WHERE cancelled_status = 'Uncancelled'
				GROUP BY customer
			) AS so ON c.name = so.customer
			SET c.cumulative_revenue = so.cumulative_revenue
		""")

		# Update true_cumulative_revenue (uncancelled, paid, fulfilled)
		frappe.db.sql("""
			UPDATE `tabCustomer` AS c
			JOIN (
				SELECT customer, SUM(grand_total) AS true_cumulative_revenue
				FROM `tabSales Order`
				WHERE cancelled_status = 'Uncancelled'
				AND financial_status = 'Paid'
				AND fulfillment_status = 'Fulfilled'
				GROUP BY customer
			) AS so ON c.name = so.customer
			SET c.true_cumulative_revenue = so.true_cumulative_revenue
		""")

		frappe.db.commit()

	except Exception as e:
		frappe.db.rollback()
