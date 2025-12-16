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
import plotly.graph_objects as go
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

# Modern CSS styling
st.markdown("""
<style>
    /* Main container */
    .block-container {
        padding: 2rem 3rem;
        max-width: 1200px;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Title styling */
    h1 {
        font-weight: 700;
        color: #1a1a2e;
        font-size: 2rem !important;
        margin-bottom: 0.5rem !important;
        letter-spacing: -0.5px;
    }

    h2, h3, .stSubheader {
        color: #1a1a2e;
        font-weight: 600;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem 1.25rem;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.25);
    }

    [data-testid="stMetricValue"] {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        color: white !important;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
        color: rgba(255,255,255,0.85) !important;
        font-weight: 500;
    }

    /* Card metrics - alternate colors */
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stMetric"] {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        box-shadow: 0 4px 15px rgba(17, 153, 142, 0.25);
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f8f9fa;
        padding: 0.5rem;
        border-radius: 10px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background-color: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        border: 2px dashed #dee2e6;
        border-radius: 12px;
        padding: 2rem;
        background: #f8f9fa;
    }

    [data-testid="stFileUploader"]:hover {
        border-color: #667eea;
        background: #f0f4ff;
    }

    /* Selectbox */
    .stSelectbox > div > div {
        border-radius: 8px;
    }

    /* Divider */
    hr {
        margin: 1.5rem 0;
        border: none;
        border-top: 1px solid #e9ecef;
    }

    /* Dataframe */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }

    /* Card breakdown section */
    .card-metric {
        background: white;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
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

    # Initialize session state for filters
    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = 'All'
    if 'selected_card' not in st.session_state:
        st.session_state.selected_card = 'All'

    # Show upload area only if no data processed yet
    if 'transactions' not in st.session_state or not st.session_state['transactions']:
        st.title("Statement Processor")
        st.caption("Upload your credit card statements and let AI categorize your spending")

        st.write("")  # Spacing

        uploaded_files = st.file_uploader(
            "Drop CSV files here or click to browse",
            type=['csv', 'CSV'],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )

        if uploaded_files:
            st.success(f"{len(uploaded_files)} file(s) selected")
            process_button = st.button("Process Files", type="primary", use_container_width=True)
        else:
            process_button = False
    else:
        # Minimal header when viewing results
        col_title, col_reset = st.columns([5, 1])
        with col_title:
            st.title("Statement Processor")
        with col_reset:
            if st.button("New Upload", type="secondary"):
                st.session_state.clear()
                st.rerun()

        uploaded_files = None
        process_button = False

    # Main content
    if uploaded_files and process_button:
        with st.spinner('Processing statements with AI...'):
            # Process files
            transactions = process_uploaded_files(uploaded_files, api_key)

        # Check results after spinner completes
        if not transactions:
            st.warning("No transactions found in the uploaded files.")
            st.stop()

        # Store in session state
        st.session_state['transactions'] = transactions
        st.session_state['df'] = transactions_to_dataframe(transactions)
        st.rerun()

    # Display results if we have processed transactions
    if 'transactions' in st.session_state and st.session_state['transactions']:
        transactions = st.session_state['transactions']
        df = st.session_state['df']

        # Separate spending from payments
        spending_df = df[df['Category'] != 'Payment/Credit']
        payment_df = df[df['Category'] == 'Payment/Credit']

        # Summary metrics at top
        total_amount = spending_df['Amount'].sum()
        total_transactions = len(spending_df)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Spending", f"${total_amount:,.2f}")
        with col2:
            st.metric("Transactions", f"{total_transactions}")
        with col3:
            avg_transaction = total_amount / total_transactions if total_transactions > 0 else 0
            st.metric("Avg Transaction", f"${avg_transaction:,.2f}")

        st.write("")  # Spacing

        # Tabs for cleaner layout
        tab1, tab2 = st.tabs(["Overview", "Transactions"])

        # TAB 1: OVERVIEW
        with tab1:
            # Spend by Card Section
            st.subheader("Spend by Card")
            card_totals = spending_df.groupby('Card')['Amount'].sum().sort_values(ascending=False)

            if not card_totals.empty:
                cols = st.columns(len(card_totals))
                for idx, (card, amount) in enumerate(card_totals.items()):
                    with cols[idx]:
                        pct = (amount / total_amount * 100) if total_amount > 0 else 0
                        st.markdown(f"""
                        <div style="background: white; border: 1px solid #e9ecef; border-radius: 12px; padding: 1.25rem; text-align: center;">
                            <div style="font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;">{card}</div>
                            <div style="font-size: 1.5rem; font-weight: 700; color: #1a1a2e;">${amount:,.0f}</div>
                            <div style="font-size: 0.8rem; color: #6c757d;">{pct:.1f}%</div>
                        </div>
                        """, unsafe_allow_html=True)

            st.write("")  # Spacing

            # By Category Section
            col_header, col_toggle = st.columns([3, 1])
            with col_header:
                st.subheader("Spending by Category")
            with col_toggle:
                chart_type = st.radio(
                    "Chart type",
                    options=["Bar", "Pie"],
                    horizontal=True,
                    label_visibility="collapsed"
                )

            category_totals = spending_df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
            category_counts = spending_df.groupby('Category').size()

            # Two columns: chart and table
            col_chart, col_table = st.columns([2, 1])

            with col_chart:
                if chart_type == "Bar":
                    # Create dataframe for chart (sorted ascending for horizontal bar)
                    chart_df = pd.DataFrame({
                        'Category': category_totals.index[::-1],
                        'Amount': category_totals.values[::-1]
                    })

                    # Color scale based on amount
                    colors = px.colors.sample_colorscale(
                        'Blues',
                        [i / (len(chart_df) - 1) if len(chart_df) > 1 else 0.5 for i in range(len(chart_df))]
                    )

                    fig = go.Figure(go.Bar(
                        x=chart_df['Amount'],
                        y=chart_df['Category'],
                        orientation='h',
                        text=[f'${x:,.0f}' for x in chart_df['Amount']],
                        textposition='outside',
                        marker=dict(
                            color=colors,
                            cornerradius=6
                        ),
                        textfont=dict(size=12, color='#495057')
                    ))

                    fig.update_layout(
                        showlegend=False,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        margin=dict(l=0, r=100, t=10, b=10),
                        height=max(350, len(category_totals) * 50),
                        xaxis=dict(
                            showgrid=True,
                            gridcolor='#f1f3f4',
                            tickformat='$,.0f',
                            title='',
                            zeroline=False
                        ),
                        yaxis=dict(
                            title='',
                            tickfont=dict(size=13, color='#495057')
                        )
                    )
                else:
                    # Pie chart
                    fig = go.Figure(go.Pie(
                        labels=category_totals.index,
                        values=category_totals.values,
                        textinfo='label+percent',
                        textposition='outside',
                        hole=0.4,
                        marker=dict(
                            colors=px.colors.qualitative.Set3
                        ),
                        textfont=dict(size=11)
                    ))

                    fig.update_layout(
                        showlegend=False,
                        margin=dict(l=20, r=20, t=20, b=20),
                        height=400,
                        paper_bgcolor='rgba(0,0,0,0)'
                    )

                st.plotly_chart(fig, use_container_width=True)

            with col_table:
                # Create summary table
                summary_df = pd.DataFrame({
                    'Category': category_totals.index,
                    'Amount': category_totals.values,
                    'Txns': [category_counts.get(cat, 0) for cat in category_totals.index]
                })

                # Calculate exact height needed (header + rows)
                row_height = 35
                header_height = 38
                table_height = header_height + (len(summary_df) * row_height) + 2

                st.dataframe(
                    summary_df,
                    use_container_width=True,
                    hide_index=True,
                    height=table_height,
                    column_config={
                        "Amount": st.column_config.NumberColumn(
                            "Amount",
                            format="$%.2f"
                        ),
                        "Txns": st.column_config.NumberColumn(
                            "Txns",
                            format="%d"
                        )
                    }
                )

        # TAB 2: TRANSACTIONS
        with tab2:
            # Filters in a clean row
            col1, col2, col3 = st.columns([1, 1, 2])

            with col1:
                category_options = ['All'] + sorted(spending_df['Category'].unique().tolist())
                selected_category = st.selectbox(
                    "Category",
                    options=category_options,
                    index=category_options.index(st.session_state.selected_category) if st.session_state.selected_category in category_options else 0,
                    key='category_filter'
                )
                st.session_state.selected_category = selected_category

            with col2:
                card_options = ['All'] + sorted(spending_df['Card'].unique().tolist())
                selected_card = st.selectbox(
                    "Card",
                    options=card_options,
                    index=card_options.index(st.session_state.selected_card) if st.session_state.selected_card in card_options else 0,
                    key='card_filter'
                )
                st.session_state.selected_card = selected_card

            with col3:
                # Show filter summary
                filtered_df = spending_df.copy()
                if selected_category != 'All':
                    filtered_df = filtered_df[filtered_df['Category'] == selected_category]
                if selected_card != 'All':
                    filtered_df = filtered_df[filtered_df['Card'] == selected_card]

                filtered_total = filtered_df['Amount'].sum()
                st.markdown(f"""
                <div style="padding: 0.75rem 1rem; background: #f8f9fa; border-radius: 8px; margin-top: 1.5rem;">
                    <span style="color: #6c757d;">Showing</span>
                    <strong>{len(filtered_df)}</strong>
                    <span style="color: #6c757d;">transactions totaling</span>
                    <strong>${filtered_total:,.2f}</strong>
                </div>
                """, unsafe_allow_html=True)

            st.write("")  # Spacing

            # Sort by date (most recent first)
            filtered_df = filtered_df.sort_values('Date', ascending=False)

            # Display table
            st.dataframe(
                filtered_df[['Date', 'Card', 'Description', 'Amount', 'Category']],
                use_container_width=True,
                hide_index=True,
                height=550,
                column_config={
                    "Amount": st.column_config.NumberColumn(
                        "Amount",
                        format="$%.2f"
                    ),
                    "Date": st.column_config.DateColumn(
                        "Date",
                        format="YYYY-MM-DD"
                    ),
                    "Description": st.column_config.TextColumn(
                        "Description",
                        width="large"
                    )
                }
            )


if __name__ == "__main__":
    main()
