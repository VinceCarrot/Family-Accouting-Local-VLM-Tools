# def clean_chinese_text(transaction_dict_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#     """去掉字典中 key 里的中文字符，并清理尾部空白。若清理后 key 重复，则保留先出现的值。"""
#     cleaned_list: List[Dict[str, Any]] = []
#
#     for transaction_dict in transaction_dict_list:
#         cleaned_dict: Dict[str, Any] = {}
#         for key, value in transaction_dict.items():
#             if isinstance(key, str):
#                 cleaned_key = re.sub(r'[\u3400-\u4DBF\u4E00-\u9FFF]', '', key)
#                 cleaned_key = cleaned_key.rstrip()
#             else:
#                 cleaned_key = key
#
#             if cleaned_key not in cleaned_dict:
#                 cleaned_dict[cleaned_key] = value
#         cleaned_list.append(cleaned_dict)
#
#     return cleaned_list
#
#
# def date_formattting(
#     transaction_dict_list: List[Dict[str, Any]],
#     account: str,
#     year: Optional[str] = None,
#     month: Optional[str] = None,
#     account_format: Optional[Dict[str, Any]] = None,
# ) -> List[Dict[str, Any]]:
#     """将交易日期按 account_format 中的 date_format 规范化为 YYYY-MM-DD。"""
#     if not transaction_dict_list:
#         return transaction_dict_list
#
#     account_format_config: Dict[str, Any] = {}
#     if isinstance(account_format, dict):
#         account_format_config, _ = dict_multi_substr_lookup(account_format, account)
#
#     date_format = ""
#     if isinstance(account_format_config, dict):
#         date_format = account_format_config.get("date_format") or ""
#
#     def normalize_date(raw_value: Any) -> Optional[str]:
#         if raw_value is None:
#             return None
#
#         text = str(raw_value).strip()
#         if not text:
#             return None
#
#         if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
#             return text
#
#         if date_format:
#             fmt = (
#                 date_format
#                 .replace("YYYY", "%Y")
#                 .replace("YY", "%y")
#                 .replace("MMMM", "%B")
#                 .replace("MMM", "%b")
#                 .replace("MM", "%m")
#                 .replace("DD", "%d")
#             )
#             try:
#                 parsed = datetime.strptime(text, fmt)
#             except ValueError:
#                 pass
#             else:
#                 if "%Y" not in fmt and year not in (None, ""):
#                     try:
#                         parsed = parsed.replace(year=int(str(year)))
#                     except ValueError:
#                         pass
#                 if not any(token in fmt for token in ("%m", "%b", "%B")) and month not in (None, ""):
#                     try:
#                         parsed = parsed.replace(month=int(str(month)))
#                     except ValueError:
#                         pass
#                 return parsed.strftime("%Y-%m-%d")
#
#         for fmt in (
#             "%Y-%m-%d",
#             "%Y/%m/%d",
#             "%a, %d %b %Y",
#             "%A, %d %B %Y",
#             "%d/%m/%Y",
#             "%d-%m-%Y",
#             "%d.%m.%Y",
#             "%d %b %Y",
#             "%d %B %Y",
#             "%d %b",
#             "%d %B",
#             "%b %d",
#             "%B %d",
#             "%d/%m/%y",
#             "%d-%m-%y",
#         ):
#             try:
#                 parsed = datetime.strptime(text, fmt)
#             except ValueError:
#                 continue
#
#             if "%Y" not in fmt and year not in (None, ""):
#                 try:
#                     parsed = parsed.replace(year=int(str(year)))
#                 except ValueError:
#                     pass
#             if not any(token in fmt for token in ("%m", "%b", "%B")) and month not in (None, ""):
#                 try:
#                     parsed = parsed.replace(month=int(str(month)))
#                 except ValueError:
#                     pass
#             return parsed.strftime("%Y-%m-%d")
#
#         return None
#
#     for transaction in transaction_dict_list:
#         if not isinstance(transaction, dict):
#             continue
#         if "date" in transaction:
#             normalized_date = normalize_date(transaction.get("date"))
#             if normalized_date:
#                 transaction["date"] = normalized_date
#
#     return transaction_dict_list
#
#
# def transaction_dict_mapping(transaction_dict_list: List[Dict[str, Any]], account_format_key_mappings: Dict[str, Any], account: str) -> List[Dict[str, Any]]:
#     """根据account_format映射字典中的键"""
#     mapped_list: List[Dict[str, Any]] = []
#     # print(transaction_dict_list)
#     for transaction_dict in transaction_dict_list:
#         mapped_dict: Dict[str, Any] = {}
#
#         for key, value in account_format_key_mappings.items():
#             if not isinstance(value, str):
#                 continue  # 如果value不是字符串，跳过
#             if value in transaction_dict:
#                 mapped_dict[key] = transaction_dict[value]
#             else:
#                 mapped_dict[key] = ""  # 如果找不到对应的键，则设置为空字符串
#
#         # print(mapped_dict)
#         # print(account_format_key_mappings)
#         amount_key_mappings = account_format_key_mappings.get("amount")
#         # print(amount_key_mappings)
#         amount_value = transaction_dict.get(amount_key_mappings.get("pos"))
#         # print(amount_value)
#         if amount_value is None:
#             amount_value = transaction_dict.get(amount_key_mappings.get("neg"))
#             # print(amount_value)
#             if amount_value is None:
#                 continue  # 如果负数列有值，则跳过正数列
#             mapped_dict["amount"] = "-" + str(amount_value)
#         else:
#             mapped_dict["amount"] = amount_value
#
#         mapped_dict["account"] = account
#         mapped_dict["from_cache"] = ""
#         mapped_dict["cache_keyword"] = ""
#         # print(amount_value)
#         # mapped_dict["amount"]
#         mapped_list.append(mapped_dict) 
#
#
#
#     return mapped_list