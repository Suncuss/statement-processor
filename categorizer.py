import json
import os
from pathlib import Path
from typing import List, Dict
from anthropic import Anthropic
from models import Transaction


class TransactionCategorizer:
    """Categorize transactions using Claude API with caching"""

    CATEGORIES = [
        "Food/Restaurant",
        "Grocery",
        "Transportation",
        "Subscriptions",
        "Utilities",
        "Shopping",
        "Healthcare",
        "Entertainment",
        "Rent/Housing",
        "Payment/Credit",
        "Other"
    ]

    def __init__(self, api_key: str, cache_file: Path = Path("cache/merchant_cache.json")):
        self.client = Anthropic(api_key=api_key)
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        """Load merchant -> category cache from file"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        """Save cache to file"""
        self.cache_file.parent.mkdir(exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def _get_cache_key(self, description: str) -> str:
        """Extract merchant name for caching (remove location info, etc.)"""
        # Simple heuristic: take first meaningful part before location codes
        # You can make this more sophisticated
        parts = description.upper().split()
        # Keep first 3-4 words as merchant identifier
        return ' '.join(parts[:min(4, len(parts))])

    def _categorize_batch_with_llm(self, transactions: List[Transaction]) -> Dict[str, str]:
        """Send batch of transactions to Claude for categorization"""

        # Prepare the transaction list for the prompt
        transaction_list = "\n".join([
            f"{i+1}. {t.description}"
            for i, t in enumerate(transactions)
        ])

        prompt = f"""Categorize these credit card transactions into one of these categories:
{', '.join(self.CATEGORIES)}

Transactions:
{transaction_list}

Return ONLY a JSON object mapping transaction number to category. Example:
{{"1": "Grocery", "2": "Food/Restaurant", "3": "Transportation"}}

Be specific:
- Trader Joe's, Whole Foods, Wegmans, Harris Teeter, Costco = Grocery
- Restaurants, cafes, food delivery = Food/Restaurant
- Gas, parking, ChargePoint, Uber, Lyft, tolls = Transportation
- Netflix, ChatGPT, GitHub, Adobe, etc. = Subscriptions
- GEICO, Spectrum, internet, phone bills = Utilities
- Medical, dental = Healthcare
- Amazon, IKEA (furniture), general shopping = Shopping
- BILT RENT, rent payments, apartment/housing payments = Rent/Housing
- AUTOPAY, PAYMENT, AUTOMATIC PAYMENT (payments TO the card company) = Payment/Credit

IMPORTANT:
- Payment/Credit is ONLY for payments you make TO the credit card company (like AUTOPAY PAYMENT)
- RENT PAYMENTS (like "BILT RENT", "BPS*BILT RENT") are Rent/Housing, NOT Payment/Credit
- Card benefits/rewards (like "AMEX Dining Credit", "AMEX Dunkin' Credit") should be categorized by what they offset (e.g., dining credits = Food/Restaurant)
- This way, category totals show your net spending after rewards

Response (JSON only):"""

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse the response
        try:
            result_text = response.content[0].text.strip()
            # Remove markdown code blocks if present
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]

            categorizations = json.loads(result_text)

            # Convert number keys to descriptions
            result = {}
            for i, transaction in enumerate(transactions):
                key = str(i + 1)
                if key in categorizations:
                    result[transaction.description] = categorizations[key]

            return result
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Error parsing LLM response: {e}")
            print(f"Response was: {response.content[0].text}")
            return {}

    def categorize_transactions(self, transactions: List[Transaction], batch_size: int = 20) -> List[Transaction]:
        """Categorize all transactions, using cache when possible"""

        uncategorized = []

        # First pass: check cache
        for transaction in transactions:
            cache_key = self._get_cache_key(transaction.description)
            if cache_key in self.cache:
                transaction.category = self.cache[cache_key]
            else:
                uncategorized.append(transaction)

        print(f"Found {len(transactions) - len(uncategorized)} cached, need to categorize {len(uncategorized)}")

        # Second pass: categorize uncached in batches
        for i in range(0, len(uncategorized), batch_size):
            batch = uncategorized[i:i + batch_size]
            print(f"Categorizing batch {i//batch_size + 1} ({len(batch)} transactions)...")

            categorizations = self._categorize_batch_with_llm(batch)

            # Apply categorizations and update cache
            for transaction in batch:
                if transaction.description in categorizations:
                    category = categorizations[transaction.description]
                    transaction.category = category

                    # Update cache
                    cache_key = self._get_cache_key(transaction.description)
                    self.cache[cache_key] = category
                else:
                    transaction.category = "Other"

        # Save updated cache
        self._save_cache()

        return transactions
