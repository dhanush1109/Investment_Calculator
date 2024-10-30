import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import boto3
import json
import os
from langchain_aws import ChatBedrock
from utils import calculate_sip, calculate_break_even, calculate_swp, create_investment_growth_report, create_swp_report, convert_df_to_excel, ask_bot
import datetime
from io import BytesIO
# Set page configuration
st.set_page_config(
    page_title="Investment Calculator",
    page_icon="💰",
    layout="wide"
)

# Import external CSS
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Streamlit app
st.title("💰 Investment Calculator")

# Sidebar navigation
option = st.sidebar.selectbox("Select Calculator", ["SIP Calculator", "SWP Calculator", "Chatbot"], key="selected_option")

if option == "SIP Calculator":
    st.header("📈 SIP Calculator")

    # Initialize default values
    DEFAULT_MONTHLY_CONTRIBUTION = 1000.0
    DEFAULT_ANNUAL_RETURN_RATE = 12.0
    DEFAULT_INVESTMENT_YEARS = 10

    # Initialize all session state variables at once
    defaults = {
        'monthly_contribution': DEFAULT_MONTHLY_CONTRIBUTION,
        'annual_return_rate': DEFAULT_ANNUAL_RETURN_RATE,
        'investment_years': DEFAULT_INVESTMENT_YEARS,
        'sip_monthly_contribution': str(DEFAULT_MONTHLY_CONTRIBUTION),
        'sip_annual_return_rate': str(DEFAULT_ANNUAL_RETURN_RATE),
        'sip_investment_years': str(DEFAULT_INVESTMENT_YEARS),
        'sip_monthly_contribution_slider': DEFAULT_MONTHLY_CONTRIBUTION,
        'sip_annual_return_rate_slider': DEFAULT_ANNUAL_RETURN_RATE,
        'sip_investment_years_slider': DEFAULT_INVESTMENT_YEARS
    }

    # Initialize any missing session state variables
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Create callback functions for syncing inputs
    def update_contribution():
        try:
            value = float(st.session_state.sip_monthly_contribution)
            st.session_state.monthly_contribution = value
            st.session_state.sip_monthly_contribution_slider = value
        except ValueError:
            pass

    def update_contribution_slider():
        st.session_state.monthly_contribution = st.session_state.sip_monthly_contribution_slider
        st.session_state.sip_monthly_contribution = str(st.session_state.sip_monthly_contribution_slider)

    def update_return_rate():
        try:
            value = float(st.session_state.sip_annual_return_rate)
            st.session_state.annual_return_rate = value
            st.session_state.sip_annual_return_rate_slider = value
        except ValueError:
            pass

    def update_return_rate_slider():
        st.session_state.annual_return_rate = st.session_state.sip_annual_return_rate_slider
        st.session_state.sip_annual_return_rate = str(st.session_state.sip_annual_return_rate_slider)

    def update_years():
        try:
            value = int(st.session_state.sip_investment_years)
            st.session_state.investment_years = value
            st.session_state.sip_investment_years_slider = value
        except ValueError:
            pass

    def update_years_slider():
        st.session_state.investment_years = st.session_state.sip_investment_years_slider
        st.session_state.sip_investment_years = str(st.session_state.sip_investment_years_slider)

    # Create columns for inputs
    col1, col2, col3 = st.columns(3)

    # Monthly Contribution
    with col1:
        st.text_input(
            "Monthly Contribution Amount (₹)",
            key="sip_monthly_contribution",
            on_change=update_contribution
        )
        st.slider(
            "Select Monthly Contribution Amount (₹)",
            100.0, 1000000.0,
            key="sip_monthly_contribution_slider",
            on_change=update_contribution_slider
        )

    # Expected Annual Return Rate
    with col2:
        st.text_input(
            "Expected Annual Return Rate (%)",
            key="sip_annual_return_rate",
            on_change=update_return_rate
        )
        st.slider(
            "Select Expected Annual Return Rate (%)",
            0.0, 50.0,
            key="sip_annual_return_rate_slider",
            on_change=update_return_rate_slider
        )

    # Investment Duration
    with col3:
        st.text_input(
            "Investment Duration (Years)",
            key="sip_investment_years",
            on_change=update_years
        )
        st.slider(
            "Select Investment Duration (Years)",
            0, 50,
            key="sip_investment_years_slider",
            on_change=update_years_slider
        )

    # Auto-calculate on any input change
    months = st.session_state.investment_years * 12
    sip_results = calculate_sip(
        st.session_state.monthly_contribution,
        st.session_state.annual_return_rate / 100,
        st.session_state.investment_years
    )
    future_value = sip_results[0]
    total_invested = sip_results[1]

    # Store future value in session state for SWP calculator
    st.session_state['sip_future_value'] = future_value

    # Rest of your code remains the same...
    # Display results
    st.metric("Future Value of Investment", f"₹{future_value:,.2f}")
    st.metric("Total Amount Invested", f"₹{total_invested:,.2f}")
    st.metric("Estimated Returns", f"₹{future_value - total_invested:,.2f}")

    # Create a pie chart to display the distribution
    pie_data = {
        'Category': ['Total Invested', 'Expected Returns'],
        'Amount': [total_invested, future_value - total_invested]
    }
    pie_chart = px.pie(pie_data, values='Amount', names='Category', title='Investment Breakdown')
    st.plotly_chart(pie_chart)

    # Display monthly SIP contribution details
    st.subheader("Monthly SIP Contribution Details")
    
    # Calculate monthly progression with improved breakeven detection
    monthly_rate = (1 + st.session_state.annual_return_rate / 100) ** (1/12) - 1
    monthly_data = []
    cumulative_investment = 0
    cumulative_value = 0
    breakeven_month = None
    has_broken_even = False  # Flag to track if investment has broken even
    
    for month in range(1, months + 1):
        cumulative_investment += st.session_state.monthly_contribution
        # Calculate compounded returns
        cumulative_value = sum([
            st.session_state.monthly_contribution * (1 + monthly_rate) ** (month - i)
            for i in range(month)
        ])
        
        returns = cumulative_value - cumulative_investment
        
        # Track breakeven point (when returns first become positive)
        if not has_broken_even and returns > 0:
            breakeven_month = month
            has_broken_even = True
            
        monthly_data.append({
            'Month': month,
            'Year': (month - 1) // 12 + 1,
            'Invested Amount': cumulative_investment,
            'Current Value': cumulative_value,
            'Returns': returns,
            'Returns %': (returns / cumulative_investment) * 100 if cumulative_investment > 0 else 0
        })
    
    # Create DataFrame with monthly details
    sip_data = pd.DataFrame(monthly_data)
    
    # Display breakeven information only if it exists
    if breakeven_month:
        breakeven_year = (breakeven_month - 1) // 12 + 1
        breakeven_month_in_year = (breakeven_month - 1) % 12 + 1
        
        # Create an info box for initial breakeven point
        st.info(f"""
        🎯 Initial Breakeven Point:
        - Investment broke even in Month {breakeven_month} (Year {breakeven_year}, Month {breakeven_month_in_year})
        - Investment at breakeven: ₹{sip_data['Invested Amount'].iloc[breakeven_month-1]:,.2f}
        - Value at breakeven: ₹{sip_data['Current Value'].iloc[breakeven_month-1]:,.2f}
        - Returns at breakeven: ₹{sip_data['Returns'].iloc[breakeven_month-1]:,.2f}
        """)

    # Fixed styling function
    def highlight_years_and_breakeven(df):
        def style_row(row):
            if breakeven_month and row.name == breakeven_month - 1:
                return ['background-color: #FFD700; font-weight: bold'] * len(row)
            elif (row['Month'] % 12) == 1:
                return ['background-color: #90EE90'] * len(row)
            return [''] * len(row)
        
        return pd.DataFrame(df.apply(style_row, axis=1).tolist(), 
                          index=df.index, 
                          columns=df.columns)

    # Format and style the DataFrame
    styled_sip_data = sip_data.style\
        .format({
            'Invested Amount': '₹{:,.2f}',
            'Current Value': '₹{:,.2f}',
            'Returns': '₹{:,.2f}',
            'Returns %': '{:,.2f}%'
        })\
        .apply(highlight_years_and_breakeven, axis=None)
    
    # Display the styled DataFrame
    st.dataframe(
        styled_sip_data,
        height=400,
        use_container_width=True
    )

    # Add summary metrics in columns with improved breakeven display
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Average Monthly Return", 
            f"₹{(sip_data['Returns'].iloc[-1] / months):,.2f}"
        )
    
    with col2:
        st.metric(
            "Current Monthly Return", 
            f"₹{sip_data['Returns'].diff().iloc[-1]:,.2f}"
        )
        
    with col3:
        if has_broken_even:
            current_returns = sip_data['Returns'].iloc[-1]
            st.metric(
                "Current Total Returns",
                f"₹{current_returns:,.2f}",
                delta=f"{(current_returns / sip_data['Invested Amount'].iloc[-1] * 100):.1f}%"
            )
        else:
            months_to_breakeven = "Not yet reached"
            st.metric(
                "Months to Breakeven",
                months_to_breakeven
            )

    # Update Excel export function to handle breakeven correctly
    def convert_df_to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='SIP Details')
            
            workbook = writer.book
            worksheet = writer.sheets['SIP Details']
            
            # Format definitions
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#F0F2F6',
                'border': 1
            })
            
            money_format = workbook.add_format({
                'num_format': '₹#,##0.00',
                'border': 1
            })
            
            percent_format = workbook.add_format({
                'num_format': '0.00"%"',
                'border': 1
            })
            
            year_format = workbook.add_format({
                'bg_color': '#90EE90',
                'border': 1
            })
            
            breakeven_format = workbook.add_format({
                'bg_color': '#FFD700',
                'bold': True,
                'border': 1
            })
            
            # Apply formats
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            # Format data rows with correct breakeven handling
            for row_num in range(1, len(df) + 1):
                row_data = df.iloc[row_num-1]
                
                # Determine if this is a year change or breakeven row
                is_year_change = row_data['Month'] % 12 == 1
                is_breakeven = breakeven_month and row_num == breakeven_month
                
                # Choose appropriate format
                if is_breakeven:
                    row_format = breakeven_format
                elif is_year_change:
                    row_format = year_format
                else:
                    row_format = money_format
                
                # Write row data with appropriate formatting
                for col_num, value in enumerate(row_data):
                    if col_num in [2, 3, 4]:  # Money columns
                        worksheet.write(row_num, col_num, value, row_format)
                    elif col_num == 5:  # Percentage column
                        worksheet.write(row_num, col_num, value/100, percent_format)
                    else:
                        worksheet.write(row_num, col_num, value, row_format)
            
            # Add breakeven information if applicable
            summary_row = len(df) + 2
            if breakeven_month:
                worksheet.write(summary_row, 0, "Breakeven Analysis", workbook.add_format({'bold': True}))
                worksheet.write(summary_row + 1, 0, f"Initial Breakeven Month: {breakeven_month}")
                worksheet.write(summary_row + 1, 1, f"Year {(breakeven_month-1)//12 + 1}, Month {(breakeven_month-1)%12 + 1}")
                worksheet.write(summary_row + 2, 0, "Returns at Breakeven")
                worksheet.write(summary_row + 2, 1, df['Returns'].iloc[breakeven_month-1], money_format)
            
        return output.getvalue()

    # Add download button
    excel_data = convert_df_to_excel(sip_data)
    st.download_button(
        label="Download Detailed SIP Analysis",
        data=excel_data,
        file_name="sip_detailed_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# SWP Calculator Section
elif option == "SWP Calculator":
    st.header("📉 SWP Calculator")
    if 'swp_initial_investment' not in st.session_state:
        st.session_state.swp_initial_investment = st.session_state.get('sip_future_value', 100000.0)
    if 'swp_monthly_withdrawal_input' not in st.session_state:
        st.session_state.swp_monthly_withdrawal_input = "5000.0"  # Initialize as a string
    if 'swp_tax_rate' not in st.session_state:
        st.session_state.swp_tax_rate = 20.0
    if 'swp_tax_rate_input' not in st.session_state:
        st.session_state.swp_tax_rate_input = "20.0"  # Initialize as a string
    if 'swp_withdraw_years' not in st.session_state:
        st.session_state.swp_withdraw_years = 20
    if 'swp_withdraw_years_input' not in st.session_state:
        st.session_state.swp_withdraw_years_input = "20"  # Initialize as a string


    # Callback functions for synchronization
    def update_investment():
        try:
            value = float(st.session_state.swp_initial_investment_input)
            st.session_state.swp_initial_investment = value
            st.session_state.swp_initial_investment_slider = value
        except ValueError:
            pass

    # Callback functions for input synchronization
    def update_investment_input():
        st.session_state.swp_initial_investment_input = f"{st.session_state.swp_initial_investment_slider:.2f}"

    def update_withdrawal_input():
        st.session_state.swp_monthly_withdrawal_input = f"{st.session_state.swp_monthly_withdrawal_slider:.2f}"

    def update_tax_input():
        st.session_state.swp_tax_rate_input = f"{st.session_state.swp_tax_rate_slider:.2f}"

    def update_years_input():
        st.session_state.swp_withdraw_years_input = str(st.session_state.swp_withdraw_years_slider)

    def update_investment_slider():
        st.session_state.swp_initial_investment = st.session_state.swp_initial_investment_slider
        st.session_state.swp_initial_investment_input = str(st.session_state.swp_initial_investment_slider)

    def update_withdrawal_slider():
        try:
            st.session_state.swp_monthly_withdrawal_slider = float(st.session_state.swp_monthly_withdrawal_input)
        except ValueError:
            st.session_state.swp_monthly_withdrawal_input = f"{st.session_state.swp_monthly_withdrawal_slider:.2f}"

    def update_tax_slider():
        try:
            st.session_state.swp_tax_rate_slider = float(st.session_state.swp_tax_rate_input)
        except ValueError:
            st.session_state.swp_tax_rate_input = f"{st.session_state.swp_tax_rate_slider:.2f}"

    def update_years_slider():
        try:
            st.session_state.swp_withdraw_years_slider = int(st.session_state.swp_withdraw_years_input)
        except ValueError:
            st.session_state.swp_withdraw_years_input = str(st.session_state.swp_withdraw_years_slider)

    # Create input layout
    col1, col2, col3 = st.columns(3)

    with col1:
        st.text_input(
            "Initial Investment Amount (₹)",
            value=str(st.session_state.swp_initial_investment),
            key="swp_initial_investment_input",
            on_change=update_investment
        )
        st.slider(
            "Initial Investment Amount (₹)",
            min_value=100.0,
            max_value=1000000.0,
            step=100.0,
            value=st.session_state.swp_initial_investment,
            key="swp_initial_investment_slider",
            on_change=update_investment_slider
        )

    with col2:
        monthly_withdrawal = st.text_input(
        "Monthly Withdrawal Amount (₹)",
        value=str(st.session_state.swp_monthly_withdrawal_input),
        key="swp_monthly_withdrawal_input",
        on_change=update_withdrawal_slider
        )

        monthly_withdrawal_slider = st.slider(
            "Monthly Withdrawal Amount (₹)",
            min_value=100.0,
            max_value=50000.0,
            step=100.0,
            value=float(monthly_withdrawal) if monthly_withdrawal else 5000.0,
            key="swp_monthly_withdrawal_slider",
            on_change=update_withdrawal_input
        )

    with col3:
        tax_rate = st.text_input(
            "Tax Rate on Withdrawals (%)",
            value=st.session_state.swp_tax_rate_input,
            key="swp_tax_rate_input",
            on_change=update_tax_slider
        )
        tax_rate_slider = st.slider(
            "Tax Rate on Withdrawals (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            value=float(tax_rate) if tax_rate else 20.0,
            key="swp_tax_rate_slider",
            on_change=update_tax_input
        )
        
        withdraw_years = st.text_input(
            "Duration of Withdrawals (Years)",
            value=st.session_state.swp_withdraw_years_input,
            key="swp_withdraw_years_input",
            on_change=update_years_slider
        )
        withdraw_years_slider = st.slider(
            "Duration of Withdrawals (Years)",
            min_value=1,
            max_value=50,
            step=1,
            value=int(withdraw_years) if withdraw_years else 20,
            key="swp_withdraw_years_slider",
            on_change=update_years_input
        )

    # Calculate and display results
    if st.button("Calculate SWP Details", key="calculate_swp"):
        # Perform calculations
        # Use st.session_state variables directly in calculations
        total_withdrawals, after_tax_withdrawals, remaining_balance, monthly_balances, after_tax_withdrawal_history = calculate_swp(
            st.session_state.swp_initial_investment_slider,
            st.session_state.swp_monthly_withdrawal_slider,
            st.session_state.swp_tax_rate_slider,
            st.session_state.swp_withdraw_years_slider
        )


        # Display summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Withdrawals (before tax)", f"₹{total_withdrawals:,.2f}")
        with col2:
            st.metric("Total Withdrawals (after tax)", f"₹{after_tax_withdrawals:,.2f}")
        with col3:
            st.metric("Remaining Balance", f"₹{remaining_balance:,.2f}")

        # Calculate total tax paid
        total_tax_paid = total_withdrawals - after_tax_withdrawals
        st.metric("Total Tax Paid", f"₹{total_tax_paid:,.2f}")

        # Create visualization data
        months = list(range(1, len(monthly_balances) + 1))
        
        # Plot balance progression
        st.subheader("Investment Balance Over Time")
        balance_data = pd.DataFrame({
            'Month': months,
            'Balance': monthly_balances
        })
        balance_chart = px.line(balance_data, x='Month', y='Balance',
                              title='Investment Balance Progression',
                              labels={'Balance': 'Balance (₹)', 'Month': 'Month Number'})
        st.plotly_chart(balance_chart)

        # Display monthly withdrawal details
        st.subheader("Monthly Withdrawal Details")
        monthly_data = pd.DataFrame({
            'Month': months,
            'Withdrawal (before tax)': [monthly_withdrawal_slider] * len(months),
            'Withdrawal (after tax)': after_tax_withdrawal_history,
            'Tax Paid': [(monthly_withdrawal_slider - amt) for amt in after_tax_withdrawal_history],
            'Remaining Balance': monthly_balances
        })

        # Display the table
        st.dataframe(monthly_data.style.format({
            'Withdrawal (before tax)': '₹{:,.2f}',
            'Withdrawal (after tax)': '₹{:,.2f}',
            'Tax Paid': '₹{:,.2f}',
            'Remaining Balance': '₹{:,.2f}'
        }))

        # Add the download button
        excel_buffer = convert_df_to_excel(monthly_data)
        st.download_button(
            label="Download Table Data",
            data=excel_buffer,
            file_name=f"swp_monthly_details_.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Chatbot Section
if option == "Chatbot":
    st.header("💬 Investment Chatbot")
    st.write("Still under development") 
    # st.write("Ask me any investment-related question!")

    # user_query = st.text_area("Your question:", height=100, key="chatbot_query")

    # if st.button("Ask", key="ask_chatbot"):
    #     if user_query:
    #         with st.spinner("Getting response..."):
    #             bot_response = ask_bot(user_query)
    #             st.write("Chatbot:", bot_response)
    #             st.session_state["chatbot_response"] = bot_response
    #     else:
    #         st.warning("Please enter a question.")

    # if "chatbot_response" in st.session_state:
    #     with st.expander("Previous Response"):
    #         st.write(st.session_state["chatbot_response"])


# if option == "Chatbot":
#     st.header("💬 Investment Chatbot")
#     st.write("Ask me any investment-related question!")

#     user_query = st.text_area("Your question:", height=100, key="chatbot_query")

#     if st.button("Ask", key="ask_chatbot"):
#         if user_query:
#             with st.spinner("Getting response..."):
#                 bot_response = ask_bot(user_query)
#                 st.write("Chatbot:", bot_response)
#                 st.session_state["chatbot_response"] = bot_response
#         else:
#             st.warning("Please enter a question.")

#     if "chatbot_response" in st.session_state:
#         with st.expander("Previous Response"):
#             st.write(st.session_state["chatbot_response"])
