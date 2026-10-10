# PDF 分析模块文档

## 📋 概述

`pdf_analyzer.py` 提供了 PDF 到图片的转换功能，用于后续的 LLM 多模态分析。

## 🎯 核心函数

## 批量预处理与人工复核

在 `WebUI_Local` 目录中编辑 `batch_input_config.json`，每一项对应一份 PDF。`account` 使用 Load Statements 页面账户下拉框中的显示名称；PDF 必须放在对应的账户目录 `estatements/{year}/{month:02d}/{secure_filename(account)}/` 中，`source_pdf` 填写该目录里的 PDF 文件名。

```json
[
    {
        "year": 2026,
        "month": 7,
        "account": "HB OCBC 360 Account",
        "source_pdf": "OCBC statement download.pdf"
    }
]
```

程序只在对应账户目录及其子目录内按完整文件名精确查找；若 PDF 缺失或同名文件不止一个，该项会报错，不会猜测。

运行批处理：

```bash
cd WebUI_Local
python main_pdf_batch_process.py
```

每成功处理一项后，剩余任务会保存到 `batch_input_config_remaining.json`；再次运行时会优先从该文件续跑。原始 `batch_input_config.json` 会保留不变。要从头重跑原始批次，请删除 `batch_input_config_remaining.json`。

每项生成 `estatements/{year}/{month:02d}/{secure_filename(account)}/{secure_filename(account)}.json`，文件内容是 `filled_transactions` 交易列表本身，不包含额外元数据。批处理请求会将 Ollama 模型保持加载，避免长批次间隔期间自动卸载。之后在 Load Statements 页面手动选择账户、年份和月份，再选择该 JSON 直接进入交易复核；编辑并保存时仍输出到原有 `static/data/transaction_history/{year}/{month:02d}/` CSV 路径。

### 1. `read_pdf(file_path, password=None) → List[Image]`

**功能**: 将 PDF 文件的每一页转换为 PIL Image 对象

**参数**:
- `file_path` (str): PDF 文件路径
- `password` (str, optional): PDF 密码（如果有）

**返回值**:
- 成功: PIL Image 对象列表，每个对象代表 PDF 的一页
- 失败: None

**特性**:
- DPI: 200 (良好的分辨率和速度平衡)
- 自动处理 PDF 密码
- 详细的错误日志

**使用示例**:
```python
from scripts.src.tools.pdf_analyzer import read_pdf

# 无密码
images = read_pdf("statement.pdf")

# 有密码
images = read_pdf("statement.pdf", password="123456")

if images:
    print(f"转换了 {len(images)} 页")
    print(f"第一页大小: {images[0].size}")
```

### 2. `save_images(images, output_dir, prefix="page") → List[str]`

**功能**: 将 PIL Image 对象列表保存为 JPG 文件

**参数**:
- `images` (List[Image]): PIL Image 对象列表
- `output_dir` (str): 输出目录
- `prefix` (str): 文件名前缀，默认为 "page"

**返回值**:
- 成功: 保存的文件路径列表
- 失败: None

**文件命名规则**:
- 格式: `{prefix}_{page_number}.jpg`
- 示例: `statement_1.jpg`, `statement_2.jpg`, ...

**特性**:
- 自动创建输出目录
- 转换为 RGB 格式确保 JPG 兼容性
- JPEG 质量: 95 (高质量)
- 详细的保存日志

**使用示例**:
```python
from scripts.src.tools.pdf_analyzer import read_pdf, save_images

images = read_pdf("statement.pdf")
if images:
    paths = save_images(images, "/tmp/pdf_output", prefix="statement")
    for path in paths:
        print(f"已保存: {path}")
```

### 3. `analyze_pdf(images, account, analysis_type, app_data) → Dict`

**功能**: 使用 LLM 分析 PDF 图片

**状态**: ⏳ 待实现

**参数**:
- `images` (List[Image]): PIL Image 对象列表
- `account` (str): 账户名称
- `analysis_type` (str): 分析类型（默认 "financial"）
- `app_data` (Dict): 应用数据

**返回值**:
```python
{
    "success": bool,
    "data": {...},  # 分析结果
    "error": str    # 错误信息（如果失败）
}
```

### 4. `post_process(result) → Dict`

**功能**: 后处理分析结果

**状态**: ⏳ 待实现

### 5. `analyze(file_path, account, analysis_type, app_data) → Dict`

**功能**: 完整的 PDF 分析流程 (读取 → 分析 → 后处理)

**参数**:
- `file_path` (str): PDF 文件路径
- `account` (str): 账户名称
- `analysis_type` (str): 分析类型（默认 "financial"）
- `app_data` (Dict): 应用数据（包含 PDF 密码等）

**返回值**:
```python
{
    "success": bool,
    "data": {...},      # 分析结果
    "account": str,     # 账户名称
    "error": str        # 错误信息（如果失败）
}
```

**使用示例**:
```python
from scripts.src.tools.pdf_analyzer import analyze

app_data = {
    "pdf_pwd": {
        "account1": "password123",
        "account2": None
    }
}

result = analyze(
    "statement.pdf", 
    account="account1",
    analysis_type="financial",
    app_data=app_data
)

if result["success"]:
    print(f"分析成功: {result['data']}")
else:
    print(f"分析失败: {result['error']}")
```

## 🔧 后端 API 使用

### POST `/api/analyze_pdf`

**请求**:
```
POST /api/analyze_pdf HTTP/1.1
Content-Type: multipart/form-data

file: <PDF 文件>
account: <账户名称>
analysis_type: financial  (可选，默认值)
```

**响应**:
```json
{
    "success": true,
    "data": {...},
    "account": "account1"
}
```

**错误响应**:
```json
{
    "success": false,
    "error": "Only PDF files supported"
}
```

## 🧪 测试脚本

### 快速测试

```bash
# 无密码
cd /mnt/d/Projects/SpendLog/WebUI_Local
python scripts/test_pdf_reader.py sample.pdf

# 有密码
python scripts/test_pdf_reader.py sample.pdf "123456" ./output

# 指定输出目录
python scripts/test_pdf_reader.py sample.pdf "" /tmp/pdf_images
```

### 在 Python 中测试

```python
import sys
sys.path.insert(0, '/mnt/d/Projects/SpendLog/WebUI_Local')

from scripts.src.tools.pdf_analyzer import read_pdf, save_images

# 读取 PDF
images = read_pdf("sample.pdf")

# 保存为 JPG
if images:
    paths = save_images(images, "output", prefix="page")
    print(f"✅ 保存了 {len(paths)} 张图片")
```

## 🔐 依赖

### 必须安装:
- `pdf2image` - PDF 转图片
- `Pillow` - 图片处理
- `PyPDF2` - PDF 处理（可选，用于高级功能）

### 系统依赖:
- `poppler` - PDF 转换工具

**安装**:
```bash
# Python 包
pip install -r requirements.txt

# Linux
sudo apt-get install poppler-utils

# macOS
brew install poppler

# Windows
# 下载 poppler: https://github.com/oschwartz10612/poppler-windows/releases/
```

## 🎨 图片规格

转换后的图片规格:

| 属性 | 值 |
|------|-----|
| DPI | 200 |
| 格式 | RGB (自动转换) |
| 输出格式 | JPEG |
| 质量 | 95/100 |
| 文件名 | `{prefix}_{page}.jpg` |

## 📝 后续步骤

1. ✅ `read_pdf()` - 已实现
2. ✅ `save_images()` - 已实现  
3. ⏳ `analyze_pdf()` - 待实现 (集成多模态 LLM)
4. ⏳ `post_process()` - 待实现 (结果格式化)

## 🐛 常见问题

### Q: 如何处理 PDF 密码?
A: 通过 `app_data` 中的 `pdf_pwd` 字典传递，或直接调用 `read_pdf()` 时指定 `password` 参数。

### Q: 支持哪些 PDF 加密方式?
A: 支持标准 PDF 密码加密。复杂的加密方式可能不支持。

### Q: 如何提高转换速度?
A: 在 `read_pdf()` 中修改 DPI 参数（值越小速度越快），或修改 fmt 参数。

### Q: 支持并行处理多个 PDF 吗?
A: 可以，但 pdf2image 有内存开销，建议一次不超过 10 个并行任务。

## 🔗 参考资源

- [pdf2image 文档](https://github.com/Belval/pdf2image)
- [Pillow 文档](https://python-pillow.org/)
- [Poppler 文档](https://poppler.freedesktop.org/)
