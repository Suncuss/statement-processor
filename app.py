#!/usr/bin/env python3
"""
Credit Card Statement Processor - Web Interface
A Streamlit app for processing and categorizing credit card statements.
"""

import os

# Fix for macOS fork crash in multi-threaded Streamlit environment
os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from dotenv import load_dotenv
import tempfile

from parser import CSVSchemaDetector, CSVParser
from categorizer import TransactionCategorizer
from aggregator import TransactionAggregator
from models import Transaction

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Statement Processor",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={}
)

# Clean CSS
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }

    h1 {
        font-weight: 600;
        color: #1A1F24;
        font-size: 1.75rem !important;
        margin-bottom: 1.5rem !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 600 !important;
        color: #333 !important;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        color: #666 !important;
    }

    .stButton>button {
        border-radius: 0.375rem;
    }

    [data-testid="stFileUploader"] {
        border: 1px dashed #ccc;
        border-radius: 0.5rem;
        padding: 1rem;
    }

    hr {
        margin: 2rem 0;
        border-color: #eee;
    }
</style>
""", unsafe_allow_html=True)


def process_uploaded_files(uploaded_files, api_key):
    """Process uploaded CSV files and return transactions"""

    if not uploaded_files:
        return []

    # Create a temporary directory to store uploaded files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Save uploaded files
        for uploaded_file in uploaded_files:
            file_path = temp_path / uploaded_file.name
            with open(file_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())

        # Parse CSV files
        schema_detector = CSVSchemaDetector(api_key)
        parser = CSVParser(schema_detector)
        transactions = parser.parse_all(temp_path)

        # Categorize transactions
        categorizer = TransactionCategorizer(api_key)
        transactions = categorizer.categorize_transactions(transactions)

        return transactions


def transactions_to_dataframe(transactions):
    """Convert transactions to pandas DataFrame"""
    data = []
    for t in transactions:
        data.append({
            'Date': t.date.strftime('%Y-%m-%d'),
            'Card': t.card_provider,
            'Description': t.description,
            'Amount': t.amount,
            'Category': t.category or 'Uncategorized'
        })
    return pd.DataFrame(data)


def main():
    # Check for API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        st.error("ANTHROPIC_API_KEY not found in .env file")
        st.stop()

    # Show upload area only if no data processed yet
    if 'transactions' not in st.session_state or not st.session_state['transactions']:
        st.title("Statement Processor")

        uploaded_files = st.file_uploader(
            "Upload credit card statements",
            type=['csv', 'CSV'],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )

        if uploaded_files:
            process_button = st.button("Process Files", type="primary")
        else:
            process_button = False
    else:
        # Minimal header when viewing results
        col_title, col_reset = st.columns([4, 1])
        with col_title:
            st.title("Statement Processor")
        with col_reset:
            if st.button("Upload New"):
                st.session_state.clear()
                st.rerun()

        uploaded_files = None
        process_button = False

    # Main content
    if uploaded_files and process_button:
        with st.spinner('🤖 Processing statements with AI...'):
            # Process files
            transactions = process_uploaded_files(uploaded_files, api_key)

        # Check results after spinner completes
        if not transactions:
            st.warning("No transactions found in the uploaded files.")
            st.stop()

        # Store in session state
        st.session_state['transactions'] = transactions
        st.session_state['df'] = transactions_to_dataframe(transactions)

    # Display results if we have processed transactions
    if 'transactions' in st.session_state and st.session_state['transactions']:
        transactions = st.session_state['transactions']
        df = st.session_state['df']

        # Separate spending from payments
        spending_df = df[df['Category'] != 'Payment/Credit']
        payment_df = df[df['Category'] == 'Payment/Credit']

        # Simple summary at top
        total_amount = spending_df['Amount'].sum()
        total_transactions = len(spending_df)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Spending", f"${abs(total_amount):,.2f}")
        with col2:
            st.metric("Transactions", f"{total_transactions} spending")

        st.divider()
        
        # Tabs for cleaner layout
        tab1, tab2 = st.tabs(["Overview", "Transactions"])
        
        # TAB 1: OVERVIEW
        with tab1:
            # Spend by Card Section
            st.subheader("Spend by Card")
            card_totals = spending_df.groupby('Card')['Amount'].sum().sort_values(ascending=True)
            
            # Dynamic Grid for cards
            if not card_totals.empty:
                cards = list(card_totals.items())
                for i in range(0, len(cards), 4):
                    row_cards = cards[i:i+4]
                    cols = st.columns(4)
                    for j, (card, amount) in enumerate(row_cards):
                        with cols[j]:
                            st.metric(card, f"${abs(amount):,.2f}")

            st.divider()

            # By Category Section
            st.subheader("By Category")

            category_totals = spending_df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
            category_counts = spending_df.groupby('Category').size()

            # Two columns: chart and table
            col_chart, col_table = st.columns([2, 1])

            with col_chart:
                # Create dataframe for chart (sorted ascending for horizontal bar)
                chart_df = pd.DataFrame({
                    'Category': category_totals.index[::-1],
                    'Amount': abs(category_totals.values[::-1])
                })

                # Create horizontal bar chart with values displayed
                fig = px.bar(
                    chart_df,
                    x='Amount',
                    y='Category',
                    orientation='h',
                    text=chart_df['Amount'].apply(lambda x: f'${x:,.0f}'),
                    color='Amount',
                    color_continuous_scale=['#e8f4f8', '#1e88e5']
                )

                fig.update_traces(
                    textposition='outside',
                    textfont_size=12,
                    marker_line_width=0
                )

                fig.update_layout(
                    showlegend=False,
                    coloraxis_showscale=False,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    margin=dict(l=0, r=80, t=20, b=20),
                    height=max(300, len(category_totals) * 45),
                    xaxis=dict(
                        showgrid=True,
                        gridcolor='#f0f0f0',
                        tickformat='$,.0f',
                        title=''
                    ),
                    yaxis=dict(
                        title='',
                        tickfont=dict(size=13)
                    )
                )

                st.plotly_chart(fig, width='stretch')

            with col_table:
                # Create summary table
                summary_df = pd.DataFrame({
                    'Category': category_totals.index,
                    'Amount': category_totals.values,
                    'Count': [category_counts.get(cat, 0) for cat in category_totals.index]
                })

                st.dataframe(
                    summary_df,
                    width='stretch',
                    hide_index=True,
                    height=max(300, len(category_totals) * 45),
                    column_config={
                        "Amount": st.column_config.NumberColumn(
                            "Amount",
                            format="$%.2f"
                        ),
                        "Count": st.column_config.NumberColumn(
                            "Txns",
                            format="%d"
                        )
                    }
                )

        # TAB 2: TRANSACTIONS
        with tab2:
            st.subheader("All Transactions")

            # Filters in a single row
            filter_col1, filter_col2, _ = st.columns([1, 1, 2])
            
            with filter_col1:
                selected_category = st.selectbox(
                    "Category",
                    options=['All'] + sorted(spending_df['Category'].unique().tolist())
                )

            with filter_col2:
                selected_card = st.selectbox(
                    "Card",
                    options=['All'] + sorted(spending_df['Card'].unique().tolist())
                )

            # Apply filters
            filtered_df = spending_df.copy()
            
            if selected_category != 'All':
                filtered_df = filtered_df[filtered_df['Category'] == selected_category]
                
            if selected_card != 'All':
                filtered_df = filtered_df[filtered_df['Card'] == selected_card]

            # Sort by date (most recent first)
            filtered_df = filtered_df.sort_values('Date', ascending=False)

            # Format amounts for display
            display_df = filtered_df[['Date', 'Card', 'Description', 'Amount', 'Category']].copy()

            st.dataframe(
                display_df,
                width='stretch',
                hide_index=True,
                height=600,
                column_config={
                    "Amount": st.column_config.NumberColumn(
                        "Amount",
                        format="$%.2f"
                    ),
                    "Date": st.column_config.DateColumn(
                        "Date",
                        format="YYYY-MM-DD"
                    )
                }
            )




if __name__ == "__main__":
    main()
