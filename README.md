# Credit Card Statement Processor

Process and categorize credit card statements from multiple providers using Claude AI.

## Features

- **Universal CSV Support**: Works with ANY credit card provider - LLM auto-detects CSV format
- **AI-powered categorization**: Uses Claude Haiku to intelligently categorize transactions
- **Smart caching**: Remembers both CSV schemas and merchant categorizations to reduce API calls
- **Web Interface**: Beautiful drag-and-drop interface with interactive charts
- **CLI Interface**: Command-line tool for batch processing
- **Consolidated reporting**: Combines transactions from all cards with category and card breakdowns

## Setup

### Option 1: Docker (Recommended)

```bash
# Set your API key
export ANTHROPIC_API_KEY=your_key_here

# Run with docker-compose
docker-compose up --build
```

Then open http://localhost:8501

### Option 2: Local Python

1. Install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Create `.env` with your API key:
```
ANTHROPIC_API_KEY=your_key_here
```

3. Run the app:
```bash
streamlit run app.py
```

Then open http://localhost:8501

Features:
- 📁 Drag and drop CSV files
- 📊 Interactive pie charts and visualizations
- 🔍 Filter transactions by category or card
- 📥 Download categorized results as CSV
- 💡 See how each transaction was categorized

### Command Line Interface

For batch processing, place CSV files in the `data/` folder and run:
```bash
source venv/bin/activate
python main.py
```

The program will:
1. Auto-detect CSV format for each file
2. Categorize transactions using Claude AI (cached results are reused)
3. Display a summary by category and card
4. Optionally show detailed transaction lists

## Categories

- Food/Restaurant
- Grocery
- Transportation
- Subscriptions
- Utilities
- Shopping
- Healthcare
- Entertainment
- Payment/Credit (automatically excluded from spending totals)
- Other

## How It Works

1. **CSV Schema Detection**: Claude analyzes the first few rows and automatically identifies:
   - Whether there's a header row
   - Which columns contain date, merchant, and amount
   - The date format
   - The card provider

2. **Smart Categorization**: Claude categorizes each transaction based on merchant name context

3. **Caching**: Both schemas and categorizations are cached to minimize API costs

## Project Structure

```
statement_processor/
├── data/                          # Place CSV files here (for CLI mode)
├── cache/
│   ├── schema_cache.json         # Cached CSV schemas
│   └── merchant_cache.json       # Cached categorizations
├── models.py                      # Transaction data model
├── parser.py                      # LLM-powered universal CSV parser
├── categorizer.py                 # Claude AI categorization with caching
├── aggregator.py                  # Report generation
├── app.py                         # Streamlit web interface
└── main.py                        # CLI interface
```

## Customization

- **Categories**: Edit `categorizer.py:15` to add/modify categories
- **Cache logic**: Modify `categorizer.py:42` for better merchant matching
- **UI styling**: Customize `app.py` for different layouts or themes
# statement-processor
