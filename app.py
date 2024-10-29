import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import boto3
import json
import os
from langchain_aws import ChatBedrock
from utils import ask_claude, calculate_sip, calculate_break_even, calculate_swp, create_investment_growth_report, create_swp_report, convert_df_to_excel
import datetime
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

    # Initialize session state variables if they don't exist
    if 'monthly_contribution' not in st.session_state:
        st.session_state.monthly_contribution = 1000.0
    if 'annual_return_rate' not in st.session_state:
        st.session_state.annual_return_rate = 12.0
    if 'investment_years' not in st.session_state:
        st.session_state.investment_years = 10

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
            value=str(st.session_state.monthly_contribution),
            on_change=update_contribution
        )
        st.slider(
            "Select Monthly Contribution Amount (₹)",
            100.0, 1000000.0, st.session_state.monthly_contribution,
            key="sip_monthly_contribution_slider",
            on_change=update_contribution_slider
        )

    # Expected Annual Return Rate
    with col2:
        st.text_input(
            "Expected Annual Return Rate (%)",
            key="sip_annual_return_rate",
            value=str(st.session_state.annual_return_rate),
            on_change=update_return_rate
        )
        st.slider(
            "Select Expected Annual Return Rate (%)",
            0.0, 50.0, st.session_state.annual_return_rate,
            key="sip_annual_return_rate_slider",
            on_change=update_return_rate_slider
        )

    # Investment Duration
    with col3:
        st.text_input(
            "Investment Duration (Years)",
            key="sip_investment_years",
            value=str(st.session_state.investment_years),
            on_change=update_years
        )
        st.slider(
            "Select Investment Duration (Years)",
            0, 50, st.session_state.investment_years,
            key="sip_investment_years_slider",
            on_change=update_years_slider
        )

    # Auto-calculate on any input change
    months = st.session_state.investment_years * 12
    future_value, total_invested, investment_history, contribution_history = calculate_sip(
        st.session_state.monthly_contribution,
        st.session_state.annual_return_rate / 100,
        st.session_state.investment_years
    )

    # Calculate estimated returns and break-even time
    estimated_returns = future_value - total_invested
    break_even_years, break_even_months = calculate_break_even(
        st.session_state.monthly_contribution,
        st.session_state.annual_return_rate / 100
    )

    # Store future value in session state for SWP calculator
    st.session_state['sip_future_value'] = future_value

    # Display results
    st.metric("Future Value of Investment", f"₹{future_value:,.2f}")
    st.metric("Total Amount Invested", f"₹{total_invested:,.2f}")
    st.metric("Estimated Returns", f"₹{estimated_returns:,.2f}")
    st.metric("Break-even Time", f"{break_even_years} years ({break_even_months} months)")

    # Create a pie chart to display the distribution
    pie_data = {
        'Category': ['Total Invested', 'Expected Returns'],
        'Amount': [total_invested, estimated_returns]
    }
    pie_chart = px.pie(pie_data, values='Amount', names='Category', title='Investment Breakdown')
    st.plotly_chart(pie_chart)

    # Generate and download the investment growth report
    if st.button("Generate Investment Growth Report"):
        report_data = create_investment_growth_report(
            st.session_state.monthly_contribution,
            st.session_state.annual_return_rate,
            st.session_state.investment_years
        )
        st.success("Investment growth report generated successfully!")
        st.download_button(
            label="Download Investment Growth Report",
            data=report_data,
            file_name=f"investment_growth_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )




elif option == "SWP Calculator":
    st.header("📉 SWP Calculator")

    # Initialize session state for each input if not already present
    if 'swp_initial_investment_input' not in st.session_state:
        st.session_state.swp_initial_investment_input = "100000.0" if "sip_future_value" not in st.session_state else f"{st.session_state['sip_future_value']:.2f}"
    if 'swp_monthly_withdrawal_input' not in st.session_state:
        st.session_state.swp_monthly_withdrawal_input = "5000.0"
    if 'swp_tax_rate_input' not in st.session_state:
        st.session_state.swp_tax_rate_input = "20.0"
    if 'swp_withdraw_years_input' not in st.session_state:
        st.session_state.swp_withdraw_years_input = "20"

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
        try:
            st.session_state.swp_initial_investment_slider = float(st.session_state.swp_initial_investment_input)
        except ValueError:
            st.session_state.swp_initial_investment_input = f"{st.session_state.swp_initial_investment_slider:.2f}"

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
        initial_investment = st.text_input(
            "Initial Investment Amount (₹)",
            value=st.session_state.swp_initial_investment_input,
            key="swp_initial_investment_input",
            on_change=update_investment_slider
        )
        initial_investment_slider = st.slider(
            "Initial Investment Amount (₹)",
            min_value=100.0,
            max_value=1000000.0,
            step=100.0,
            value=float(initial_investment) if initial_investment else 100000.0,
            key="swp_initial_investment_slider",
            on_change=update_investment_input
        )

    with col2:
        monthly_withdrawal = st.text_input(
            "Monthly Withdrawal Amount (₹)",
            value=st.session_state.swp_monthly_withdrawal_input,
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
        total_withdrawals, after_tax_withdrawals, remaining_balance, monthly_balances, after_tax_withdrawal_history = calculate_swp(
            initial_investment_slider,
            monthly_withdrawal_slider,
            tax_rate_slider,
            withdraw_years_slider
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
elif option == "Chatbot":
    st.header("💬 Chatbot Assistant")
    st.write("Ask me any investment-related question!")

    user_query = st.text_input("Your question:", key="chatbot_query")

    if st.button("Ask", key="ask_chatbot"):
        if user_query:
            with st.spinner("Getting response..."):
                # Call the ask_claude function with the user's question
                bot_response = ask_claude(user_query)
                st.write("Chatbot:", bot_response)
                st.session_state["chatbot_response"] = bot_response
        else:
            st.write("Please enter a question.")
