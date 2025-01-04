import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
from typing import Dict, List
from utils import (
    calculate_sip,
    calculate_break_even,
    calculate_swp,
    create_investment_growth_report,
    create_swp_report,
    convert_df_to_excel,
    initialize_qa_bot,
    get_answer
)
import intel_extension_for_pytorch as ipex
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch
from huggingface_hub import login
import logging
import os
import gc
import sys
import logging
import torch
from datetime import datetime
from typing import Dict, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from dataclasses import dataclass
from enum import Enum
import re
login(token="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")

# from bot import initialize_chatbot
# Set page configuration
st.set_page_config(
    page_title="Investment Calculator",
    page_icon="💰",
    layout="wide"
)

@st.cache_resource
def load_qa_system():
    return initialize_qa_bot()

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


class BackendType(Enum):
    CUDA = "cuda"
    MPS = "mps"
    CPU = "cpu"
    ROCM = "rocm"
    IPEX = "ipex"

@dataclass
class BackendConfig:
    device_type: BackendType
    quantization_supported: bool
    max_memory: Optional[float] = None
    device_name: Optional[str] = None

class MultiBackendLlama:
    def __init__(self):
        self.logger = self._setup_logging()
        self.backend = self._detect_backend()
        self.logger.info(f"Initialized with backend: {self.backend.device_type.value}")
        self._initialize_model()

    
    def _detect_backend(self) -> BackendConfig:
        """Detect and configure the best available backend"""
        try:
            # Check CUDA
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                max_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                return BackendConfig(
                    device_type=BackendType.CUDA,
                    quantization_supported=True,
                    max_memory=max_memory,
                    device_name=device_name
                )
            
            # Check MPS (Apple Silicon)
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return BackendConfig(
                    device_type=BackendType.MPS,
                    quantization_supported=False,
                    device_name="Apple Silicon"
                )
            
            # Check for IPEX (Intel)
            elif os.environ.get('INTEL_EXTENSION_FOR_PYTORCH', False):
                return BackendConfig(
                    device_type=BackendType.IPEX,
                    quantization_supported=True,
                    device_name="Intel CPU/GPU"
                )
            
            # Fallback to CPU
            else:
                return BackendConfig(
                    device_type=BackendType.CPU,
                    quantization_supported=False,
                    device_name="CPU"
                )
                
        except Exception as e:
            self.logger.warning(f"Error detecting backend: {str(e)}. Falling back to CPU.")
            return BackendConfig(
                device_type=BackendType.CPU,
                quantization_supported=False,
                device_name="CPU"
            )

    def _get_device_map(self):
        """Generate appropriate device map based on backend"""
        if self.backend.device_type == BackendType.CUDA:
            return {
                'model.embed_tokens': 'cpu',
                'model.norm': 'cpu',
                'lm_head': 'cpu',
                'model.layers.0': 'cuda:0',
                'model.layers.1': 'cuda:0',
                'model.layers.2': 'cuda:0',
                'model.layers.3': 'cpu',
                'model.layers.4': 'cpu',
                'model.layers.5': 'cpu'
            }
        return "auto"

    def _get_quantization_config(self):
        """Get quantization configuration based on backend support"""
        if not self.backend.quantization_supported:
            return None
            
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True
        )

    def _initialize_model(self):
        """Initialize the model with backend-specific configurations"""
        try:
            self.model_name = "meta-llama/Llama-2-7b-chat-hf"
            
            # Initialize tokenizer
            self.logger.info("Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                model_max_length=256
            )
            
            # Prepare model configuration
            model_kwargs = {
                "torch_dtype": torch.float16 if self.backend.device_type != BackendType.CPU else torch.float32,
                "device_map": self._get_device_map(),
                "offload_folder": "offload_folder",
                "offload_state_dict": True,
                "low_cpu_mem_usage": True
            }
            
            # Add quantization if supported
            quant_config = self._get_quantization_config()
            if quant_config:
                model_kwargs["quantization_config"] = quant_config
            
            # Load model
            self.logger.info(f"Loading model with {self.backend.device_type.value} backend...")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                **model_kwargs
            )
            
            # Backend-specific optimizations
            self._apply_backend_optimizations()
            
        except Exception as e:
            self.logger.error(f"Error initializing model: {str(e)}")
            raise

    def _apply_backend_optimizations(self):
        """Apply backend-specific optimizations"""
        self.model.eval()
        
        if self.backend.device_type == BackendType.CUDA:
            torch.cuda.empty_cache()
            torch.backends.cudnn.benchmark = True
        elif self.backend.device_type == BackendType.IPEX:
            # import intel_extension_for_pytorch as ipex
            self.model = ipex.optimize(self.model)

    def __call__(self, inputs: Dict[str, str]) -> Dict[str, str]:
        try:
            self.logger.info("Starting inference...")
            
            prompt = f"""<s>[INST] You are a helpful investment advisor chatbot. 
            Please answer the following question:
            {inputs['input']} [/INST]"""
            
            # Memory cleanup
            if self.backend.device_type == BackendType.CUDA:
                torch.cuda.empty_cache()
                gc.collect()
            
            # Tokenize
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128
            )
            
            # Move inputs to appropriate device
            device = self.backend.device_type.value
            if device == "cuda":
                inputs = {k: v.to('cuda:0') if k == 'input_ids' else v.to('cpu') 
                         for k, v in inputs.items()}
            else:
                inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # Generate response
            outputs = self.model.generate(
                inputs['input_ids'],
                max_new_tokens=64,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                num_beams=1,
                no_repeat_ngram_size=3,
                early_stopping=True,
                use_cache=True
            )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            response = response.split("[/INST]")[-1].strip()
            
            return {"output": response}
            
        except Exception as e:
            self.logger.error(f"Error during inference: {str(e)}")
            return {"output": f"I apologize, but I encountered an error: {str(e)}"}

    def __del__(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up resources...")
        if self.backend.device_type == BackendType.CUDA:
            torch.cuda.empty_cache()
        gc.collect()

# Setup logging function remains the same
def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')

    logger = logging.getLogger('ChatbotLogger')
    logger.setLevel(logging.DEBUG)

    log_filename = f'logs/chatbot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

class LLMChatbot:
    def __init__(self, model_name="meta-llama/Llama-3.3-70B-Instruct"):
        """Initialize the Llama chatbot with HuggingFace authentication."""
        try:
            logger.info(f"Loading {model_name} model and tokenizer...")
            
            # Initialize tokenizer with trust_remote_code for Llama
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True,
                use_auth_token=True
            )
            
            # Initialize model with specific configuration for Llama
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                trust_remote_code=True,
                use_auth_token=True,
                torch_dtype=torch.float16,  # Use float16 for memory efficiency
                device_map="auto",  # Automatically handle model placement
                load_in_8bit=True  # Use 8-bit quantization to reduce memory usage
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.system_prompt = """<s>[INST] You are a clear and concise financial advisor. 
            When answering questions, follow these guidelines:
            
            1. Keep responses under 250 words
            2. Use simple, clear language
            3. Structure answers with:
               - Brief definition
               - Key benefits
               - Important considerations
            4. Focus on practical, actionable information
            
            Current question: {user_input} [/INST]"""
            
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Model initialized successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Error initializing model: {str(e)}", exc_info=True)
            raise
    
    def generate_response(self, user_input, max_new_tokens=150):
        """Generate a response using the Llama model."""
        try:
            # Format prompt according to Llama instruction format
            full_prompt = self.system_prompt.format(user_input=user_input)
            
            # Tokenize with Llama-specific parameters
            inputs = self.tokenizer(
                full_prompt,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512,  # Limit input length
                add_special_tokens=True,
                return_attention_mask=True
            ).to(self.device)
            
            # Generate response with Llama-optimized parameters
            outputs = self.model.generate(
                input_ids=inputs.input_ids,
                attention_mask=inputs.attention_mask,
                max_new_tokens=max_new_tokens,
                num_return_sequences=1,
                pad_token_id=self.tokenizer.pad_token_id,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                top_k=40,
                repetition_penalty=1.1,
                no_repeat_ngram_size=3,
                early_stopping=True
            )
            
            # Decode and clean response
            response = self.tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1]:],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True
            )
            
            # Clean up response
            response = self._clean_response(response)
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return "I apologize, but I encountered an error. Please try asking your question again."
    
    def _clean_response(self, response):
        """Clean and format the response."""
        # Remove Llama instruction tokens and format markers
        response = re.sub(r'\[/INST\]|\[INST\]', '', response)
        response = re.sub(r'<s>|</s>', '', response)
        
        # Remove multiple newlines and spaces
        response = re.sub(r'\n\s*\n', '\n\n', response)
        
        # Ensure response doesn't exceed 250 words
        words = response.split()
        if len(words) > 250:
            response = ' '.join(words[:250]) + '...'
        
        return response.strip()
    
    def _is_finance_related(self, response):
        """Check if the response is related to finance and investments."""
        finance_keywords = [
            'invest', 'finance', 'money', 'market', 'stock', 'bond', 'sip', 'swp',
            'portfolio', 'return', 'risk', 'fund', 'equity', 'debt', 'asset',
            'dividend', 'interest', 'capital', 'wealth', 'financial'
        ]
        
        response_lower = response.lower()
        return any(keyword in response_lower for keyword in finance_keywords)

# The rest of the code (initialize_chatbot and run_chatbot_section) remains the same
def initialize_chatbot():
    """Initialize the chatbot with Llama model."""
    logger.info("Starting Llama chatbot initialization...")
    try:
        # Clear GPU memory before initialization
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            logger.info("GPU memory cleared")
            
            # Log GPU information
            gpu_name = torch.cuda.get_device_name(0)
            total_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info(f"Using GPU: {gpu_name}")
            logger.info(f"Total GPU Memory: {total_memory:.2f} GB")
            
            st.success(f"Using GPU: {gpu_name}")
            st.info(f"Total GPU Memory: {total_memory:.2f} GB")
        
        logger.info("Creating Llama Chatbot instance...")
        chatbot = LLMChatbot()
        logger.info("Chatbot initialization successful")
        return chatbot
        
    except Exception as e:
        logger.error("Failed to initialize chatbot", exc_info=True)
        st.error(f"Error initializing chatbot: {str(e)}")
        return None
    
def run_chatbot_section():
    st.header("💬 Investment & Finance Chatbot")
    st.write("Ask me about investments, SIP, SWP, and financial planning!")

    if os.path.exists('logs'):
        log_files = [f for f in os.listdir('logs') if f.endswith('.log')]
        if log_files:
            latest_log = max(log_files, key=lambda x: os.path.getctime(os.path.join('logs', x)))
            st.info(f"Debug logs are being written to: logs/{latest_log}")

    @st.cache_resource
    def get_chatbot():
        return initialize_chatbot()

    chatbot = get_chatbot()

    # Initialize chat history if not exists
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Initialize message keys if not exists
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.chat_history:
            st.markdown(
                f"""<div style='background-color: #000000; color: #00FF00; padding: 10px; border-radius: 5px; margin-bottom: 10px; font-family: monospace;'>
                    <b>You:</b> {message['question']}
                </div>""",
                unsafe_allow_html=True
            )
            st.markdown(
                f"""<div style='background-color: #000000; color: #00FF00; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-family: monospace;'>
                    <b>Bot:</b> {message['answer']}
                </div>""",
                unsafe_allow_html=True
            )

    # Get user input
    if prompt := st.chat_input("Ask about investments, SIP, SWP, or financial planning..."):
        if chatbot:
            try:
                logger.info(f"Processing user query: {prompt}")
                
                # Add user message to chat history
                st.markdown(
                    f"""<div style='background-color: #000000; color: #00FF00; padding: 10px; border-radius: 5px; margin-bottom: 10px; font-family: monospace;'>
                        <b>You:</b> {prompt}
                    </div>""",
                    unsafe_allow_html=True
                )

                # Generate response with spinner
                with st.spinner("Thinking..."):
                    response = chatbot.generate_response(prompt)
                    formatted_response = response.replace("\n", "\n\n")

                # Display bot response
                st.markdown(
                    f"""<div style='background-color: #000000; color: #00FF00; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-family: monospace;'>
                        <b>Bot:</b> {formatted_response}
                    </div>""",
                    unsafe_allow_html=True
                )

                # Update chat history
                st.session_state.chat_history.append({
                    "question": prompt,
                    "answer": formatted_response
                })

                logger.info("Response generated and chat history updated")

            except Exception as e:
                logger.error(f"Error during chat interaction: {str(e)}", exc_info=True)
                st.error(f"An error occurred: {str(e)}")
        else:
            logger.error("Chatbot is not initialized")
            st.error("Chatbot initialization failed. Check logs for details.")

if __name__ == "__main__":
    run_chatbot_section()
