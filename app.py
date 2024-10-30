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
    sip_results = calculate_sip(
        st.session_state.monthly_contribution,
        st.session_state.annual_return_rate / 100,
        st.session_state.investment_years
    )
    future_value = sip_results[0]
    total_invested = sip_results[1]


    # Store future value in session state for SWP calculator
    st.session_state['sip_future_value'] = future_value

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
# ... (previous code remains the same until the Monthly SIP Contribution Details section)

    # Display monthly SIP contribution details
    st.subheader("Monthly SIP Contribution Details")
    
    # Calculate monthly progression with improved breakeven detection
    monthly_rate = (1 + st.session_state.annual_return_rate / 100) ** (1/12) - 1
    monthly_data = []
    cumulative_investment = 0
    cumulative_value = 0
    breakeven_month = None
    has_breakeven_occurred = False
    
    for month in range(1, months + 1):
        cumulative_investment += st.session_state.monthly_contribution
        # Calculate compounded returns
        cumulative_value = sum([
            st.session_state.monthly_contribution * (1 + monthly_rate) ** (month - i)
            for i in range(month)
        ])
        
        returns = cumulative_value - cumulative_investment
        
        # Improved breakeven detection
        if not has_breakeven_occurred and returns > 0:
            # Linear interpolation to find more precise breakeven point
            if month > 1:
                prev_returns = monthly_data[-1]['Returns']
                if prev_returns < 0 and returns > 0:
                    # Calculate fraction of month where breakeven occurred
                    fraction = abs(prev_returns) / (returns - prev_returns)
                    breakeven_month = month - 1 + fraction
                    has_breakeven_occurred = True
            else:
                breakeven_month = month
                has_breakeven_occurred = True
            
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
    
    # Enhanced styling function for the DataFrame
    def highlight_years_and_breakeven(x):
        df_styled = pd.DataFrame('', index=x.index, columns=x.columns)
        
        # Highlight year changes
        df_styled.loc[x['Month'] % 12 == 1, :] = 'background-color: #50C878'
        
        # Highlight breakeven point if it exists and hasn't occurred yet
        if breakeven_month and not has_breakeven_occurred:
            # Find the closest month to highlight
            closest_month = int(np.ceil(breakeven_month))
            df_styled.loc[closest_month-1, :] = 'background-color: #FFD700'
            
        return df_styled

    # Apply styling to DataFrame
    styled_sip_data = sip_data.style.format({
        'Invested Amount': '₹{:,.2f}',
        'Current Value': '₹{:,.2f}',
        'Returns': '₹{:,.2f}',
        'Returns %': '{:,.2f}%'
    }).apply(highlight_years_and_breakeven, axis=None)
    
    # Display breakeven information only if it hasn't occurred yet
    if breakeven_month and not has_breakeven_occurred:
        breakeven_year = (int(breakeven_month) - 1) // 12 + 1
        breakeven_month_in_year = int(breakeven_month - 1) % 12 + 1
        
        # Create columns for breakeven metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.success(f"📈 Breakeven Point: Month {breakeven_month:.1f} (Year {breakeven_year}, Month {breakeven_month_in_year})")
        
        # Find the closest month for displaying breakeven values
        closest_month_index = int(np.ceil(breakeven_month)) - 1
        
        with col2:
            st.metric(
                "Investment at Breakeven",
                f"₹{sip_data['Invested Amount'].iloc[closest_month_index]:,.2f}"
            )
        
        with col3:
            st.metric(
                "Value at Breakeven",
                f"₹{sip_data['Current Value'].iloc[closest_month_index]:,.2f}"
            )
    
    # Display the styled DataFrame
    st.dataframe(styled_sip_data)
    
    # Add summary statistics
    col1, col2 = st.columns(2)
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

    # Update the Excel conversion function to handle the new breakeven logic
    def convert_df_to_excel(df, breakeven_month, has_breakeven_occurred):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # ... (previous Excel formatting code remains the same until summary section)
            
            # Update breakeven information in Excel
            if breakeven_month and not has_breakeven_occurred:
                breakeven_year = (int(breakeven_month) - 1) // 12 + 1
                breakeven_month_in_year = int(breakeven_month - 1) % 12 + 1
                
                worksheet.write(
                    summary_row + 3, 0,
                    f"Breakeven Point: Month {breakeven_month:.1f} (Year {breakeven_year}, Month {breakeven_month_in_year})"
                )
                
                closest_month_index = int(np.ceil(breakeven_month)) - 1
                
                worksheet.write(summary_row + 4, 0, "Investment at Breakeven")
                worksheet.write(
                    summary_row + 4, 1,
                    df['Invested Amount'].iloc[closest_month_index],
                    money_format
                )
                
                worksheet.write(summary_row + 5, 0, "Value at Breakeven")
                worksheet.write(
                    summary_row + 5, 1,
                    df['Current Value'].iloc[closest_month_index],
                    money_format
                )
        
        output.seek(0)
        return output.getvalue()

    # Add a download button for the SIP data
    sip_excel_buffer = convert_df_to_excel(sip_data, breakeven_month, has_breakeven_occurred)
    st.download_button(
        label="Download Detailed SIP Analysis",
        data=sip_excel_buffer,
        file_name="sip_detailed_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# SWP Calculator Section
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
