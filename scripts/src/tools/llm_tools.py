from typing import Dict, Any, Optional, List, Union

import json
import os
import re
from scripts.src.tools.llm_library import ollama_llm, ollama_multi_modal_llm

from scripts.src.tools.prompts import *


def dict_substr_lookup(d: Dict[str, Any], query: str) -> Optional[str]:
    """在字典中查找包含查询字符串的键，并返回对应的值"""
    if not isinstance(d, dict) or query is None:
        return None, None

    query = str(query)
    for key, value in d.items():
        if not isinstance(key, str):
            continue
        if query.lower() in key.lower() or key.lower() in query.lower():
            return value, key
        
    return None, None

def dict_multi_substr_lookup(d: Dict[str, Any], query: str) -> List[Dict[str, Any]]:

    if not isinstance(d, dict) or query is None:
            return None, None

    for key, value in d.items():
        if not isinstance(key, str):
            continue

        key_subs = key.lower().split("_")
        hit = True
        for k in key_subs:
            if k not in query.lower():
                hit = False
                break
        if hit:
            return value, key

    return None, None

def img_to_json(
    img_path: str,
    account: str,
    keep_alive: Optional[Union[int, str]] = None,
) -> Optional[Dict[str, Any]]:
    """将图片路径转换为JSON格式，供LLM分析使用"""

    sys_prompt = IMG_TO_JSON_BASE_PROMPT + IMG_TO_JSON_ACCOUNT_PROMPTS.get(account, "")

    usr_prompt = IMG_TO_JSON_USR_PROMPT
    # print(f"Calling multi-modal LLM with image: {img_path}")
    response = ollama_multi_modal_llm(
        img_path,
        sys_prompt,
        usr_prompt,
        keep_alive=keep_alive,
    )
    # print(f"LLM response: {response}")
    response = response["message"]["content"]

    return response
    

def imgs_to_json(
    img_paths: List[str],
    account: str,
    keep_alive: Optional[Union[int, str]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """将图片路径列表转换为JSON格式，供LLM分析使用"""
    
    transactions = []
    for img_path in img_paths:
        print(f"Processing image: {img_path}")
        transaction_part_string = img_to_json(img_path, account, keep_alive=keep_alive)
        if transaction_part_string:
            transactions.append(transaction_part_string)

        # print(f"Processed image {img_path}, extracted transactions: {transaction_part_string}")
        # print(type(transaction_part_string))
        # print(type(transaction_part_string[0]))  # Debug: Check the type of transactions list after appending each item
        # break
    return transactions


# ============================================================
# 逐行标准化（取代规则式 transaction_dict_mapping + date_formattting）
# ============================================================
def resolve_account_type(account_meta: Any, account: str) -> str:
    """根据 AppData.accountMeta 判断账户属于信用卡还是储蓄账户。
    返回 'credit card' 或 'saving account'（无法判断时按名字兜底）。"""
    account_name = str(account or "").strip().lower()
    if isinstance(account_meta, list):
        for group in account_meta:
            if not isinstance(group, dict):
                continue
            children = group.get("child_accounts") or []
            child_names = {
                str(child.get("name", "")).strip().lower()
                for child in children
                if isinstance(child, dict)
            }
            if account_name in child_names:
                group_name = str(group.get("name", "")).lower()
                if "credit" in group_name or "card" in group_name:
                    return "credit card"
                return "saving account"
    # 兜底：名字里带 card 认为是信用卡，否则储蓄账户
    return "credit card" if "card" in account_name else "saving account"


def _extract_amount_digits(amount_text: Any) -> str:
    """提取金额里的数字串（去符号、去千分位、保留小数点）。"""
    cleaned = str(amount_text or "").replace(",", "")
    match = re.search(r"\d[\d.]*", cleaned)
    return match.group(0) if match else ""


def _amount_present_in_row(amount_text: Any, raw_dict: Dict[str, Any]) -> bool:
    """校验标准化后的金额数字确实出现在原始行某个字段里
    （只允许加符号/去千分位，不许改数字）。"""
    digits = _extract_amount_digits(amount_text)
    if digits == "":
        return False
    raw_concat = " ".join(
        str(value) for value in raw_dict.values() if value is not None
    ).replace(",", "")
    return digits in raw_concat


def transaction_standardization(
    raw_dict: Dict[str, Any],
    account: str,
    account_type: str,
    year: Any,
    month: Any,
    keep_alive: Optional[Union[int, str]] = None,
) -> Dict[str, Any]:
    """把单条 VLM 原始行标准化为统一结构（11 键），供分类步衔接。
    LLM 只产出 date/transaction_detail/amount，其余字段在此补全；
    金额数字校验也在此完成（只允许加符号，不许改数字）。"""

    sys_prompt = TRANSACTION_STANDARDIZE_BASE_PROMPT
    usr_prompt = TRANSACTION_STANDARDIZE_USR_PROMPT.format(
        account_type=account_type,
        account=account,
        year=year,
        month=month,
        raw_row=json.dumps(raw_dict, ensure_ascii=False),
    )

    response = ollama_llm(sys_prompt, usr_prompt, think=False, keep_alive=keep_alive)
    if isinstance(response, dict):
        printable_response = {k: v for k, v in response.items() if k != "context"}
    else:
        printable_response = response
    print(f"Standardize LLM response: {printable_response}", flush=True)

    # 统一结构：即使解析失败也返回（保证行不丢，能衔接 transactions_categorization）
    standardized: Dict[str, Any] = {
        "date": "",
        "l0_category": "",
        "l1_category": "",
        "l2_category": "",
        "l3_category": "",
        "account": account,
        "transaction_detail": "",
        "note": "",
        "amount": "",
        "from_cache": "",
        "cache_keyword": "",
    }

    try:
        content = response["message"]["content"]
    except Exception:
        standardized["note"] = "⚠ standardization failed (no LLM content)"
        return standardized

    parsed = None
    try:
        parsed = json.loads(content)
    except Exception:
        try:
            start = content.find("{")
            end = content.rfind("}")
            parsed = json.loads(content[start:end + 1])
        except Exception:
            parsed = None

    if not isinstance(parsed, dict):
        standardized["note"] = "⚠ standardization failed (unparseable output)"
        return standardized

    standardized["date"] = str(parsed.get("date", "") or "")
    standardized["transaction_detail"] = str(parsed.get("transaction_detail", "") or "")
    amount_value = str(parsed.get("amount", "") or "")
    standardized["amount"] = amount_value

    # 数字校验：标准化后的金额数字必须来自原始行（只允许加符号）
    if amount_value and not _amount_present_in_row(amount_value, raw_dict):
        print(
            f"⚠ amount digits not found in raw row: amount={amount_value!r}, raw={raw_dict}",
            flush=True,
        )
        standardized["note"] = "⚠ amount unverified"

    return standardized


def transactions_standardization(
    transaction_dict_list: List[Dict[str, Any]],
    account: str,
    account_meta: Any,
    year: Any,
    month: Any,
    keep_alive: Optional[Union[int, str]] = None,
) -> List[Dict[str, Any]]:
    """逐行标准化 VLM 输出。输出为统一结构的 list，可直接作为
    transactions_categorization 的输入。"""
    account_type = resolve_account_type(account_meta, account)
    print(
        f"Standardizing {len(transaction_dict_list)} rows as account_type={account_type!r}",
        flush=True,
    )

    standardized_list: List[Dict[str, Any]] = []
    for raw_dict in transaction_dict_list:
        if not isinstance(raw_dict, dict):
            continue
        standardized_list.append(
            transaction_standardization(
                raw_dict, account, account_type, year, month, keep_alive=keep_alive
            )
        )
    return standardized_list


def transactions_categorization(
    transaction_lst: List[Dict[str, Any]],
    categories: Dict[str, Any],
    category_cache: Dict[str, str],
    account: str,
    keep_alive: Optional[Union[int, str]] = None,
) -> List[Dict[str, Any]]:
   
    for transaction in transaction_lst:
        trans_detail = " ".join(str(transaction.get("transaction_detail") or "").split())
        transaction["transaction_detail"] = trans_detail

        # print(f"Categorizing transaction: {trans_detail}")
        # Check if the transaction has already been categorized


        account_cat_cache, _ = dict_multi_substr_lookup(category_cache, account)

        matched_cache, matched_keyword = dict_substr_lookup(account_cat_cache or {}, trans_detail)
        # print(matched_cache)
        if matched_cache is not None:
            # print(f"Transaction found in cache, using cached categories for: {trans_detail}")
            transaction["l0_category"] = matched_cache["l0_category"]
            transaction["l1_category"] = matched_cache["l1_category"]
            transaction["l2_category"] = matched_cache["l2_category"]
            transaction["l3_category"] = matched_cache["l3_category"]
            transaction["from_cache"] = "Yes"
            transaction["cache_keyword"] = matched_keyword
        else:
            # print("Transaction not found in cache, calling LLM for category")
            transaction = transaction_categorization(
                transaction,
                categories,
                keep_alive=keep_alive,
            )
            transaction["from_cache"] = "No"

    return transaction_lst



def transaction_categorization(
    transaction: Dict[str, Any],
    categories: Dict[str, Any],
    keep_alive: Optional[Union[int, str]] = None,
) -> Dict[str, Any]:
    """对单个交易进行分类，调用 LLM 并将结果合并回 transaction 字典。"""

    trans_detail = transaction.get("transaction_detail")
    trans_amount = transaction.get("amount")
    # print(f"Categorizing transaction: {trans_detail} with amount: {trans_amount}")
    # Build prompts
    cat_str = json.dumps(categories, ensure_ascii=False)
    # print(f"Categories mapping: {cat_str}")
    sys_prompt = TRANSACTION_CATEGORIZATION_BASE_PROMPT.format(categories=cat_str)
    # Provide categories mapping and the single transaction as the user prompt body
    usr_prompt = TRANSACTION_CATEGORIZATION_USR_PROMPT.format(trans_detail=trans_detail, trans_amount=trans_amount)

    print(f"Calling LLM for transaction: {trans_detail}", flush=True)
    # Call LLM
    response = ollama_llm(
        sys_prompt,
        usr_prompt,
        think=False,
        keep_alive=keep_alive,
    )
    if isinstance(response, dict):
        message = response.get("message")
        if isinstance(message, dict) and "thinking" in message:
            message["thinking"] = "Hidden"
    # 打印时去掉冗长的 context（token id 列表），但不改变 response 本身
    if isinstance(response, dict):
        printable_response = {k: v for k, v in response.items() if k != "context"}
    else:
        printable_response = response
    print(f"LLM response: {printable_response}", flush=True)
    # Extract content
    content = None
    try:
        content = response["message"]["content"]
    except Exception:
        # Fallback: return transaction with error
        transaction["l0_category"] = "Unknown"
        transaction["l1_category"] = "Unknown"
        transaction["l2_category"] = "Unknown"
        transaction["l3_category"] = "Unknown"

        return transaction

    # Try to parse JSON content from LLM
    try:
        parsed = json.loads(content)
    except Exception:
        # If parsing fails, attempt to locate a JSON object substring
        try:
            start = content.find('{')
            end = content.rfind('}')
            parsed = json.loads(content[start:end+1])
        except Exception:
            transaction["l0_category"] = "Unknown"
            transaction["l1_category"] = "Unknown"
            transaction["l2_category"] = "Unknown"
            transaction["l3_category"] = "Unknown"

            return transaction

    # Merge parsed labels back into transaction
    transaction["l0_category"] = parsed.get("l0")
    transaction["l1_category"] = parsed.get("l1")
    transaction["l2_category"] = parsed.get("l2")
    transaction["l3_category"] = parsed.get("l3")
    

    return transaction

