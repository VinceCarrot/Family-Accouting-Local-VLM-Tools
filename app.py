from fileinput import filename

from flask import Flask, render_template, jsonify, request
from werkzeug.utils import secure_filename

import subprocess

import os
import time
import json
import copy
import random
import tempfile

# 导入PDF分析模块
from scripts.src.tools.pdf_analyzer import (
    analyze,
    pdf_file_preprocess,
    save_transactions_to_cache,
    save_transactions_to_csv,
)

app = Flask(__name__)

AppData = None

@app.route("/")
def home():
    return render_template('index.html')


@app.route('/upload_appdata', methods=['POST'])
def upload_appdata():
    """接收前端AppData"""
    global AppData
    AppData = request.json
    print("📥 AppData received in backend")

    # print("✅ AppData content:", AppData)
    return jsonify({"status": "ok"})


@app.route('/api/analyze_pdf', methods=['POST'])
def analyze_pdf():
    """PDF分析API"""
    if 'file' not in request.files or not request.files['file']:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files['file']
    account = request.form.get('account', '')
    year = request.form.get('year', '')
    month = request.form.get('month', '')

    
    # 文件预处理和验证
    # print("📥 Received file:", file.filename)
    preprocess_result = pdf_file_preprocess(file, file.filename, account, year, month)
    # print("🔍 Preprocess result:", preprocess_result)
    if not preprocess_result.get("success"):
        return jsonify(preprocess_result), 400
    
    temp_file = preprocess_result["file_path"]
    
    try:
        result = analyze(temp_file, account, year, month, AppData)
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
    finally:
        # 确保临时PDF文件一定被删除
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass


@app.route('/api/load_filled_transactions', methods=['POST'])
def load_filled_transactions():
    """Load a batch-generated transaction JSON file for manual review."""
    uploaded_file = request.files.get('file')
    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({"success": False, "error": "No JSON file provided"}), 400

    try:
        payload = json.load(uploaded_file.stream)
        transactions = payload.get('filled_transactions') if isinstance(payload, dict) else payload
        account = request.form.get('account', '')
        year = int(request.form.get('year', ''))
        month = int(request.form.get('month', ''))
        if not isinstance(transactions, list) or any(not isinstance(item, dict) for item in transactions):
            raise ValueError("filled_transactions must be a list of objects")
        if not isinstance(account, str) or not account.strip():
            raise ValueError("account is required")
        if year < 1 or not 1 <= month <= 12:
            raise ValueError("year or month is invalid")

        return jsonify({
            "success": True,
            "data": transactions,
            "year": year,
            "month": month,
            "account": account,
        }), 200
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as error:
        return jsonify({"success": False, "error": f"Invalid transaction JSON: {error}"}), 400


@app.route('/api/save_transactions', methods=['POST'])
def save_transactions():
    """保存当前表格内容并更新 category_cache.json。"""
    global AppData

    try:
        payload = request.get_json(silent=True) or {}
        transactions = payload.get('filled_transactions', [])
        account = payload.get('account', '') or ''
        year = payload.get('year', '') or ''
        month = payload.get('month', '') or ''

        if not AppData:
            AppData = {}

        result = save_transactions_to_cache(
            transactions=transactions,
            account=account,
            app_data=AppData,
            cache_path=os.path.join(os.path.dirname(__file__), 'static', 'data', 'category_cache.json'),
        )
        history_path = save_transactions_to_csv(
            transactions=transactions,
            account=account,
            year=year,
            month=month,
            history_dir=os.path.join(os.path.dirname(__file__), 'static', 'data', 'transaction_history'),
        )
        result['transaction_history_path'] = os.path.relpath(
            history_path,
            os.path.dirname(__file__),
        )
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    SERVER_NAME = "127.0.0.1"
    PORT = 5001
    app.run(
        host = SERVER_NAME,
        port = PORT,
        debug=True
    )
