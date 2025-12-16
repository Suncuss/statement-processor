import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from anthropic import Anthropic
from models import Transaction


class CSVSchemaDetector:
    """Uses Claude to automatically detect CSV schema"""

    def __init__(self, api_key: str, cache_file: Path = Path("cache/schema_cache.json")):
        self.client = Anthropic(api_key=api_key)
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load schema cache from file"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        """Save cache to file"""
        self.cache_file.parent.mkdir(exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def _get_cache_key(self, file_path: Path) -> str:
        """Generate cache key based on file name pattern.

        Extracts a provider identifier by removing date-like parts from filename.
        E.g., 'VenmoStatement_December_2025.csv' -> 'VENMOSTATEMENT'
              'activity_AMEX_NOV.csv' -> 'ACTIVITY_AMEX'
        """
        import re
        name = file_path.stem.upper()

        # Remove common date patterns (months, years, dates)
        months = r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)'
        name = re.sub(months, '', name)
        name = re.sub(r'20\d{2}', '', name)  # Remove years like 2024, 2025
        name = re.sub(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', '', name)  # Remove dates
        name = re.sub(r'[_\-]+', '_', name)  # Normalize separators
        name = name.strip('_')  # Remove leading/trailing underscores

        return name if name else file_path.stem.upper()

    def detect_schema(self, file_path: Path, sample_rows: int = 10) -> Dict:
        """Detect CSV schema using Claude API"""

        # Check cache first
        cache_key = self._get_cache_key(file_path)
        if cache_key in self.cache:
            print(f"  Using cached schema for {cache_key}")
            return self.cache[cache_key]

        # Read sample rows
        with open(file_path, 'r') as f:
            content = []
            for i, line in enumerate(f):
                if i >= sample_rows + 1:  # +1 for potential header
                    break
                content.append(line.strip())

        csv_sample = '\n'.join(content)

        # Define the tool for structured output
        tools = [{
            "name": "identify_csv_schema",
            "description": "Identify the schema of a credit card or payment CSV file by specifying which columns contain date, merchant description, and amount information",
            "input_schema": {
                "type": "object",
                "properties": {
                    "has_header": {
                        "type": "boolean",
                        "description": "Whether the CSV has a header row with column names"
                    },
                    "skip_rows": {
                        "type": "integer",
                        "description": "Number of metadata/title rows to skip before the header row (0 if header is on first line)"
                    },
                    "date_column": {
                        "type": "string",
                        "description": "Column name (if header exists) or column index (0-based, e.g., '0', '1') for the transaction date"
                    },
                    "description_column": {
                        "type": "string",
                        "description": "Column name or index for the merchant/transaction description or note"
                    },
                    "amount_column": {
                        "type": "string",
                        "description": "Column name or index for the transaction amount"
                    },
                    "date_format": {
                        "type": "string",
                        "description": "The date format string (e.g., '%m/%d/%Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S')"
                    },
                    "card_provider": {
                        "type": "string",
                        "description": "The card/payment provider name extracted from filename or content (e.g., 'AMEX', 'CHASE', 'VENMO', 'PAYPAL')"
                    },
                    "spending_is_negative": {
                        "type": "boolean",
                        "description": "Look at the MAJORITY of regular purchase transactions (restaurants, stores, subscriptions). True if these purchases are NEGATIVE (like -50.00 or '- $50'), False if purchases are POSITIVE (like 50.00 or '$50'). Ignore credits/refunds which are the opposite sign."
                    }
                },
                "required": ["has_header", "skip_rows", "date_column", "description_column", "amount_column", "date_format", "card_provider", "spending_is_negative"]
            }
        }]

        prompt = f"""Analyze this credit card or payment service CSV file sample and identify the schema.

Filename: {file_path.name}

CSV Sample:
{csv_sample}

Identify:
1. Does it have a header row with column names?
2. How many rows need to be skipped before the header? (e.g., if there are title/metadata rows before the actual column headers, count them)
3. Which column contains the transaction date?
4. Which column contains the merchant/description/note?
5. Which column contains the amount?
6. What is the date format? (Python strptime format, e.g., '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S')
7. What provider is this? (look at filename: AMEX, CHASE, BILT, VENMO, PAYPAL, etc.)
8. IMPORTANT - Look at the REGULAR PURCHASES (restaurants, stores, subscriptions - NOT credits/refunds):
   - If most purchases show as POSITIVE numbers (like 19.99 or $50.00), then spending_is_negative=False
   - If most purchases show as NEGATIVE numbers (like -19.99 or -$50.00), then spending_is_negative=True

Use the identify_csv_schema tool to provide this information."""

        response = self.client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            tools=tools,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Extract tool use from response
        for block in response.content:
            if block.type == "tool_use" and block.name == "identify_csv_schema":
                schema = block.input

                # Cache the schema
                self.cache[cache_key] = schema
                self._save_cache()

                print(f"  Detected schema for {cache_key}: {schema}")
                return schema

        raise ValueError("Failed to detect CSV schema")


class CSVParser:
    """Universal CSV parser using LLM-detected schema"""

    def __init__(self, schema_detector: CSVSchemaDetector):
        self.schema_detector = schema_detector

    @staticmethod
    def parse_amount(amount_str: str) -> float:
        """
        Parse amount string that may contain +/-, $, commas, etc.
        Examples: "- $59.27", "+ $66.00", "$1,590.10", "-45.00"
        """
        # Remove whitespace
        amount_str = amount_str.strip()

        # Check for negative sign (could be at start or after currency symbol)
        is_negative = '-' in amount_str
        is_positive = '+' in amount_str

        # Remove currency symbols, +/-, commas, and spaces
        cleaned = amount_str.replace('$', '').replace(',', '').replace('+', '').replace('-', '').strip()

        if not cleaned:
            raise ValueError(f"Empty amount after cleaning: {amount_str}")

        amount = float(cleaned)

        # Apply sign
        if is_negative:
            amount = -amount

        return amount

    @staticmethod
    def normalize_amount(amount: float, spending_is_negative: bool) -> float:
        """
        Normalize transaction amounts to a consistent convention:
        - Spending should be POSITIVE
        - Credits/Payments/Refunds should be NEGATIVE

        Args:
            amount: The parsed amount (may be positive or negative)
            spending_is_negative: True if the source shows spending as negative numbers
        """
        if spending_is_negative:
            # Flip the sign: spending was negative, we want it positive
            return -amount
        else:
            # Already in correct convention
            return amount

    def parse_file(self, file_path: Path) -> List[Transaction]:
        """Parse CSV file using auto-detected schema"""

        print(f"Parsing {file_path.name}...")

        # Detect schema
        schema = self.schema_detector.detect_schema(file_path)

        transactions = []

        with open(file_path, 'r') as f:
            # Skip metadata rows if specified
            skip_rows = schema.get('skip_rows', 0)
            for _ in range(skip_rows):
                next(f)

            if schema['has_header']:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        date_str = row[schema['date_column']].strip()
                        description = row[schema['description_column']].strip()
                        amount_str = row[schema['amount_column']].strip()

                        # Skip rows with empty essential fields
                        if not date_str or not amount_str:
                            continue

                        date = datetime.strptime(date_str, schema['date_format'])
                        raw_amount = self.parse_amount(amount_str)

                        # Normalize amount to consistent convention
                        amount = self.normalize_amount(raw_amount, schema.get('spending_is_negative', True))

                        transactions.append(Transaction(
                            date=date,
                            description=description,
                            amount=amount,
                            card_provider=schema['card_provider']
                        ))
                    except (ValueError, KeyError) as e:
                        # Silently skip invalid rows (headers, footers, etc.)
                        pass
            else:
                reader = csv.reader(f)
                for row in reader:
                    try:
                        if len(row) == 0:
                            continue

                        date_idx = int(schema['date_column'])
                        desc_idx = int(schema['description_column'])
                        amount_idx = int(schema['amount_column'])

                        date_str = row[date_idx].strip()
                        description = row[desc_idx].strip()
                        amount_str = row[amount_idx].strip()

                        # Skip rows with empty essential fields
                        if not date_str or not amount_str:
                            continue

                        date = datetime.strptime(date_str, schema['date_format'])
                        raw_amount = self.parse_amount(amount_str)

                        # Normalize amount to consistent convention
                        amount = self.normalize_amount(raw_amount, schema.get('spending_is_negative', True))

                        transactions.append(Transaction(
                            date=date,
                            description=description,
                            amount=amount,
                            card_provider=schema['card_provider']
                        ))
                    except (ValueError, IndexError) as e:
                        print(f"  Warning: Skipping invalid row: {row} - {e}")

        print(f"  Found {len(transactions)} transactions")
        return transactions

    def parse_all(self, data_dir: Path) -> List[Transaction]:
        """Parse all CSV files in the data directory"""
        all_transactions = []

        csv_files = list(data_dir.glob('*.csv')) + list(data_dir.glob('*.CSV'))

        for csv_file in csv_files:
            transactions = self.parse_file(csv_file)
            all_transactions.extend(transactions)

        # Sort by date
        all_transactions.sort(key=lambda t: t.date)
        return all_transactions
