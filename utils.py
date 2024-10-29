import pandas as pd
from langchain_aws import ChatBedrock
import plotly.express as px
import plotly.graph_objects as go
import boto3

# Initialize the ChatBedrock client
chat_client = ChatBedrock(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    model_kwargs={"temperature": 0.0}
)

def ask_claude(text_prompt):
    try:
        # Call the invoke method with the input
        response = chat_client.invoke(input=text_prompt)
        
        # Extract the response content
        if "content" in response:
            return response["content"]
        else:
            return "Error: No response content from the model."
    except Exception as e:
        return f"Error: {str(e)}"
    
# Function to calculate SIP returns
# def calculate_sip(monthly_contribution, annual_return_rate, investment_years):
#     months = investment_years * 12
#     total_invested = monthly_contribution
#     future_value = monthly_contribution
#     investment_history = []
#     contribution_history = []
    
#     for month in range(months):
#         future_value *= (1 + annual_return_rate / 12)  # Compound the investment
#         if month > 0:  # Skip the first month if there's no contribution yet
#             future_value += monthly_contribution
#             total_invested += monthly_contribution
        
#         # Store the history for visualization
#         investment_history.append(future_value)
#         contribution_history.append(total_invested)

#     return future_value, total_invested, investment_history, contribution_history

def calculate_sip(monthly_contribution, annual_return_rate, investment_years):
    monthly_return_rate = annual_return_rate / 12
    total_months = investment_years * 12
    future_value = monthly_contribution * (((1 + monthly_return_rate) ** total_months - 1) / monthly_return_rate) * (1 + monthly_return_rate)
    total_invested = monthly_contribution * total_months
    investment_history = []  # Populate as needed
    contribution_history = []  # Populate as needed
    
    return future_value, total_invested, investment_history, contribution_history

def create_sip_visualizations(investment_history, contribution_history):
    months = len(investment_history)
    time_series = list(range(1, months + 1))

    # Plot Investment Growth Over Time
    fig_growth = go.Figure()
    fig_growth.add_trace(go.Scatter(x=time_series, y=investment_history, mode='lines+markers', name='Investment Growth'))
    fig_growth.update_layout(title='Investment Growth Over Time', xaxis_title='Months', yaxis_title='Value (₹)')

    # Plot Total Contributions vs. Total Value
    fig_comparison = go.Figure()
    fig_comparison.add_trace(go.Scatter(x=time_series, y=contribution_history, mode='lines', name='Total Contributions'))
    fig_comparison.add_trace(go.Scatter(x=time_series, y=investment_history, mode='lines', name='Total Value', line=dict(dash='dash')))
    fig_comparison.update_layout(title='Total Contributions vs Total Value', xaxis_title='Months', yaxis_title='Amount (₹)')

    # Plot Monthly Contributions vs. Value
    fig_monthly = go.Figure()
    fig_monthly.add_trace(go.Scatter(x=time_series, y=[investment_history[i] - contribution_history[i] for i in range(months)], mode='lines', name='Monthly Contributions'))
    fig_monthly.add_trace(go.Scatter(x=time_series, y=investment_history, mode='lines', name='Total Value'))
    fig_monthly.update_layout(title='Monthly Contributions vs Total Value', xaxis_title='Months', yaxis_title='Amount (₹)')

    return fig_growth, fig_comparison, fig_monthly


def calculate_break_even(monthly_investment, expected_return):
    """
    Calculates the time in months and years required to break even on a monthly investment
    given an expected annual return rate.

    Parameters:
    monthly_investment (float): The amount invested each month
    expected_return (float): The expected annual return rate (e.g. 0.08 for 8% annual return)

    Returns:
    Tuple[int, int]: The time to break even in years and remaining months
    """
    months = 0
    while True:
        total_invested = monthly_investment * months
        future_value = calculate_sip(monthly_investment, expected_return, months // 12)[0]  # Use the first return value for future value
        if future_value > total_invested:
            break
        months += 1
    years = months // 12
    remaining_months = months % 12
    return years, remaining_months

# def calculate_sip(monthly_investment, annual_return, years):
#     """
#     Calculates the future value of a series of equal monthly investments (SIP)
#     given an annual return rate and the number of years.

#     Parameters:
#     monthly_investment (float): The amount invested each month
#     annual_return (float): The expected annual return rate (e.g. 0.08 for 8% annual return)
#     years (int): The number of years to calculate the future value for

#     Returns:
#     Tuple[float, float]: The future value and the total amount invested
#     """
#     monthly_return = (1 + annual_return) ** (1/12) - 1
#     future_value = monthly_investment * ((1 + monthly_return) ** (years * 12) - 1) / monthly_return
#     total_invested = monthly_investment * years * 12
#     return future_value, total_invested


def create_investment_growth_report(investment_history, contribution_history, monthly_investment, expected_return, years):
    # Create a DataFrame with monthly balances and contributions
    df = pd.DataFrame({
        "Month": range(1, len(investment_history) + 1),
        "Future Value": investment_history,
        "Total Invested": contribution_history
    })
    
    # Add additional columns
    df["Monthly Investment"] = monthly_investment
    df["Expected Annual Return (%)"] = expected_return
    df["Investment Duration (Years)"] = years
    
    # Save the DataFrame to an Excel file
    file_name = f"investment_growth_report_{monthly_investment}_{expected_return}_{years}.xlsx"
    df.to_excel(file_name, index=False)
    
    return file_name


def calculate_swp(initial_investment, monthly_withdrawal, tax_rate, withdraw_years):
    months = withdraw_years * 12
    monthly_balances = []
    total_withdrawal_history = []
    current_balance = initial_investment

    for month in range(months):
        # Calculate the monthly withdrawal (post-tax)
        tax = (monthly_withdrawal * tax_rate) / 100
        after_tax_withdrawal = monthly_withdrawal + tax
        current_balance -= after_tax_withdrawal
        
        # Compound the remaining balance
        current_balance *= (1 + 0.01)  # Assuming a 1% monthly growth for illustration
        
        # Store the results
        monthly_balances.append(current_balance)
        total_withdrawal_history.append(after_tax_withdrawal)
    
    total_withdrawals = sum(total_withdrawal_history)
    after_tax_withdrawals = total_withdrawals - (total_withdrawals * (tax_rate / 100))
    remaining_balance = current_balance

    return total_withdrawals, after_tax_withdrawals, remaining_balance, monthly_balances, total_withdrawal_history

# Function to create SWP visualizations
def create_swp_visualizations(monthly_balances, total_withdrawal_history, initial_investment):
    months = len(monthly_balances)
    time_series = list(range(1, months + 1))

    # Plot Remaining Balance Over Time
    fig_balance = go.Figure()
    fig_balance.add_trace(go.Scatter(x=time_series, y=monthly_balances, mode='lines+markers', name='Remaining Balance'))
    fig_balance.update_layout(title='Remaining Balance Over Time', xaxis_title='Months', yaxis_title='Balance (₹)')
    
    # Plot Total Withdrawals Over Time
    fig_withdrawals = go.Figure()
    fig_withdrawals.add_trace(go.Scatter(x=time_series, y=total_withdrawal_history, mode='lines+markers', name='Total Withdrawals'))
    fig_withdrawals.update_layout(title='Total Withdrawals Over Time', xaxis_title='Months', yaxis_title='Withdrawals (₹)')
    
    # Plot Initial Investment vs Remaining Balance
    fig_comparison = go.Figure()
    fig_comparison.add_trace(go.Scatter(x=time_series, y=[initial_investment] * months, mode='lines', name='Initial Investment', line=dict(dash='dash')))
    fig_comparison.add_trace(go.Scatter(x=time_series, y=monthly_balances, mode='lines', name='Remaining Balance'))
    fig_comparison.update_layout(title='Initial Investment vs Remaining Balance', xaxis_title='Months', yaxis_title='Amount (₹)')

    return fig_balance, fig_withdrawals, fig_comparison

def create_swp_report(initial_investment, monthly_withdrawal, tax_rate, withdraw_years, total_withdrawals, after_tax_withdrawals, remaining_balance):
    # Create a DataFrame for the report
    df = pd.DataFrame({
        "Total Withdrawals (before tax)": [total_withdrawals],
        "Total Withdrawals (after tax)": [after_tax_withdrawals],
        "Remaining Balance": [remaining_balance],
    })

    # Define the file name
    file_name = f"swp_report_{initial_investment}_{monthly_withdrawal}_{tax_rate}_{withdraw_years}.xlsx"
    
    # Save the DataFrame to an Excel file
    df.to_excel(file_name, index=False)
    
    return file_name


def create_withdrawal_report(initial_investment, monthly_withdrawal, tax_rate, withdrawal_years):
    months = withdrawal_years * 12
    balance = initial_investment
    total_withdrawals = 0
    after_tax_withdrawals = 0

    # Monthly rate of return
    annual_rate_of_return = 0.12  # You can modify this as needed
    monthly_rate_of_return = annual_rate_of_return / 12

    # Create a list to hold the report data
    report_data = []

    for month in range(months):
        # Apply monthly compounding
        balance *= (1 + monthly_rate_of_return)

        # Determine the withdrawal amount and remaining balance
        if balance >= monthly_withdrawal:
            current_withdrawal = monthly_withdrawal
            balance -= monthly_withdrawal
        else:
            current_withdrawal = balance
            balance = 0  # Set balance to zero after withdrawal

        # Calculate tax and after-tax withdrawal
        tax = (current_withdrawal * tax_rate) / 100
        after_tax_withdrawal = current_withdrawal - tax

        # Update total withdrawals and after-tax withdrawals
        total_withdrawals += current_withdrawal
        after_tax_withdrawals += after_tax_withdrawal

        # Store the data for the report
        report_data.append({
            "Month": month + 1,
            "Withdrawal Amount": current_withdrawal,
            "Tax Paid": tax,
            "After-tax Withdrawal": after_tax_withdrawal,
            "Remaining Balance": balance
        })

    # Create a DataFrame for the report
    report_df = pd.DataFrame(report_data)

    # Save the report to an Excel file
    file_name = f"swp_report_{initial_investment}_{monthly_withdrawal}_{tax_rate}_{withdrawal_years}.xlsx"
    report_df.to_excel(file_name, index=False)

    return file_name, report_df

