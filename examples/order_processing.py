"""Equivalent conventional Python implementation of the demo behaviour.

This is the *comparison baseline* for benchmarking only — the platform's
primary artifact is the IR in ``order_processing.json``, never this file.
"""

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def process_order(order_id, customer_name, customer_email, items, inventory=None):
    inventory = inventory if inventory is not None else {"SKU-A": 50, "SKU-B": 20, "SKU-C": 5}
    if not customer_name:
        raise ValueError("customer_name is required and must be non-empty.")
    if not _EMAIL_RE.match(customer_email or ""):
        raise ValueError(f"Invalid email address: {customer_email!r}.")
    if not items:
        raise ValueError("items is required and must be non-empty.")
    for item in items:
        if item["sku"] not in inventory:
            raise ValueError(f"Unknown SKU: {item['sku']!r}.")
        if inventory[item["sku"]] < item["qty"]:
            raise ValueError(
                f"Insufficient stock for {item['sku']!r}: need {item['qty']}, have {inventory[item['sku']]}."
            )

    subtotal = sum(i["price"] * i["qty"] for i in items)
    rate = 0.10 if subtotal >= 100 else 0.0
    after = subtotal * (1 - rate)
    shipping = 0.0 if after >= 50 else 9.99
    total = round(after + shipping, 2)
    confirmation = (
        f"Thanks {customer_name}! Order {order_id} confirmed. Total: ${total:.2f}."
    )
    return {"confirmation": confirmation, "total": total, "status": "confirmed"}
