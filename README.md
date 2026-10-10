# Family Accounting Local PDF Tools

`WebUI_Local` is a Flask application for extracting transactions from bank statement PDFs with an Ollama vision model, reviewing the extracted transactions, and saving approved records to transaction history. It can process one statement at a time through the browser or run a configured batch from the command line.

## Sidebar Pages

- **Load Statements**: Select an account, statement year and month, then process one PDF or load a transaction JSON file for review. Edit extracted transaction details/categories and save the reviewed transactions.
- **Input Transactions**: A navigation entry reserved for transaction input. Its page template is currently empty; the active statement review workflow is under Load Statements.

## Requirements

- Python 3.11 or compatible, with packages from `requirements.txt`.
- Poppler, required by `pdf2image` to convert PDF pages to images. On Ubuntu/WSL:

  ```bash
  sudo apt install poppler-utils
  ```

- Ollama reachable from the Python environment, with the model used by the analyzer available:

  ```bash
  ollama pull qwen3-vl:8b
  ```

- A running `WebUI_Server` instance. The Local app obtains accounts, categories, and other shared data from its `/get_appdata` endpoint. Open the Server UI at least once so it can load and publish that data to the Server process.

Install and start the Local app from this directory:

```bash
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5001>.

### Configure Local Settings

The following files are loaded from `static/data/` and are not included in Git. Create or restore these files locally before using the app:

- `account_format.json`: Per-account statement parsing rules, including the statement date format and source-column-to-transaction-field mappings (`key_mappings`). Use the account names shown in the Server data and configure mappings for each bank statement format you process.
- `pdf_pwd.json`: A JSON object mapping account display names to PDF passwords. Use `{}` when none of your statements are password-protected.
- `category_cache.json`: The Local app's learned account/category mappings. Use `{}` for a fresh cache; it is updated as transactions are reviewed and saved.

The browser currently fetches shared data from `http://192.168.1.33:5000/get_appdata`, as configured in `static/js/app.js`. Change that URL to the address of your `WebUI_Server` if it differs. The batch script has a separate override, `SPENDLOG_APPDATA_URL`, described below.

## Process One PDF Through the UI

1. Start `WebUI_Server` and `WebUI_Local`, and make sure the Local app can reach the Server and Ollama.
2. In **Load Statements**, select the account, statement year, and month.
3. Select or drop one PDF. The **Change statement folder** control can set a default statement root in supported browsers; otherwise, choose the PDF directly.
4. Select **Process Statement** and wait for extraction. Review and correct the transaction rows and categories.
5. Select **Save** to update the local category cache and append the reviewed transactions to `static/data/transaction_history/{year}/{month}/` as CSV.

## Process PDFs in a Batch

Batch processing runs `main_pdf_batch_process.py`. It reads jobs from `batch_input_config.json` in the `WebUI_Local` directory. Each job identifies the account and the statement PDF's year, month, and exact filename. The PDF must be stored under `estatements/{year}/{month:02d}/{secure_filename(account)}/`.

Create a local `batch_input_config.json` like this, replacing the example values:

```json
[
  {
    "year": 2026,
    "month": 1,
    "account": "Everyday Account",
    "source_pdf": "statement-january.pdf"
  }
]
```

The `account` must match an account name supplied by `WebUI_Server`. The script finds the PDF by exact filename inside that account's statement folder. It fetches shared data from the Server endpoint; override the script's default URL if needed:

```bash
SPENDLOG_APPDATA_URL="http://<server-host>:5000/get_appdata" python main_pdf_batch_process.py
```

After each successful job, the script saves extracted transactions as JSON under the same account/year/month statement folder and checkpoints unfinished jobs in `batch_input_config_remaining.json`. A later run prefers the remaining-jobs file to resume. To restart the original batch, remove that checkpoint file and run the script again. Load each generated transaction JSON in the UI's **Load Statements** page to review and save it to CSV transaction history.

