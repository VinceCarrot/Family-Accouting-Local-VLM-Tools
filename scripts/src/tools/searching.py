from ddgs import DDGS
from difflib import SequenceMatcher
import json
from typing import Dict, List, Any, Optional


def search_transaction_in_lut(query: dict, lut: dict) -> list:
    """
    从 lookup table 搜索相似的交易

    Args:
        query: {"account": "...", "description": "..."}
        lut: lookup table, 格式为 
        {
            account_name_1: 
            {
                description_1: labels
                description_2: labels
                ...
            },
            account_name_2: 
            {
                ...
            }
        }

    Returns:
        labels
    """

    if not lut or not query:
        return []

    account = query.get("account", "")
    description = query.get("description", "")  

    if account in lut:
        lut_accoun = lut[account]
        if description in lut_accoun:
            return lut_accoun[description]
        else:
            return None
    else:
        return None     
   


def search_transaction_history(query: str, transaction_history: list) -> list:
    """
    从交易历史搜索相似的交易项

    Args:
        query: 搜索查询，格式为 JSON: {"account": "...", "description": "..."}
        transaction_history: 交易历史列表，格式为 [{"transaction_date": "...", "description": "...", "tags": {...}}]

    Returns:
        List[Dict] - 找到的相似交易列表
    """
    if not transaction_history or not query:
        return []

    try:
        query_data = json.loads(query) if isinstance(query, str) else query
        account = query_data.get("account", "")
        description = query_data.get("description", "")
    except:
        return []

    results = []
    threshold = 0.5  # 相似度阈值（比LUT宽松一些）

    for trans in transaction_history:
        trans_account = trans.get("account", "")
        trans_description = trans.get("description", "")

        # 只搜索相同账户的记录
        if trans_account.lower() == account.lower():
            # 计算描述的相似度
            similarity = SequenceMatcher(None, description.lower(), trans_description.lower()).ratio()
            if similarity >= threshold:
                results.append({
                    "type": "history_match",
                    "transaction_date": trans.get("transaction_date"),
                    "description": trans_description,
                    "similarity": similarity,
                    "tags": trans.get("tags", {}),
                    "withdrawal": trans.get("withdrawal"),
                    "deposit": trans.get("deposit")
                })

    # 按相似度排序，返回前10个
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:10]


def ddgs_search_text(query: str, top_k: int = 5) -> list:
    """
    使用 DuckDuckGo (ddgs 新版) 进行网络搜索
        pip install ddgs

    Args:
        query: 搜索文本
        top_k: 返回结果数量

    Returns:
        List[Dict] - 搜索结果，格式为 [{"title": "...", "snippet": "...", "url": "..."}]
    """

    results = []

    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=top_k, region="sg-en"):
                result_item = {
                    "type": "web_search",
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", "")
                }
                results.append(result_item)

    except Exception as e:
        print(f"[DDGS Search Error] {e}")
        return []

    return results


def searching_tool(
    transaction_item: Dict[str, Any],
    account: str,
    lut: Optional[Dict] = None,
    transaction_history: Optional[List] = None,
    enable_web_search: bool = True
) -> Dict[str, Any]:
    """
    综合搜索：LUT + 交易历史 + 网络搜索

    Args:
        transaction_item: 待分类的交易项，包含 description, withdrawal, deposit 等
        account: 账户名称
        lut: lookup table (可选)
        transaction_history: 交易历史列表 (可选)
        enable_web_search: 是否启用网络搜索

    Returns:
        Dict 包含：
            - lut_matches: LUT 搜索结果
            - history_matches: 交易历史搜索结果
            - web_search_results: 网络搜索结果
    """
    description = transaction_item.get("description", "")

    query = json.dumps({"account": account, "description": description}, ensure_ascii=False)

    search_results = {
        "transaction_item": transaction_item,
        "account": account,
        "lut_matches": [],
        "history_matches": [],
        "web_search_results": []
    }

    # 1️⃣ 搜索 LUT
    if lut:
        search_results["lut_matches"] = search_transaction_in_lut(query, lut)

    # 2️⃣ 搜索交易历史
    if transaction_history:
        search_results["history_matches"] = search_transaction_history(query, transaction_history)

    # 3️⃣ 网络搜索 (提取关键词)
    if enable_web_search and description:
        # 从描述中提取关键词（去除数字和通用词）
        keywords = extract_search_keywords(description)
        if keywords:
            search_results["web_search_results"] = ddgs_search_text(keywords, top_k=5)

    return search_results


def extract_search_keywords(description: str) -> str:
    """
    从交易描述中提取搜索关键词

    Args:
        description: 交易描述文本

    Returns:
        str - 提取的关键詞字符串
    """
    # 移除常见的技术词汇和操作码
    exclude_words = {
        'via', 'from', 'to', 'mobile', 'transfer', 'payment', 'purchase',
        'withdrawal', 'deposit', 'transaction', 'account', 'bank',
        'code', 'ref', 'reference', 'othr', 'others'
    }

    words = description.split()
    filtered_words = []

    for word in words:
        word_lower = word.lower().rstrip('.,!?;:-')
        # 保留非数字、非代码的词汇
        if (word_lower not in exclude_words and
                not word_lower.startswith('qr') and
                not word_lower.isdigit() and
                len(word_lower) > 2):
            filtered_words.append(word_lower)


    return ' '.join(filtered_words) if filtered_words else ""
