"""Fetch public AWS S3 price-list evidence; no credentials or AWS SDK."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import urllib.request

URL = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-1/index.json"
OUT = Path(__file__).resolve().parents[1] / "evidence"


def main() -> None:
    with urllib.request.urlopen(URL, timeout=60) as response:
        offer = json.load(response)
    items = []
    for sku, product in offer["products"].items():
        attrs = product["attributes"]
        if attrs.get("regionCode") != "us-east-1":
            continue
        standard_storage = product.get("productFamily") == "Storage" and attrs.get("volumeType") == "Standard"
        standard_requests = product.get("productFamily") == "API Request" and attrs.get("usagetype") in ("Requests-Tier1", "Requests-Tier2")
        if not (standard_storage or standard_requests):
            continue
        for term in offer["terms"]["OnDemand"].get(sku, {}).values():
            for dimension in term["priceDimensions"].values():
                items.append({"sku": sku, "attributes": attrs, "effective_date": term["effectiveDate"], **dimension})
    assert items, "No matching current S3 price dimensions"
    OUT.mkdir(parents=True, exist_ok=True)
    output = {"source_url": URL, "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "offer_publication_date": offer["publicationDate"], "offer_version": offer["version"], "price_dimensions": items}
    (OUT / "aws-s3-price-evidence.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
