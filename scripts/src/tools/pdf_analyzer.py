from typing import Dict, Any, Optional, List, Union

from PIL.Image import Image
import logging
import os
import time
import tempfile
from datetime import datetime
from werkzeug.utils import secure_filename
import PyPDF2
from pdf2image import convert_from_path

import json
import csv
import ast
import re
from scripts.src.tools.llm_tools import dict_substr_lookup, dict_multi_substr_lookup, imgs_to_json, transactions_categorization, transactions_standardization

logger = logging.getLogger(__name__)


def pdf_file_preprocess(file, filename: str, account: str, year: str, month: str) -> Dict[str, Any]:
    """
    预处理PDF文件：验证、保存临时文件
    
    Args:
        file: 上传的文件对象
        filename: 文件名
        account: 账户
        year: 年份
        month: 月份
    
    Returns:
        {"success": True/False, "file_path": "...", "error": "..."}
    """
    # 验证文件名后缀
    if not filename.lower().endswith('.pdf'):
        return {"success": False, "error": "Only PDF files supported"}
    
    # 验证account
    if not account:
        return {"success": False, "error": "Account required"}
    
    try:
        # 保存临时文件
        temp_file = os.path.join(
            tempfile.gettempdir(),
            f"{int(time.time()*1000)}_{secure_filename(filename)}"
        )
        file.save(temp_file)
        logger.info(f"PDF file saved to: {temp_file}")
        
        return {
            "success": True,
            "file_path": temp_file
        }
    except Exception as e:
        logger.error(f"Error preprocessing PDF: {str(e)}")
        return {"success": False, "error": str(e)}


def save_images(images: List[Image], output_dir: str, prefix: str = "page") -> Optional[List[str]]:
    """
    将图片列表保存为JPG文件
    
    Args:
        images: PIL Image 对象列表
        output_dir: 输出目录
        prefix: 文件名前缀，如 "page" 会生成 page_1.jpg, page_2.jpg 等
    
    Returns:
        保存的文件路径列表，失败返回None
    
    Example:
        images = read_pdf("statement.pdf")
        paths = save_images(images, "/tmp/pdf_output", prefix="statement")
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        saved_paths = []
        for i, img in enumerate(images, 1):
            # 转换为RGB格式（确保JPG兼容）
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            file_path = os.path.join(output_dir, f"{prefix}_{i}.jpg")
            img.save(file_path, "JPEG", quality=95)
            saved_paths.append(file_path)
            logger.info(f"Saved image: {file_path}")
        
        logger.info(f"Successfully saved {len(saved_paths)} images to {output_dir}")
        return saved_paths
        
    except Exception as e:
        logger.error(f"Error saving images: {str(e)}")
        return None


def read_pdf(file_path: str, password: Optional[str] = None) -> Optional[List[Image]]:
    """
    读取PDF文件，将每一页转换为图片
    
    Args:
        file_path: PDF文件路径
        password: PDF密码（可选）
    
    Returns:
        图片对象列表，每个元素代表PDF的一页（PIL Image格式）
        返回None表示读取失败
    
    Example:
        images = read_pdf("statement.pdf", password="123456")
        if images:
            for i, img in enumerate(images):
                img.save(f"page_{i+1}.jpg", "JPEG")
    """
   
    # 验证文件存在
    if not os.path.exists(file_path):
        logger.error(f"PDF file not found: {file_path}")
        return None
    
    
   
    logger.info(f"Converting PDF to images: {file_path}")
    
    kwargs = {
        'dpi': 200
    }

    if password:
        kwargs['userpw'] = password # pdf2image的参数名是userpw 
    
    try:
        # print(f"DEBUG: file_path={file_path}, password={password}")  # 调试
        images = convert_from_path(file_path, userpw=password)
        # print(len(images))
        return images
    except Exception as e:
        logger.error(f"Error converting PDF to images: {str(e)}")
        # print(f"DEBUG: Exception type: {type(e)}, Full error: {e}")  # 调试：打印完整错误
        return None
    

def process_imgs(
    img_paths: List[str],
    account: str,
    keep_alive: Optional[Union[int, str]] = None,
) -> Optional[Dict[str, Any]]:
    """将图片路径转换为JSON格式，供LLM分析使用"""

    transactions = imgs_to_json(img_paths, account, keep_alive=keep_alive)
    return transactions


def str_to_dict(transaction_str: List[str]) -> List[Dict[str, Any]]:
    """将LLM返回的字符串转换为字典列表"""
    transaction_dict_list = []
   
    def _strip_to_json_array(text):
        """去掉可能的 ``` 围栏/前后杂文本，截取最外层 [...] 区间。"""
        if not isinstance(text, str):
            return text
        s = text.strip()
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
        start = s.find("[")
        end = s.rfind("]")
        if start != -1 and end != -1 and end > start:
            s = s[start:end + 1]
        return s

    def _quote_bare_keys(text):
        """给形如 {Post Date: ...} 的裸键补双引号（模型偶发不加引号时的兜底）。"""
        return re.sub(
            r'([{,]\s*)([^"\'\s{}\[\],][^:{}\[\],]*?)\s*:',
            lambda m: f'{m.group(1)}"{m.group(2).strip()}":',
            text,
        )

    def _parse_one_page(page_str):
        """单页输出解析为 list，依次尝试多种策略，全失败才抛出。"""
        cleaned = _strip_to_json_array(page_str)
        # 1) 标准 JSON（双引号键值）
        try:
            return json.loads(cleaned)
        except Exception:
            pass
        # 2) Python 字面量（单引号键值）
        try:
            return ast.literal_eval(cleaned)
        except Exception:
            pass
        # 3) 裸键补引号后按 JSON 解析
        try:
            return json.loads(_quote_bare_keys(cleaned))
        except Exception:
            pass
        # 4) 裸键补引号后按 Python 字面量解析（可容纳单引号值）
        return ast.literal_eval(_quote_bare_keys(cleaned))

    # transaction_str 为各页响应字符串组成的列表；兼容传入单个字符串
    if isinstance(transaction_str, str):
        page_str_list = [transaction_str]
    else:
        page_str_list = list(transaction_str)

    for idx, page_str in enumerate(page_str_list, start=1):
        try:
            transaction_dicts = _parse_one_page(page_str)
        except Exception as e:
            logger.error(f"Failed to parse OCR page {idx}, skipped. Error: {e}")
            logger.debug(f"Unparseable page {idx} content: {page_str}")
            continue

        if not isinstance(transaction_dicts, list) or any(
            not isinstance(transaction, dict) for transaction in transaction_dicts
        ):
            logger.error(f"OCR page {idx} is not a list of objects, skipped.")
            continue

        transaction_dict_list.extend(transaction_dicts)

    return transaction_dict_list


def delete_temp_files(file_paths: List[str]):
    """删除临时文件"""
    for path in file_paths:
        try:
            os.remove(path)
            logger.info(f"Deleted temporary file: {path}")
        except Exception as e:
            logger.warning(f"Failed to delete {path}: {str(e)}")


def update_category_cache_from_transactions(
    transactions: List[Dict[str, Any]],
    category_cache: Optional[Dict[str, Any]],
    account: str,
) -> tuple[Dict[str, Any], int]:
    """根据交易记录增量更新 category_cache。"""
    if not isinstance(category_cache, dict):
        category_cache = {}

    account_cache, account_cache_key = dict_multi_substr_lookup(category_cache, account)
    if account_cache_key is None:
        account_cache_key = str(account).strip()
        if not account_cache_key:
            raise ValueError("account is required to update category cache")

        legacy_cache = category_cache.pop("null", None)
        account_cache = legacy_cache if isinstance(legacy_cache, dict) else None
        if account_cache is None:
            account_cache = category_cache.get(account_cache_key)

    if not isinstance(account_cache, dict):
        account_cache = {}

    updated_count = 0

    for transaction in transactions:
        if not isinstance(transaction, dict):
            continue

        save_to_cache = transaction.get("save_to_cache")
        if save_to_cache is not True and save_to_cache != 1 and save_to_cache != "true":
            continue

        cache_keyword = str(transaction.get("cache_keyword") or "").strip()
        if not cache_keyword:
            continue

        if cache_keyword in account_cache:
            continue

        account_cache[cache_keyword] = {
            "l0_category": transaction.get("l0_category", ""),
            "l1_category": transaction.get("l1_category", ""),
            "l2_category": transaction.get("l2_category", ""),
            "l3_category": transaction.get("l3_category", ""),
        }
        updated_count += 1

    category_cache[account_cache_key] = account_cache
    return category_cache, updated_count


def save_transactions_to_cache(
    transactions: List[Dict[str, Any]],
    account: str,
    app_data: Optional[Dict[str, Any]] = None,
    cache_path: Optional[str] = None,
) -> Dict[str, Any]:
    """将当前交易表格内容更新到 category_cache.json。"""
    if not isinstance(transactions, list):
        raise ValueError("filled_transactions must be a list")

    app_data = app_data or {}

    if cache_path is None:
        cache_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "static",
            "data",
            "category_cache.json",
        )

    category_cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            stored_cache = json.load(f)
        if isinstance(stored_cache, dict):
            category_cache = stored_cache

    if not category_cache:
        app_cache = app_data.get("category_cache")
        if isinstance(app_cache, dict):
            category_cache = app_cache

    updated_cache, updated_count = update_category_cache_from_transactions(
        transactions,
        category_cache,
        account,
    )
    app_data["category_cache"] = updated_cache

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(updated_cache, f, ensure_ascii=False, indent=2)

    return {
        "success": True,
        "message": "Category cache updated",
        "updated_count": updated_count,
    }


def transaction_output_path(
    account: str,
    year: Any,
    month: Any,
    output_root: str,
    extension: str,
) -> str:
    """Build the shared year/month/account filename used by CSV and JSON outputs."""
    if not account or not str(year) or not str(month):
        raise ValueError("account, year, and month are required")

    try:
        year_text = f"{int(year):04d}"
        month_text = f"{int(month):02d}"
    except (TypeError, ValueError):
        raise ValueError("year and month must be numeric")

    account_name = secure_filename(str(account))
    if not account_name:
        raise ValueError("account is not valid for a filename")

    extension = extension.lstrip(".")
    month_dir = os.path.join(output_root, year_text, month_text)
    if extension == "json":
        account_dir = os.path.join(month_dir, account_name)
        os.makedirs(account_dir, exist_ok=True)
        return os.path.join(account_dir, f"{account_name}.json")

    os.makedirs(month_dir, exist_ok=True)
    return os.path.join(month_dir, f"{year_text}_{month_text}_{account_name}.csv")


def save_filled_transactions_to_json(
    transactions: List[Dict[str, Any]],
    account: str,
    year: Any,
    month: Any,
    output_root: str,
) -> str:
    """Save a bare transaction list in the statement account folder for UI editing."""
    if not isinstance(transactions, list):
        raise ValueError("filled_transactions must be a list")

    file_path = transaction_output_path(account, year, month, output_root, "json")
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(transactions, file, ensure_ascii=False, indent=2)
    return file_path


def save_transactions_to_csv(
    transactions: List[Dict[str, Any]],
    account: str,
    year: Any,
    month: Any,
    history_dir: str,
) -> str:
    """将完整交易列表覆盖写入指定账户和月份的CSV历史文件。"""
    if not isinstance(transactions, list):
        raise ValueError("filled_transactions must be a list")

    file_path = transaction_output_path(account, year, month, history_dir, "csv")

    rows = [
        transaction
        for transaction in transactions
        if isinstance(transaction, dict) and transaction.get("save_to_file", True)
    ]
    fieldnames: List[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)

    with open(file_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)

    return file_path


def analyze(
    file_path: str,
    account: str,
    year: str,
    month: str,
    app_data: Dict[str, Any] = None,
    keep_alive: Optional[Union[int, str]] = None,
) -> Dict[str, Any]:
    """完整分析流程"""
    saved_image_paths = []
    
    pdf_pwd = app_data.get('pdf_pwd', {}) if app_data else {}
    categories = app_data.get('categories')
    account_format = app_data.get('account_format')
    category_cache = app_data.get('category_cache')
    account_meta = app_data.get('accountMeta') if app_data else None

    try:
        # Step 1: 读取PDF为图片列表
        
        password = pdf_pwd.get(account)
        images = read_pdf(file_path, password)

        print(account, year, month, flush=True)
        print(file_path, password, flush=True)

        if not images:
            return {"success": False, "error": "Failed to read PDF"}
        
        logger.info(f"PDF converted to {len(images)} images")
        
        file_name_prefix = "bank_statement_page"
        saved_image_paths = save_images(images, "tmp_files", prefix=file_name_prefix) 

        img_names = [f"tmp_files/{file_name_prefix}_{i+1}.jpg" for i in range(len(images))]
        print(img_names, flush=True)
        # Step 2: vllm table to json
        transaction_lst = process_imgs(img_names, account, keep_alive=keep_alive)
        
        transaction_dict_list = str_to_dict(transaction_lst)
        with open("tmp_files/raw_transaction_str.txt", "w", encoding="utf-8") as f:
            json.dump(transaction_dict_list, f, ensure_ascii=False, indent=4)

        # ===== 旧的规则式标准化流程（已由 transactions_standardization 取代，保留备查） =====
        # transaction_dict_list = clean_chinese_text(transaction_dict_list)
        # with open("tmp_files/raw_transaction_str.txt", "w", encoding="utf-8") as f:
        #     json.dump(transaction_dict_list, f, ensure_ascii=False, indent=4)
        # # print("Cleaned transactions:", transaction_dict_list, flush=True)
        #
        #
        # with open("tmp_files/raw_transaction_str.txt", "r", encoding="utf-8") as f:
        #     transaction_dict_list = json.load(f)
        #
        #
        # account_format_key_mappings, _ = dict_multi_substr_lookup(account_format, account)
        # account_format_key_mappings = account_format_key_mappings.get("key_mappings")
        # standardized_transactions = transaction_dict_mapping(transaction_dict_list, account_format_key_mappings, account)
        # standardized_transactions = date_formattting(
        #     standardized_transactions,
        #     account=account,
        #     year=year,
        #     month=month,
        #     account_format=account_format,
        # )
        # ===== 旧流程结束 =====

        # 新的逐行 LLM 标准化（表头映射 + 符号 + 日期 + OCR 纠错，内含金额数字校验）
        standardized_transactions = transactions_standardization(
            transaction_dict_list,
            account,
            account_meta,
            year,
            month,
            keep_alive=keep_alive,
        )

        # print("Standardized transactions:", standardized_transactions)


        with open("tmp_files/transaction_standardized.txt", "w", encoding="utf-8") as f:
            json.dump(standardized_transactions, f, ensure_ascii=False, indent=4)

        with open("tmp_files/transaction_standardized.txt", "r", encoding="utf-8") as f:
            standardized_transactions = json.load(f)

        filled_transactions = transactions_categorization(
            standardized_transactions,
            categories,
            category_cache,
            account,
            keep_alive=keep_alive,
        )
        

        with open("tmp_files/filled_transaction_str.txt", "w", encoding="utf-8") as f:
            json.dump(filled_transactions, f, ensure_ascii=False, indent=4)
        
        with open("tmp_files/filled_transaction_str.txt", "r", encoding="utf-8") as f:
            filled_transactions = json.load(f)

        if not filled_transactions:
            return {"success": False, "error": "Analysis failed"}
        
        
        
        return {
            "success": True,
            "data": filled_transactions,
            "account": account
        }
    
    except Exception as e:
        logger.error(f"Error in analyze: {str(e)}")
        # 异常时也尝试清理临时文件
        # if saved_image_paths:
            # delete_temp_files(saved_image_paths)

        return {"success": False, "error": str(e)}
