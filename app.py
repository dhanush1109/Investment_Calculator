import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import boto3
import json
import os
from langchain_aws import ChatBedrock
from utils import ask_claude, calculate_sip, calculate_break_even, calculate_swp, create_investment_growth_report,create_sip_visualizations, create_swp_visualizations, create_withdrawal_report, create_swp_report

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

    # Create sliders and text inputs for SIP inputs
    col1, col2, col3 = st.columns(3)
    with col1:
        monthly_contribution = st.text_input("Monthly Contribution Amount (₹)", value="1000.0", key="sip_monthly_contribution")
        monthly_contribution = float(monthly_contribution) if monthly_contribution else 0.0
    with col2:
        annual_return_rate = st.text_input("Expected Annual Return Rate (%)", value="12.0", key="sip_annual_return_rate")
        annual_return_rate = float(annual_return_rate) / 100 if annual_return_rate else 0.0
    with col3:    
        investment_years = st.text_input("Investment Duration (Years)", value="20", key="sip_investment_years")
        investment_years = int(investment_years) if investment_years else 0

    if st.button("Calculate SIP Details", key="calculate_sip"):
        months = investment_years * 12  # Calculate total months for investment
        future_value, total_invested, investment_history, contribution_history = calculate_sip(
            monthly_contribution, annual_return_rate, investment_years
        )

        # Calculate estimated returns and break-even time
        estimated_returns = future_value - total_invested
        break_even_years, break_even_months = calculate_break_even(monthly_contribution, annual_return_rate)

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
            report_file = create_investment_growth_report(investment_history, contribution_history, monthly_contribution, annual_return_rate * 100, investment_years)
            st.success("Investment growth report generated successfully!")
            st.download_button(
                label="Download Investment Growth Report",
                data=report_file,
                file_name=f"investment_growth_report_{monthly_contribution}_{annual_return_rate * 100}_{investment_years}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# SWP Calculator Section
elif option == "SWP Calculator":
    st.header("📉 SWP Calculator")

    # Create sliders and text inputs for SWP inputs
    col1, col2, col3 = st.columns(3)
    with col1:
        # Use the SIP total value for the initial investment
        initial_investment = st.text_input("Initial Investment Amount (₹)", 
                                            value=f"{st.session_state['sip_future_value']:.2f}" if "sip_future_value" in st.session_state else "100000.0", 
                                            key="swp_initial_investment")
        initial_investment = float(initial_investment) if initial_investment else 0.0
        initial_investment_slider = st.slider("Initial Investment Amount (₹)", 
                                               min_value=100.0, max_value=1000000.0, step=100.0, 
                                               value=initial_investment)
    with col2:
        monthly_withdrawal = st.text_input("Monthly Withdrawal Amount (₹)", value="5000.0", key="swp_monthly_withdrawal")
        monthly_withdrawal = float(monthly_withdrawal) if monthly_withdrawal else 0.0
        monthly_withdrawal_slider = st.slider("Monthly Withdrawal Amount (₹)", min_value=100.0, max_value=50000.0, step=100.0, value=monthly_withdrawal)
    with col3:
        tax_rate = st.text_input("Tax Rate on Withdrawals (%)", value="20.0", key="swp_tax_rate")
        tax_rate = float(tax_rate) if tax_rate else 0.0
        tax_rate_slider = st.slider("Tax Rate on Withdrawals (%)", min_value=0.0, max_value=100.0, step=0.1, value=tax_rate)
        withdraw_years = st.text_input("Duration of Withdrawals (Years)", value="20", key="swp_withdrawal_years")
        withdraw_years = int(withdraw_years) if withdraw_years else 0
        withdraw_years_slider = st.slider("Duration of Withdrawals (Years)", min_value=1, max_value=50, step=1, value=withdraw_years)

    # Ensure that the values are up-to-date
    if st.button("Calculate SWP Details", key="calculate_swp"):
        total_withdrawals, after_tax_withdrawals, remaining_balance, monthly_balances, total_withdrawal_history = calculate_swp(initial_investment_slider, monthly_withdrawal_slider, tax_rate_slider, withdraw_years_slider)

        # Display results
        st.metric("Total Withdrawals (before tax)", f"₹{total_withdrawals:,.2f}")
        st.metric("Total Withdrawals (after tax)", f"₹{after_tax_withdrawals:,.2f}")
        st.metric("Remaining Balance", f"₹{remaining_balance:,.2f}")

        # Generate the SWP report and get the filename
        swp_file_name = create_swp_report(initial_investment_slider, monthly_withdrawal_slider, tax_rate_slider, withdraw_years_slider, total_withdrawals, after_tax_withdrawals, remaining_balance)

        # Provide a download button for the SWP report
        st.download_button(
            label="Download SWP Report",
            data=open(swp_file_name, "rb"),
            file_name=swp_file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Create and display visualizations
        fig_balance, fig_withdrawals, fig_comparison = create_swp_visualizations(monthly_balances, total_withdrawal_history, initial_investment_slider)

        st.plotly_chart(fig_balance)
        st.plotly_chart(fig_withdrawals)
        st.plotly_chart(fig_comparison)

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