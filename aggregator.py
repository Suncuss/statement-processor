from typing import List, Dict
from collections import defaultdict
from models import Transaction


class TransactionAggregator:
    """Aggregate and summarize transactions"""

    @staticmethod
    def filter_spending_only(transactions: List[Transaction]) -> List[Transaction]:
        """Filter out Payment/Credit transactions to get actual spending"""
        return [t for t in transactions if t.category != "Payment/Credit"]

    @staticmethod
    def aggregate_by_category(transactions: List[Transaction], exclude_payments: bool = True) -> Dict[str, float]:
        """Calculate total spending per category"""
        totals = defaultdict(float)

        if exclude_payments:
            transactions = TransactionAggregator.filter_spending_only(transactions)

        for transaction in transactions:
            category = transaction.category or "Uncategorized"
            totals[category] += transaction.amount

        return dict(totals)

    @staticmethod
    def aggregate_by_card(transactions: List[Transaction], exclude_payments: bool = True) -> Dict[str, float]:
        """Calculate total spending per card"""
        totals = defaultdict(float)

        if exclude_payments:
            transactions = TransactionAggregator.filter_spending_only(transactions)

        for transaction in transactions:
            totals[transaction.card_provider] += transaction.amount

        return dict(totals)

    @staticmethod
    def print_summary(transactions: List[Transaction]):
        """Print a detailed summary of all transactions"""

        print("\n" + "=" * 120)
        print("TRANSACTION SUMMARY")
        print("=" * 120)

        # Separate spending from payments
        spending_transactions = TransactionAggregator.filter_spending_only(transactions)
        payment_transactions = [t for t in transactions if t.category == "Payment/Credit"]

        # Overall stats
        total_transactions = len(spending_transactions)
        total_spending = sum(t.amount for t in spending_transactions)
        total_payments = sum(t.amount for t in payment_transactions)

        print(f"\nSpending Transactions: {total_transactions}")
        print(f"Total Spending: ${abs(total_spending):,.2f}")
        if payment_transactions:
            print(f"Payments/Credits: ${abs(total_payments):,.2f} ({len(payment_transactions)} transactions)")

        # By category
        category_totals = TransactionAggregator.aggregate_by_category(transactions)
        print("\n" + "-" * 120)
        print("BY CATEGORY:")
        print("-" * 120)

        for category, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            percentage = (total / total_spending * 100) if total_spending != 0 else 0
            print(f"{category:25} ${total:10.2f} ({percentage:5.1f}%)")

        # By card
        card_totals = TransactionAggregator.aggregate_by_card(transactions)
        print("\n" + "-" * 120)
        print("BY CARD:")
        print("-" * 120)

        for card, total in sorted(card_totals.items()):
            percentage = (total / total_spending * 100) if total_spending != 0 else 0
            print(f"{card:25} ${total:10.2f} ({percentage:5.1f}%)")

        print("\n" + "=" * 120)

    @staticmethod
    def print_detailed_transactions(transactions: List[Transaction], category_filter: str = None):
        """Print detailed transaction list, optionally filtered by category"""

        filtered = transactions
        if category_filter:
            filtered = [t for t in transactions if t.category == category_filter]

        print("\n" + "=" * 120)
        if category_filter:
            print(f"TRANSACTIONS - {category_filter}")
        else:
            print("ALL TRANSACTIONS")
        print("=" * 120)
        print(f"{'Date':<12} {'Card':<6} {'Amount':>10} {'Description':<45} {'Category':<20}")
        print("-" * 120)

        for t in filtered:
            print(t)

        print("-" * 120)
        print(f"Total: ${sum(t.amount for t in filtered):,.2f} ({len(filtered)} transactions)")
        print("=" * 120)
