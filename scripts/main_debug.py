from utils.llm_library import call_ollama

from pydantic import BaseModel, Field
import json

class TaggingRequest(BaseModel):
    l0_tag_name: str = Field(description="The name of the L0 tag to be applied.")
    l1_tag_name: str = Field(description="The name of the L1 tag to be applied.")
    l2_tag_name: str = Field(description="The name of the L2 tag to be applied.")
    l3_tag_name: str = Field(description="The name of the L3 tag to be applied.")
    confidence: float = Field(description="The confidence score of the tagging result, ranging from 0 to 1.")
    reason: str = Field(description="The reason for the tagging result, providing an explanation for why the specific tags were applied based on the content of the log entry.")



class SearchToolCallingRequest(BaseModel):
    use_tool: bool = Field(description="A boolean indicating whether to use the search tool or not.")
    query: str = Field(description="The query to be used if the search tool is called. This field should be provided only if use_tool is true.")

with open("../../WebUI_Server/static/data/categories.json", "r", encoding="utf-8") as f:
    tags_hierarchy = json.load(f)

system_prompt = """
You are a precise and helpful assistant for tagging log entries with appropriate tags based on their content.

The tags are organized in a hierarchical structure with four levels: L0, L1, L2, and L3, where L0 is the most general and L3 is the most specific.

For each log entry:
- Analyze the content carefully.
- Apply the most relevant tags at each level (L0 → L3).
- Provide a confidence score for your tagging decisions, reflecting how certain you are about the appropriateness of the tags.

Output format:
- Your output must strictly follow the provided {schema}.
- Return only valid JSON that matches the above schema, without any additional text or explanation.

The confidence score should reflect the certainty of the tagging decision, which should not be too optimistic. If you are unsure or the input is ambiguous, output confidence < 0.5 and provide a clear reason in the 'reason' field.


Hierarchical tags structure:
{tags}

"""

transaction_item = {
    "transaction_date": "15 FEB",
    "value_date": "16 FEB",
    "description": "NETS QR 23033924 NETS QR PURCHASE CHEF WANG FRIED RICE",
    "withdrawal": "0.2",
    "deposit": "0.0",
    "balance": "239,180.00"
}

transaction_item = {
    "transaction_date": "14 FEB",
    "value_date": "14 FEB",
    "description": "FUND TRANSFER via PayNow-Mobile to HE JUNYI OTHR - OTHR",
    "withdrawal": "10,000.0",
    "deposit": "0.0",
    "balance": "239,180.00"
}

transaction_item = json.dumps(transaction_item, ensure_ascii=False)

user_prompt = """
transaction item: {transaction_item}
"""

tool = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "A tool for searching information on the web to assist with tagging decisions. It should be used when the log entry contains ambiguous or insufficient information that makes it difficult to determine the appropriate tags with high confidence.",
        "parameters": SearchToolCallingRequest.model_json_schema()  # 直接传 schema
    }
}

messages = [
    {"role": "system", "content": system_prompt.format(schema=json.dumps(TaggingRequest.model_json_schema(), ensure_ascii=False), tags=json.dumps(tags_hierarchy, ensure_ascii=False))},
    {"role": "user", "content": user_prompt.format(transaction_item=transaction_item)}
]   



MODEL_NAME = "qwen3-coder:30b"
response = call_ollama(MODEL_NAME, messages, tools=[tool])
print("Tagging Result:")

response = json.loads(response)
print(response["properties"])
