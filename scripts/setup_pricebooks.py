"""Phase 0 setup: products and segment price books.

Reads reference/price_books.yaml, then:
  - activates the Standard Price Book
  - creates/updates the six products
  - creates/activates the SMB, Mid-Market and Enterprise price books
  - upserts a price book entry per product per book (Standard first)

Safe to re-run: records are matched by name / product code and prices updated.
Run:  python scripts/setup_pricebooks.py
"""

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from simple_salesforce import Salesforce

CATALOG = Path(__file__).resolve().parent.parent / "reference" / "price_books.yaml"
STANDARD = "Standard Price Book"


def main() -> int:
    load_dotenv(".env")
    sf = Salesforce(
        username=os.environ["SF_USERNAME"],
        password=os.environ["SF_PASSWORD"],
        security_token=os.environ["SF_SECURITY_TOKEN"],
        domain=os.getenv("SF_DOMAIN", "login"),
    )
    cfg = yaml.safe_load(CATALOG.read_text())

    # 1. Price books (Standard must be active before entries can be used)
    books = {}
    std = sf.query("SELECT Id, IsActive FROM Pricebook2 WHERE IsStandard = true")["records"][0]
    if not std["IsActive"]:
        sf.Pricebook2.update(std["Id"], {"IsActive": True})
    books[STANDARD] = std["Id"]
    print(f"OK    {STANDARD} active")
    for name in cfg["price_books"]:
        if name == STANDARD:
            continue
        found = sf.query("SELECT Id, IsActive FROM Pricebook2 "
                         f"WHERE Name = '{name}' AND IsStandard = false")["records"]
        if found:
            books[name] = found[0]["Id"]
            if not found[0]["IsActive"]:
                sf.Pricebook2.update(books[name], {"IsActive": True})
            print(f"OK    price book {name} (exists, active)")
        else:
            books[name] = sf.Pricebook2.create({
                "Name": name, "IsActive": True,
                "Description": f"List prices for {name} segment deals (Quote Copilot)"})["id"]
            print(f"OK    price book {name} (created, active)")

    # 2. Products
    products = {}
    for p in cfg["products"]:
        data = {"Name": p["name"], "ProductCode": p["code"], "IsActive": True,
                "Description": p["description"], "QuantityUnitOfMeasure": p["unit"]}
        found = sf.query(f"SELECT Id FROM Product2 WHERE ProductCode = '{p['code']}'")["records"]
        if found:
            products[p["name"]] = found[0]["Id"]
            sf.Product2.update(products[p["name"]], data)
            print(f"OK    product {p['name']} (updated)")
        else:
            products[p["name"]] = sf.Product2.create(data)["id"]
            print(f"OK    product {p['name']} (created)")

    # 3. Entries: Standard first (Salesforce requires it), then the segment books
    order = [STANDARD] + [b for b in cfg["price_books"] if b != STANDARD]
    for book in order:
        for product, price in cfg["price_books"][book].items():
            found = sf.query("SELECT Id FROM PricebookEntry WHERE "
                             f"Pricebook2Id = '{books[book]}' AND "
                             f"Product2Id = '{products[product]}'")["records"]
            data = {"UnitPrice": price, "IsActive": True}
            if found:
                sf.PricebookEntry.update(found[0]["Id"], data)
            else:
                sf.PricebookEntry.create({**data, "Pricebook2Id": books[book],
                                          "Product2Id": products[product],
                                          "UseStandardPrice": False})
        print(f"OK    {book}: {len(cfg['price_books'][book])} entries")

    print("\nPhase 0 products and price books: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
