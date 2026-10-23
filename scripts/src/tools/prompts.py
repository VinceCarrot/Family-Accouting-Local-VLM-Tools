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






