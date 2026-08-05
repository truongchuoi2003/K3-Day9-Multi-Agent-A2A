"""Read-only access to the Olist datasets used by the agent pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd


class DatasetError(RuntimeError):
    """Raised when a required dataset file or column is unavailable."""


class DataLoader:
    """Load Olist tables and provide safe, order-centred query helpers.

    The policy-critical tables are loaded eagerly. Supporting tables are loaded
    on demand to keep startup and memory use reasonable (notably geolocation).
    """

    _FILES: Final[dict[str, str]] = {
        "orders": "olist_orders_dataset.csv",
        "order_items": "olist_order_items_dataset.csv",
        "order_payments": "olist_order_payments_dataset.csv",
        "sellers": "olist_sellers_dataset.csv",
        "customers": "olist_customers_dataset.csv",
        "order_reviews": "olist_order_reviews_dataset.csv",
        "products": "olist_products_dataset.csv",
        "geolocation": "olist_geolocation_dataset.csv",
        "category_translation": "product_category_name_translation.csv",
    }

    _DATE_COLUMNS: Final[dict[str, list[str]]] = {
        "orders": [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        "order_items": ["shipping_limit_date"],
        "order_reviews": ["review_creation_date", "review_answer_timestamp"],
    }

    _REQUIRED_COLUMNS: Final[dict[str, set[str]]] = {
        "orders": {
            "order_id",
            "customer_id",
            "order_status",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        },
        "order_items": {
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        },
        "order_payments": {
            "order_id",
            "payment_sequential",
            "payment_value",
        },
        "sellers": {"seller_id"},
    }

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self._tables: dict[str, pd.DataFrame] = {}

        # These tables directly support EC_POLICY_V1 or seller-ID validation.
        for table_name in ("orders", "order_items", "order_payments", "sellers"):
            self._tables[table_name] = self._read_table(table_name)

    @property
    def orders(self) -> pd.DataFrame:
        return self._tables["orders"]

    @property
    def order_items(self) -> pd.DataFrame:
        return self._tables["order_items"]

    @property
    def order_payments(self) -> pd.DataFrame:
        return self._tables["order_payments"]

    @property
    def sellers(self) -> pd.DataFrame:
        return self._tables["sellers"]

    def load_supporting_table(self, table_name: str) -> pd.DataFrame:
        """Load and cache one non-policy table by its logical table name."""
        if table_name not in self._FILES:
            raise KeyError(f"Unknown table: {table_name}")
        if table_name not in self._tables:
            self._tables[table_name] = self._read_table(table_name)
        return self._tables[table_name]

    def load_all_tables(self) -> None:
        """Load all nine supplied CSV files, including supporting datasets."""
        for table_name in self._FILES:
            self.load_supporting_table(table_name)

    def get_order(self, order_id: str) -> pd.Series:
        """Return the single order row or raise a clear error when absent."""
        rows = self.orders.loc[self.orders["order_id"] == order_id]
        if rows.empty:
            raise KeyError(f"Order not found: {order_id}")
        if len(rows) != 1:
            raise DatasetError(f"Expected one order row for {order_id}, found {len(rows)}")
        return rows.iloc[0].copy()

    def get_order_items(self, order_id: str) -> pd.DataFrame:
        """Return all items for an order, in original item sequence."""
        rows = self.order_items.loc[self.order_items["order_id"] == order_id].copy()
        return rows.sort_values("order_item_id")

    def get_order_payments(self, order_id: str) -> pd.DataFrame:
        """Return all payment rows for an order, in payment sequence."""
        rows = self.order_payments.loc[self.order_payments["order_id"] == order_id].copy()
        return rows.sort_values("payment_sequential")

    def seller_exists(self, seller_id: str) -> bool:
        """Check that a seller ID referenced by an item exists in sellers.csv."""
        return bool((self.sellers["seller_id"] == seller_id).any())

    def get_customer_for_order(self, order_id: str) -> pd.Series | None:
        """Return the related customer row when supporting customer data is needed."""
        order = self.get_order(order_id)
        customers = self.load_supporting_table("customers")
        rows = customers.loc[customers["customer_id"] == order["customer_id"]]
        return None if rows.empty else rows.iloc[0].copy()

    def get_product(self, product_id: str) -> pd.Series | None:
        """Return optional product metadata for future analysis features."""
        products = self.load_supporting_table("products")
        rows = products.loc[products["product_id"] == product_id]
        return None if rows.empty else rows.iloc[0].copy()

    def _read_table(self, table_name: str) -> pd.DataFrame:
        path = self.data_dir / self._FILES[table_name]
        if not path.is_file():
            raise DatasetError(f"Dataset file not found: {path}")

        table = pd.read_csv(path, parse_dates=self._DATE_COLUMNS.get(table_name))
        required_columns = self._REQUIRED_COLUMNS.get(table_name, set())
        missing_columns = required_columns.difference(table.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise DatasetError(f"{path.name} is missing required columns: {missing}")
        return table
