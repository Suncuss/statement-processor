#!/usr/bin/env python3
"""
Credit Card Statement Processor
Processes credit card statements from multiple providers and categorizes expenses using Claude AI.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from parser import CSVParser, CSVSchemaDetector
from categorizer import TransactionCategorizer
from aggregator import TransactionAggregator


def main():
    # Load environment variables
    load_dotenv()

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file")
        sys.exit(1)

    # Configuration
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"Error: Data directory '{data_dir}' not found")
        sys.exit(1)

    print("=" * 120)
    print("CREDIT CARD STATEMENT PROCESSOR")
    print("=" * 120)

    # Step 1: Parse all CSV files using LLM-powered schema detection
    print("\n[1/3] Parsing CSV files with LLM-powered schema detection...")
    schema_detector = CSVSchemaDetector(api_key)
    parser = CSVParser(schema_detector)
    transactions = parser.parse_all(data_dir)
    print(f"Total transactions loaded: {len(transactions)}")

    # Step 2: Categorize transactions
    print("\n[2/3] Categorizing transactions with Claude AI...")
    categorizer = TransactionCategorizer(api_key)
    transactions = categorizer.categorize_transactions(transactions)

    # Step 3: Generate reports
    print("\n[3/3] Generating reports...")

    # Print summary
    TransactionAggregator.print_summary(transactions)

    # Optional: print detailed view
    print("\n")
    choice = input("Show detailed transaction list? (y/n): ").strip().lower()
    if choice == 'y':
        TransactionAggregator.print_detailed_transactions(transactions)

    # Optional: filter by category
    print("\n")
    choice = input("Filter by category? Enter category name or press Enter to skip: ").strip()
    if choice:
        TransactionAggregator.print_detailed_transactions(transactions, category_filter=choice)

    print("\nDone! Categorization cache saved for future runs.")


if __name__ == "__main__":
    main()
