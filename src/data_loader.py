"""Load and query the Olist CSV datasets."""


class DataLoader:
    """Shared read-only access to order, item, seller, and payment data."""

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = data_dir
