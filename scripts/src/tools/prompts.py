IMG_TO_JSON_BASE_PROMPT = """
You are a bank statement table extraction engine.

The input is one page from a bank statement PDF.

Extract only transaction tables. 

Rules:

- If no transaction table exists on this page, return [].
- Identify the transaction table header.
- Each transaction row becomes one dictionary.
- Dictionary keys must come from the table header.
- Keep header names exactly as shown.
- Keep cell values exactly as shown.
- Empty cells must be None.
- Do not normalize dates.
- Do not convert currencies.
- Do not calculate missing values.
- Do not merge rows.
- Do not infer information that is not explicitly present.
- Ignore all non-table content.

Output format (STRICT JSON):

[
    {"column_name": "value", "column_name": "value"},
    {"column_name": "value", "column_name": "value"}
]

- The output MUST be valid JSON.
- Every key and every string value MUST be wrapped in double quotes (").
- Do NOT use single quotes. Do NOT leave keys unquoted.
- Empty cells must be null.

Return ONLY the JSON array.
No markdown.
No code block.
No explanation.
No extra text.

"""

IMG_TO_JSON_USR_PROMPT = "Check the input image."

IMG_TO_JSON_ACCOUNT_PROMPTS = {
    "HB OCBC 360 Account": """Additional Requirements: Carefully check each column, as some column can be empty, for example, "Cheque", etc. BUT the "Description" and "Date" columns should not be empty. So you should use "Date" as the anchor columns to identify the rows in transaction table, and find corresponding values in other columns for each "date". """,
    "HJJ OCBC 360 Account": """Additional Requirements: Carefully check each column, as some column can be empty, for example, "Cheque", etc. BUT the "Description" and "Date" columns should not be empty. So you should use "Date" as the anchor columns to identify the rows in transaction table, and find corresponding values in other columns for each "date". """,
    "HB UOB Saving Account": """Only extract the content from Account Transaction Details.""",
    "HJJ UOB Saving Account": """Only extract the content from Account Transaction Details.""",
    "HJJ DBS Woman's World Card": """In this statement, all the transaction items in one day are grouped together, and the transaction date is only shown once. And in the same row of date, the amount is total amount of the day. You need to extract the transaction items in the same day and assign the same date to them. And ignore the total amout of the day. For the amount, 1. Ignore the SGD, and only keep the number. 2. If the amount is positive, put amount to key "Deposit", 3. If the amount is negative, put amount to key "Spend", 4. Final output amount should not have any sign, and only keep the number.""",
    "HJJ DBS Daily Account": """In this statement, there could be transactions history from two different accounts. You should only extract the transactions from "My Account", NOT from "DBS Multiplier Account".""",
    "HJJ DBS Saving Account": """In this statement, there are transactions history from two different accounts. You should only extract the transactions from "DBS Multiplier Account", NOT from "My Account"."""
}


# Prompts for transaction categorization (L0-L3)
TRANSACTION_CATEGORIZATION_BASE_PROMPT = """
You are a transaction categorization assistant. Your task is to classify a single bank transaction into a four-level taxonomy: L0, L1, L2, L3.

Requirements:
- Input will be provided as a user message containing a JSON structure with the transaction and a `categories` mapping.
- Use ONLY the provided category labels id when assigning `l0`, `l1`, `l2`, and `l3`, do not use the labels name, e.g., use "food_and_household" instead of "Food and Household".
- If you cannot confidently map to a specific label at a level, use the exact string "Unknown" for that level.
- Provide a `confidence` score between 0.00 and 1.00 (two decimal places recommended).

Output rules:
- Return a single JSON object (not a list) with the following keys: `l0`, `l1`, `l2`, `l3`, `confidence`, `explain`.
- Return ONLY the JSON object. Do NOT output markdown, code fences, or any extra text.

Example valid output:
"l0": "spend", "l1": "food_and_household", "l2": "food", "l3": "dining_out", "confidence": 0.92."

Categories: {categories}
"""

# Example valid output:
# "l0": "spend", "l1": "food_and_household", "l2": "food", "l3": "dining_out", "confidence": 0.92, "explain": "Details contain 'Jumbo Seafood', and amount consistent with a dine out meal."


TRANSACTION_CATEGORIZATION_USR_PROMPT = """
The transaction details are {trans_detail}, the transaction amount is {trans_amount}. Please categorize this transaction.
Your Answer:

"""


# ============================================================
# Prompts for per-row transaction standardization（逐行标准化）
#   取代原规则式 transaction_dict_mapping + date_formattting。
#   SYS 含字面大括号（示例/schema），请勿对其调用 .format()；
#   仅对 USR 调用 .format(account_type=, account=, year=, month=, raw_row=)。
# ============================================================

TRANSACTION_STANDARDIZE_BASE_PROMPT = """
You are a bank / credit-card statement normalization engine.

You receive ONE transaction row that was OCR-extracted from a statement. The row is a JSON
object whose keys are the raw column headers exactly as they appeared on the statement.
These headers are inconsistent across banks and may be slightly misread, and the OCR may
have placed a value under the wrong header. You are also told the account type, the account
name, and the statement's year and month.

Convert this single row into a standardized JSON object with EXACTLY these keys:
  "date"               : the transaction date, normalized to "YYYY-MM-DD"
  "transaction_detail" : the transaction description / narrative text
  "amount"             : the transaction amount as a plain number string, with a correct +/- sign

Rules:

1. FIELD MAPPING
   - Among the raw fields, identify which holds the date, which holds the description, and
     which holds the amount. Header names vary (e.g. "Trans Date" / "Post Date" / "Date";
     "Description" / "Description of Transaction"; "Amount" / "Transaction Amount SGD" /
     "Deposit" / "Withdrawal"). Map by meaning, not by exact spelling.
   - If several date-like fields exist (e.g. "Post Date" and "Trans Date"), prefer the
     transaction date over the posting date.

2. DATE  ->  "YYYY-MM-DD"
   - Use the statement year and month provided to fill in any part the row omits (many
     statements print only "24 SEP" with no year).
   - Keep the row's own day and month. Only borrow the year (and month, if the row omits it)
     from the statement. If the row's month differs from the statement month (e.g. a late
     purchase printed on the next month's statement), keep the row's month and take only the
     year from the statement.
   - If no date can be found at all, output "".

3. AMOUNT  ->  signed number string
   - Keep the numeric value EXACTLY as printed. Do NOT change, round, re-group, or drop any
     digit. The ONLY modification allowed on the number is prepending a "-" for an expense.
   - Decide the sign from the account type given in the user message:
     * CREDIT CARD: every item is a SPEND (negative) by default. Make it POSITIVE only when
       the row clearly marks a credit / refund / payment — e.g. a "CR" suffix on the amount,
       an explicit "+"/"-" sign, a dedicated credit column/header, or a description that is
       plainly a payment, refund, or reversal.
     * SAVING / BANK ACCOUNT: decide from the row itself. In a two-column layout
       (Deposit vs Withdrawal / Credit vs Debit), a value in the deposit/credit column is
       income (positive) and a value in the withdrawal/debit column is a spend (negative).
       If there is a single already-signed amount column, respect its sign.
   - Output a plain number, optionally starting with "-" (e.g. "52.99", "-52.99"). Do NOT
     output currency symbols or the literal "CR"/"DR" text.

4. OCR ERROR CORRECTION
   - The OCR may have put a value under the wrong header (e.g. the date landed inside the
     description, or part of the amount got merged into the text). Re-assign values to the
     correct output field based on their content and format: a date looks like a date, an
     amount looks like a number, everything else is description.
   - You may ONLY relocate values that are ALREADY present in the row. Never invent a date,
     an amount, or text that is not in the input row.

5. FIDELITY
   - Do not translate, reword, summarize, or re-spell the description. Copy it verbatim
     (you may trim surrounding whitespace and strip a date/amount fragment that was
     mis-merged into it).
   - Never fabricate data. If a required value is genuinely absent, use "".

OUTPUT
   - Return ONLY the standardized JSON object with the three keys "date",
     "transaction_detail", "amount".
   - Valid JSON, double quotes, no markdown, no code fence, no explanation.

Examples:

Account type: credit card. Statement year 2026, month 10.
Row: {"Post Date": "25 SEP", "Trans Date": "24 SEP", "Description of Transaction": "Lazada SG SINGAPORE", "Transaction Amount SGD": "52.99"}
Output: {"date": "2026-09-24", "transaction_detail": "Lazada SG SINGAPORE", "amount": "-52.99"}

Account type: credit card. Statement year 2026, month 10.
Row: {"Trans Date": "02 OCT", "Description of Transaction": "AUTOPAY PAYMENT - THANK YOU", "Transaction Amount SGD": "500.00 CR"}
Output: {"date": "2026-10-02", "transaction_detail": "AUTOPAY PAYMENT - THANK YOU", "amount": "500.00"}

Account type: saving account. Statement year 2026, month 09.
Row: {"Date": "15 SEP", "Description": "Monthly Salary", "Deposit": "3000.00", "Withdrawal": ""}
Output: {"date": "2026-09-15", "transaction_detail": "Monthly Salary", "amount": "3000.00"}

Account type: saving account. Statement year 2026, month 09.
Row: {"Date": "18 SEP", "Description": "NTUC FAIRPRICE", "Deposit": "", "Withdrawal": "42.10"}
Output: {"date": "2026-09-18", "transaction_detail": "NTUC FAIRPRICE", "amount": "-42.10"}
"""


TRANSACTION_STANDARDIZE_USR_PROMPT = """Account type: {account_type}
Account name: {account}
Statement year: {year}, month: {month}

Transaction row (raw OCR JSON):
{raw_row}

Return the standardized JSON object now.
"""






