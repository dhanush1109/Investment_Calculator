import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import boto3
from io import BytesIO
import os
import io
import torch
from langchain_aws import ChatBedrock
from langchain.vectorstores import FAISS
from langchain.embeddings import SentenceTransformerEmbeddings
from langchain.schema import Document
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.llms import HuggingFacePipeline
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline, AutoModelForSeq2SeqLM
import warnings


# Suppress warnings
warnings.filterwarnings('ignore', category=FutureWarning)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'


# Load the FAISS index from the saved file
vectorstore_faiss = FAISS.load_local("INVSTMT_DB", SentenceTransformerEmbeddings(), allow_dangerous_deserialization=True)

# Load the embedding model again if necessary
embedding_function = SentenceTransformerEmbeddings(model_name="thenlper/gte-small")

def initialize_qa_bot():
    try:
        print("Loading models... This might take a minute on first run...")
        
        # Initialize the embedding model
        embedding_function = SentenceTransformerEmbeddings(model_name="thenlper/gte-small")
        
        # Load the saved FAISS index with safe loading enabled
        vectorstore = FAISS.load_local(
            "INVSTMT_DB", 
            embedding_function,
            allow_dangerous_deserialization=True
        )
        
        # Initialize a smaller, efficient model for text generation
        model_name = "facebook/bart-large-cnn"  # Can also use "google/flan-t5-small" for an even smaller model
        
        # Check if CUDA (GPU) is available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        
        # Load tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        model.to(device)
        
        # Create text generation pipeline
        pipe = pipeline(
            "text2text-generation",
            model=model,
            tokenizer=tokenizer,
            max_length=512,
            device=0 if device == "cuda" else -1,
        )
        
        # Convert pipeline to LangChain
        llm = HuggingFacePipeline(pipeline=pipe)
        
        # Create a custom prompt template
        prompt_template = """
        Based on the following context, answer the question. Be concise and accurate.
        If you can't find the answer in the context, say "I don't have enough information to answer that question."
        
        Context: {context}
        
        Question: {question}
        
        Answer:
        """
        
        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        # Create the retrieval chain
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
            return_source_documents=True,
            chain_type_kwargs={"prompt": PROMPT}
        )
        
        return qa_chain
    
    except Exception as e:
        print(f"\nError initializing QA bot: {str(e)}")
        print("\nPlease ensure:")
        print("1. The INVSTMT_DB directory exists in the current working directory")
        print("2. All required packages are installed:")
        print("   pip install langchain-community langchain transformers torch sentencepiece")
        return None

def get_answer(qa_chain, question: str):
    """
    Get answer for a question using the QA chain
    """
    if qa_chain is None:
        return "QA system is not properly initialized. Please check the error messages above."
    
    try:
        result = qa_chain({"query": question})
        
        # Extract the answer and source documents
        answer = result['result']
        source_docs = result['source_documents']
        
        # Format source information
        sources = []
        for doc in source_docs:
            sources.append(f"- {doc.metadata['qa_pair']} from {doc.metadata['filename']}")
        
        # Combine answer with sources
        response = f"""
Answer: {answer}

Sources:
{chr(10).join(sources)}
"""
        return response
    
    except Exception as e:
        return f"An error occurred while processing your question: {str(e)}"

    

def calculate_sip(monthly_contribution, annual_return_rate, investment_years):
    monthly_return_rate = annual_return_rate / 12
    total_months = investment_years * 12
    future_value = monthly_contribution * (((1 + monthly_return_rate) ** total_months - 1) / monthly_return_rate) * (1 + monthly_return_rate)
    total_invested = monthly_contribution * total_months
    investment_history = []  # Populate as needed
    contribution_history = []  # Populate as needed
    
    return future_value, total_invested, investment_history, contribution_history


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


def create_investment_growth_report(monthly_investment, annual_return_rate, investment_duration_years):
    """
    Create an Excel report for investment growth with a custom monthly and yearly breakdown.

    Parameters:
    monthly_investment (float): Monthly investment amount.
    annual_return_rate (float): Expected annual return rate as a percentage.
    investment_duration_years (int): Investment duration in years.

    Returns:
    bytes: Excel file content as bytes.
    """
    excel_buffer = BytesIO()

    # Setup monthly and yearly calculation parameters
    total_months = investment_duration_years * 12
    monthly_rate = (annual_return_rate / 12) / 100

    # Initialize investment report data
    investment_data = []
    monthly_balance = 0
    yearly_balance = 0
    year = 1

    # Calculate monthly and yearly balances
    for month in range(1, total_months + 1):
        monthly_balance += monthly_investment
        monthly_balance *= (1 + monthly_rate)

        # Accumulate yearly balance at the end of each year
        if month % 12 == 0:
            yearly_balance = monthly_balance
            year += 1

        # Append data for each month
        investment_data.append({
            'Month': month,
            'Monthly Balance': round(monthly_balance, 2),
            'Year': year if month % 12 != 0 else year - 1,
            'Yearly Balance': round(yearly_balance, 2) if month % 12 == 0 else '',
            'Monthly Investment': monthly_investment,
            'Expected Annual Return': annual_return_rate,
            'Investment Duration (Years)': investment_duration_years
        })

    # Create DataFrame for investment data
    investment_df = pd.DataFrame(investment_data)

    # Write to Excel with formatting
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        investment_df.to_excel(writer, sheet_name='Investment Report', index=False)
        
        # Format worksheet
        workbook = writer.book
        worksheet = writer.sheets['Investment Report']
        
        # Apply formatting for readability
        header_format = workbook.add_format({'bold': True, 'bg_color': '#f0f0f0', 'font_size': 12})
        currency_format = workbook.add_format({'num_format': '₹#,##0.00'})

        # Set column widths and apply header formatting
        for col_num, value in enumerate(investment_df.columns):
            worksheet.write(0, col_num, value, header_format)

        # Apply currency formatting to balance columns
        worksheet.set_column('B:B', 15, currency_format)
        worksheet.set_column('D:D', 15, currency_format)

    # Return the Excel file as bytes
    excel_buffer.seek(0)
    return excel_buffer.getvalue()



def create_swp_report(initial_investment, monthly_withdrawal, tax_rate, withdraw_years, total_withdrawals, after_tax_withdrawals, remaining_balance):
    # Create a BytesIO object to store the Excel file
    excel_buffer = BytesIO()
    
    # Create a Pandas Excel writer using the BytesIO buffer
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        # Create summary data
        summary_data = {
            'Parameter': ['Initial Investment', 'Monthly Withdrawal', 'Tax Rate', 'Withdrawal Duration',
                         'Total Withdrawals (Pre-tax)', 'Total Withdrawals (After-tax)', 'Remaining Balance'],
            'Value': [f'₹{initial_investment:,.2f}', f'₹{monthly_withdrawal:,.2f}', 
                     f'{tax_rate}%', f'{withdraw_years} years',
                     f'₹{total_withdrawals:,.2f}', f'₹{after_tax_withdrawals:,.2f}',
                     f'₹{remaining_balance:,.2f}']
        }
        
        # Write summary sheet
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
        
        # Get the xlsxwriter workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Summary']
        
        # Add formatting
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#f0f0f0'
        })
        
        # Apply formatting to the header row
        for col_num, value in enumerate(summary_data.keys()):
            worksheet.write(0, col_num, value, header_format)
    
    # Reset the buffer position to the start
    excel_buffer.seek(0)
    
    return excel_buffer.getvalue()

def calculate_swp(initial_investment, monthly_withdrawal, tax_rate, withdraw_years):
    months = withdraw_years * 12
    monthly_balances = []
    total_withdrawal_history = []  # This will store pre-tax withdrawal amounts
    after_tax_withdrawal_history = []  # This will store after-tax withdrawal amounts
    current_balance = initial_investment
    
    for month in range(months):
        # Calculate the tax on the monthly withdrawal
        tax = (monthly_withdrawal * tax_rate) / 100
        after_tax_withdrawal = monthly_withdrawal - tax  # Subtract tax instead of adding
        
        # Deduct the pre-tax withdrawal from the current balance
        current_balance -= monthly_withdrawal
        
        # Compound the remaining balance (1% monthly growth)
        current_balance *= (1 + 0.01)
        
        # Store the results
        monthly_balances.append(current_balance)
        total_withdrawal_history.append(monthly_withdrawal)  # Store pre-tax withdrawal
        after_tax_withdrawal_history.append(after_tax_withdrawal)  # Store after-tax withdrawal
    
    total_withdrawals = sum(total_withdrawal_history)  # Total pre-tax withdrawals
    after_tax_withdrawals = sum(after_tax_withdrawal_history)  # Total after-tax withdrawals
    remaining_balance = current_balance
    
    return total_withdrawals, after_tax_withdrawals, remaining_balance, monthly_balances, after_tax_withdrawal_history

def convert_df_to_excel(df):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # Write DataFrame to Excel
                df.to_excel(writer, sheet_name='Monthly Details', index=False)
                
                # Get workbook and worksheet objects
                workbook = writer.book
                worksheet = writer.sheets['Monthly Details']
                
                # Add formatting
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#D3D3D3',
                    'border': 1,
                    'text_wrap': True,
                    'valign': 'vcenter',
                    'align': 'center'
                })
                
                currency_format = workbook.add_format({
                    'num_format': '₹#,##0.00',
                    'border': 1
                })
                
                # Apply header format
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Set column widths
                worksheet.set_column('A:A', 10)  # Month column
                worksheet.set_column('B:E', 20)  # Other columns
                
                # Apply currency format to relevant columns
                for row in range(1, len(df) + 1):
                    worksheet.write_number(row, 1, df.iloc[row-1]['Withdrawal (before tax)'], currency_format)
                    worksheet.write_number(row, 2, df.iloc[row-1]['Withdrawal (after tax)'], currency_format)
                    worksheet.write_number(row, 3, df.iloc[row-1]['Tax Paid'], currency_format)
                    worksheet.write_number(row, 4, df.iloc[row-1]['Remaining Balance'], currency_format)
            
            buffer.seek(0)
            return buffer

