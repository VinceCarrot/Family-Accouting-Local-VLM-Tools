// static/modules/load_statements/load_statements.js

let initialized = false;
let filled_transactions = [];
window.filled_transactions = filled_transactions;
const STATEMENT_HANDLE_DB = 'spendlog-statement-folders';
let statementRootHandle = null;

function openStatementHandleDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(STATEMENT_HANDLE_DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore('handles');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function loadStatementRootHandle() {
  const db = await openStatementHandleDb();
  return new Promise((resolve, reject) => {
    const request = db.transaction('handles', 'readonly').objectStore('handles').get('root');
    request.onsuccess = () => {
      db.close();
      resolve(request.result || null);
    };
    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

async function saveStatementRootHandle(handle) {
  const db = await openStatementHandleDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('handles', 'readwrite');
    transaction.objectStore('handles').put(handle, 'root');
    transaction.oncomplete = () => {
      db.close();
      resolve();
    };
    transaction.onerror = () => {
      db.close();
      reject(transaction.error);
    };
  });
}

function secureAccountFolderName(accountName) {
  return String(accountName)
    .normalize('NFKD')
    .replace(/[^\x00-\x7F]/g, '')
    .replace(/[\\/]/g, ' ')
    .replace(/ /g, '_')
    .replace(/[^A-Za-z0-9_.-]/g, '')
    .replace(/^[._]+|[._]+$/g, '');
}

/* =========================================================
   保存前两步检查（移植自 main_check_transaction_amount_signs.py
   与 main_check_transaction_dates.py），仅针对勾选 Save to File 的项。
   ========================================================= */
const NUMERIC_AMOUNT_RE = /^[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+)$/;

function isNumericAmount(value) {
  return NUMERIC_AMOUNT_RE.test(String(value ?? '').trim());
}

function parseAmountValue(value) {
  // 去掉末尾 " CR" 与千分位逗号后转数字
  const normalized = String(value ?? '').trim().replace(/\s+CR$/i, '').replace(/,/g, '');
  if (normalized === '') return NaN;
  const num = Number(normalized);
  return Number.isNaN(num) ? NaN : num;
}

function expectedSignRule(l0Category, l1Category) {
  const l0 = String(l0Category ?? '').trim().toLowerCase();
  const l1 = String(l1Category ?? '').trim().toLowerCase().replace(/ /g, '_');

  const rules = [];
  if (l0 === 'spend') rules.push(['l0=spend', true]);
  else if (l0 === 'income') rules.push(['l0=income', false]);
  if (l1 === 'transfer_out') rules.push(['l1=transfer_out', true]);
  else if (l1 === 'transfer_in') rules.push(['l1=transfer_in', false]);

  if (rules.length === 0) return null;
  const distinctSigns = new Set(rules.map(rule => rule[1]));
  if (distinctSigns.size > 1) {
    return { conflict: true, rules };
  }
  return { conflict: false, ruleName: rules[0][0], shouldBeNegative: rules[0][1] };
}

function describeTransactionRow(tx, rowNo) {
  const info = [];
  if (tx.account) info.push(tx.account);
  if (tx.date) info.push(tx.date);
  if (tx.transaction_detail) info.push(`"${tx.transaction_detail}"`);
  return info.length ? `第${rowNo}行 (${info.join(', ')})` : `第${rowNo}行`;
}

function validateTransactionsBeforeSave(transactions) {
  const amountErrors = [];
  const dateErrors = [];

  transactions.forEach((tx, index) => {
    if (!tx || tx.save_to_file === false) return; // 只检查勾选 Save to File 的项
    const rowNo = index + 1;

    // ---- 检查二：日期不能为空 ----
    if (String(tx.date ?? '').trim() === '') {
      dateErrors.push(`${describeTransactionRow(tx, rowNo)}: 日期为空`);
    }

    // ---- 检查一：金额格式与符号 ----
    const rawAmount = tx.amount ?? '';
    if (!isNumericAmount(rawAmount)) {
      amountErrors.push(`${describeTransactionRow(tx, rowNo)}: 金额不是有效数字 (${JSON.stringify(String(rawAmount))})`);
    }

    const amount = parseAmountValue(rawAmount);
    if (Number.isNaN(amount)) return; // 无法解析，符号检查跳过

    const rule = expectedSignRule(tx.l0_category, tx.l1_category);
    if (rule && rule.conflict) {
      amountErrors.push(`${describeTransactionRow(tx, rowNo)}: 符号规则冲突 ${JSON.stringify(rule.rules)}`);
      return;
    }
    if (rule === null || amount === 0) return;

    if ((amount < 0) !== rule.shouldBeNegative) {
      const expectText = rule.shouldBeNegative ? '应为负数' : '应为正数';
      amountErrors.push(
        `${describeTransactionRow(tx, rowNo)}: amount=${JSON.stringify(String(rawAmount))} ${expectText}（规则 ${rule.ruleName}）`
      );
    }
  });

  return { amountErrors, dateErrors };
}

function getCategoryTree() {
  return window.AppData?.categories || [];
}

function findCategory(categoryId, level, parentIds = {}) {
  const categories = getCategoryTree();
  if (level === 'l0') {
    return categories.find(item => item.id === categoryId);
  }

  const l0 = categories.find(item => item.id === parentIds.l0);
  if (!l0) return null;
  if (level === 'l1') {
    return l0.l1_cats?.find(item => item.id === categoryId) || null;
  }

  const l1 = l0.l1_cats?.find(item => item.id === parentIds.l1);
  if (!l1) return null;
  if (level === 'l2') {
    return l1.l2_cats?.find(item => item.id === categoryId) || null;
  }

  const l2 = l1.l2_cats?.find(item => item.id === parentIds.l2);
  if (!l2) return null;
  if (level === 'l3') {
    return l2.l3_cats?.find(item => item.id === categoryId) || null;
  }

  return null;
}

function getOptions(level, parentIds = {}) {
  const categories = getCategoryTree();
  if (level === 'l0') {
    return categories.map(item => ({ id: item.id, label: item.l0_name }));
  }

  const l0 = categories.find(item => item.id === parentIds.l0);
  if (!l0) return [];
  if (level === 'l1') {
    return (l0.l1_cats || []).map(item => ({ id: item.id, label: item.l1_name }));
  }

  const l1 = l0.l1_cats?.find(item => item.id === parentIds.l1);
  if (!l1) return [];
  if (level === 'l2') {
    return (l1.l2_cats || []).map(item => ({ id: item.id, label: item.l2_name }));
  }

  const l2 = l1.l2_cats?.find(item => item.id === parentIds.l2);
  if (!l2) return [];
  if (level === 'l3') {
    return (l2.l3_cats || []).map(item => ({ id: item.id, label: item.l3_name }));
  }

  return [];
}

function createCategorySelect(level, rowIndex, currentValue, parentIds = {}) {
  const select = document.createElement('select');
  select.className = 'transaction-table__select';
  select.dataset.level = level;
  select.dataset.rowIndex = rowIndex;
  select.dataset.l0 = parentIds.l0 || '';
  select.dataset.l1 = parentIds.l1 || '';
  select.dataset.l2 = parentIds.l2 || '';

  const options = getOptions(level, parentIds);
  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = 'Select';
  select.appendChild(defaultOption);

  options.forEach(item => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.label;
    option.selected = item.id === currentValue;
    select.appendChild(option);
  });

  if (currentValue && !options.some(item => item.id === currentValue)) {
    const fallback = document.createElement('option');
    fallback.value = currentValue;
    fallback.textContent = currentValue;
    fallback.selected = true;
    select.appendChild(fallback);
  }

  select.addEventListener('change', event => {
    const target = event.target;
    const level = target.dataset.level;
    const row = Number(target.dataset.rowIndex);
    const value = target.value;
    const tx = filled_transactions[row];
    if (!tx) return;

    if (level === 'l0') {
      tx.l0_category = value;
      tx.l1_category = '';
      tx.l2_category = '';
      tx.l3_category = '';
    } else if (level === 'l1') {
      tx.l1_category = value;
      tx.l2_category = '';
      tx.l3_category = '';
    } else if (level === 'l2') {
      tx.l2_category = value;
      tx.l3_category = '';
    } else if (level === 'l3') {
      tx.l3_category = value;
    }

    updateCategoryRow(row);
    window.filled_transactions = filled_transactions;
  });

  return select;
}

function populateSelect(select, level, rowIndex, currentValue, parentIds = {}) {
  select.innerHTML = '';
  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = 'Select';
  select.appendChild(defaultOption);

  const options = getOptions(level, parentIds);
  options.forEach(item => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.label;
    option.selected = item.id === currentValue;
    select.appendChild(option);
  });

  if (currentValue && !options.some(item => item.id === currentValue)) {
    const fallback = document.createElement('option');
    fallback.value = currentValue;
    fallback.textContent = currentValue;
    fallback.selected = true;
    select.appendChild(fallback);
  }
}

function updateCategoryRow(rowIndex) {
  const row = document.querySelector(`tr[data-row-index="${rowIndex}"]`);
  if (!row) return;

  const tx = filled_transactions[rowIndex];
  if (!tx) return;

  const l0Select = row.querySelector('select[data-level="l0"]');
  const l1Select = row.querySelector('select[data-level="l1"]');
  const l2Select = row.querySelector('select[data-level="l2"]');
  const l3Select = row.querySelector('select[data-level="l3"]');

  populateSelect(l0Select, 'l0', rowIndex, tx.l0_category, {});
  populateSelect(l1Select, 'l1', rowIndex, tx.l1_category, { l0: tx.l0_category });
  populateSelect(l2Select, 'l2', rowIndex, tx.l2_category, { l0: tx.l0_category, l1: tx.l1_category });
  populateSelect(l3Select, 'l3', rowIndex, tx.l3_category, { l0: tx.l0_category, l1: tx.l1_category, l2: tx.l2_category });

  l1Select.dataset.l0 = tx.l0_category || '';
  l2Select.dataset.l0 = tx.l0_category || '';
  l2Select.dataset.l1 = tx.l1_category || '';
  l3Select.dataset.l0 = tx.l0_category || '';
  l3Select.dataset.l1 = tx.l1_category || '';
  l3Select.dataset.l2 = tx.l2_category || '';
}

export function initLoadStatement() {
  if (initialized) return;
  initialized = true;

  console.log("📄 Load Statements init");

  /* ===============================
     模块内部共享状态
  =============================== */
  let selectedAccount = "";
  let selectedYear = "";
  let selectedMonth = "";
  const contextualPickerAvailable = typeof window.showOpenFilePicker === "function"
    && typeof window.showDirectoryPicker === "function"
    && typeof indexedDB !== "undefined";
  let selectedFile = null;

  let accountSelect = null;
  let yearSelect = null;
  let monthSelect = null;
  let uploadArea = null;
  let fileInput = null;
  let statementFolderButton = null;
  let uploadIcon = null;
  let uploadText = null;
  let uploadTitle = null;
  let uploadHint = null;
  let processBtn = null;
  let saveBtn = null;

  /* =====================================================
     1️⃣ 初始化 DOM 引用
  ===================================================== */
  function initDOM() {
    accountSelect = document.getElementById("account_select");
    yearSelect = document.getElementById("year_select");
    monthSelect = document.getElementById("month_select");
    uploadArea = document.getElementById("upload_area");
    fileInput = document.getElementById("pdf_input");
    statementFolderButton = document.getElementById("statement_folder_button");
    uploadIcon = uploadArea.querySelector(".load-statements__upload-icon");
    uploadText = uploadArea.querySelector(".load-statements__upload-text");
    uploadTitle = uploadText.querySelector(".load-statements__upload-title");
    uploadHint = uploadText.querySelector(".load-statements__upload-hint");
    processBtn = document.getElementById("process_btn");
    saveBtn = document.getElementById("save_btn");

    if (!accountSelect || !yearSelect || !monthSelect || !uploadArea || !fileInput || !statementFolderButton || !processBtn || !saveBtn) {
      console.error("❌ Load Statements: Required DOM elements not found");
      return false;
    }

    return true;
  }

  /* =====================================================
     2️⃣ 渲染账户选择下拉菜单
  ===================================================== */
  function renderAccountSelect() {
    const accountNames = (AppData.accountMeta || [])
      .flatMap(group => group.child_accounts || [])
      .filter(account => account.active === true)
      .map(account => account.name)
      .filter(Boolean);

    if (accountNames.length === 0) {
      console.warn("⚠️ No active accounts found in accountMeta");
      return;
    }

    // 清空现有选项（保留第一个占位符）
    accountSelect.innerHTML = '<option value="">-- Choose an account --</option>';

    // 添加所有账户
    accountNames.forEach(accountName => {
      const option = document.createElement("option");
      option.value = accountName;
      option.textContent = accountName;
      accountSelect.appendChild(option);
    });

    console.log("✅ Account select rendered with", accountNames.length, "accounts");
  }

  /* =====================================================
     2️⃣ 渲染年份选择下拉菜单
  ===================================================== */
  function renderYearSelect() {
    // 获取当前年份，并生成过去5年和未来1年的选项
    const currentYear = new Date().getFullYear();
    const years = [];

    for (let i = currentYear - 5; i <= currentYear + 1; i++) {
      years.push(i);
    }

    // 清空现有选项（保留第一个占位符）
    yearSelect.innerHTML = '<option value="">-- Choose a year --</option>';

    // 添加所有年份，当前年份作为默认选中
    years.forEach(year => {
      const option = document.createElement("option");
      option.value = year;
      option.textContent = year;
      if (year === currentYear) {
        option.selected = true;
        selectedYear = year;
      }
      yearSelect.appendChild(option);
    });

    console.log("✅ Year select rendered with", years.length, "years");
  }

  /* =====================================================
     2️⃣ 渲染月份选择下拉菜单
  ===================================================== */
  function renderMonthSelect() {
    const months = [
      { value: 1, label: "January" },
      { value: 2, label: "February" },
      { value: 3, label: "March" },
      { value: 4, label: "April" },
      { value: 5, label: "May" },
      { value: 6, label: "June" },
      { value: 7, label: "July" },
      { value: 8, label: "August" },
      { value: 9, label: "September" },
      { value: 10, label: "October" },
      { value: 11, label: "November" },
      { value: 12, label: "December" }
    ];

    // 清空现有选项（保留第一个占位符）
    monthSelect.innerHTML = '<option value="">-- Choose a month --</option>';

    // 添加所有月份，当前月份作为默认选中
    const currentMonth = new Date().getMonth() + 1;
    months.forEach(month => {
      const option = document.createElement("option");
      option.value = month.value;
      option.textContent = month.label;
      if (month.value === currentMonth) {
        option.selected = true;
        selectedMonth = month.value;
      }
      monthSelect.appendChild(option);
    });

    console.log("✅ Month select rendered with", months.length, "months");
  }

  /* =====================================================
     3️⃣ 处理文件选择
  ===================================================== */
  function handleFileSelect(file) {
    const extension = file?.name.split(".").pop().toLowerCase();
    if (file && !["pdf", "json"].includes(extension)) {
      alert("Please select a PDF or transaction JSON file");
      return;
    }

    selectedFile = file;

    if (file) {
      // 计算文件大小
      const fileSizeKB = (file.size / 1024).toFixed(2);
      // 获取文件名（不包含路径）
      const fileName = file.name;
      
      // 修改图标为文件名
      uploadIcon.textContent = fileName;
      
      // 在原位置显示文件信息
      uploadTitle.textContent = `✓ ${fileName}`;
      uploadHint.textContent = `${fileSizeKB} KB`;
      
      // 改变上传框的视觉样式
      uploadArea.classList.add("has-file");
      
      console.log("📂 File selected:", fileName);
    } else {
      // 恢复默认状态
      uploadIcon.textContent = "📄";
      // 恢复默认状态
      uploadTitle.textContent = "Drop a PDF or transaction JSON file here, or click to select";
      updateUploadDestinationHint();
      uploadArea.classList.remove("has-file");
      
      console.log("📂 File cleared");
    }
  }

  function applyStatementMetadata(metadata) {
    const account = String(metadata.account);
    if (![...accountSelect.options].some(option => option.value === account)) {
      accountSelect.add(new Option(account, account));
    }
    accountSelect.value = account;
    selectedAccount = account;

    const year = String(metadata.year);
    if (![...yearSelect.options].some(option => option.value === year)) {
      yearSelect.add(new Option(year, year));
    }
    yearSelect.value = year;
    selectedYear = year;

    selectedMonth = String(metadata.month);
    monthSelect.value = selectedMonth;
    updateUploadDestinationHint();
  }

  function updateUploadDestinationHint() {
    if (selectedFile) return;
    if (!selectedAccount || !selectedYear || !selectedMonth) {
      uploadHint.textContent = "Select an account, year, and month first";
      return;
    }

    const month = String(selectedMonth).padStart(2, "0");
    const accountFolder = secureAccountFolderName(selectedAccount);
    const destination = `${selectedYear}/${month}/${accountFolder}`;
    uploadHint.textContent = contextualPickerAvailable && statementRootHandle
      ? `Default folder: ${destination}`
      : `Target folder (choose manually): ${destination}`;
  }

  async function openContextualFilePicker() {
    if (!selectedAccount || !selectedYear || !selectedMonth) {
      alert("Please select an account, year, and month first");
      return;
    }
    if (!statementRootHandle) {
      fileInput.click();
      return;
    }

    try {
      const permission = await statementRootHandle.queryPermission({ mode: "readwrite" });
      if (permission !== "granted") {
        fileInput.click();
        return;
      }

      const yearDirectory = await statementRootHandle.getDirectoryHandle(String(selectedYear), { create: true });
      const monthDirectory = await yearDirectory.getDirectoryHandle(String(selectedMonth).padStart(2, "0"), { create: true });
      const accountDirectory = await monthDirectory.getDirectoryHandle(secureAccountFolderName(selectedAccount), { create: true });
      const [fileHandle] = await window.showOpenFilePicker({
        id: "spendlog-statement-file",
        startIn: accountDirectory,
        multiple: false,
        types: [
          {
            description: "PDF or transaction JSON",
            accept: {
              "application/pdf": [".pdf"],
              "application/json": [".json"],
            },
          },
        ],
      });
      handleFileSelect(await fileHandle.getFile());
    } catch (error) {
      if (error.name !== "AbortError") {
        console.error("Could not open statement PDF:", error);
        alert(error.message || "Could not open the selected statement folder");
      }
    }
  }

  /* =====================================================
     4️⃣ 绑定交互事件
  ===================================================== */
  function bindEvents() {
    if (contextualPickerAvailable) {
      loadStatementRootHandle()
        .then(handle => {
          statementRootHandle = handle;
          if (handle) {
            statementFolderButton.textContent = "Change estatements folder";
            updateUploadDestinationHint();
          }
        })
        .catch(error => console.error("Could not restore statement folder:", error));
    }

    // 账户选择变化
    accountSelect.addEventListener("change", (e) => {
      selectedAccount = e.target.value;
      console.log("🔖 Selected account:", selectedAccount);
      updateUploadDestinationHint();
    });

    // 年份选择变化
    yearSelect.addEventListener("change", (e) => {
      selectedYear = e.target.value;
      console.log("📅 Selected year:", selectedYear);
      updateUploadDestinationHint();
    });

    // 月份选择变化
    monthSelect.addEventListener("change", (e) => {
      selectedMonth = e.target.value;
      console.log("📅 Selected month:", selectedMonth);
      updateUploadDestinationHint();
    });

    // 文件输入变化
    fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      handleFileSelect(file);
    });

    // 上传区域点击
    uploadArea.addEventListener("click", (event) => {
      if (event.target === fileInput) return;
      if (contextualPickerAvailable && statementRootHandle) {
        void openContextualFilePicker();
      } else {
        fileInput.click();
      }
    });

    statementFolderButton.addEventListener("click", async () => {
      if (!contextualPickerAvailable) {
        alert("This browser cannot set a default folder. Use the upload area to choose a PDF manually.");
        return;
      }
      try {
        statementRootHandle = await window.showDirectoryPicker({
          id: "spendlog-estatements-root",
          mode: "readwrite",
        });
        await saveStatementRootHandle(statementRootHandle);
        statementFolderButton.textContent = "Change statement folder";
        updateUploadDestinationHint();
      } catch (error) {
        if (error.name !== "AbortError") {
          console.error("Could not set statement folder:", error);
          alert(error.message || "Could not access the statement folder");
        }
      }
    });

    // 拖拽事件
    uploadArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadArea.classList.add("active");
    });

    uploadArea.addEventListener("dragleave", () => {
      uploadArea.classList.remove("active");
    });

    uploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadArea.classList.remove("active");
      
      const file = e.dataTransfer.files[0];
      if (file) {
        handleFileSelect(file);
        // 同步文件输入值
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;
      }
    });

    // Process 按钮点击
    processBtn.addEventListener("click", () => {
      handleProcessClick();
    });

    saveBtn.addEventListener("click", () => {
      handleSaveClick();
    });
  }

  /* =====================================================
     5️⃣ Process 按钮处理
  ===================================================== */
  async function handleProcessClick() {
    if (!selectedFile) {
      alert("Please select a PDF or transaction JSON file");
      return;
    }

    if (!selectedAccount || !selectedYear || !selectedMonth) {
      alert("Please select an account, year, and month before processing");
      return;
    }

    console.log("🔄 Processing:", {
      account: selectedAccount,
      file: selectedFile.name
    });

    // 发送到后端进行分析
    await sendPdfToBackend();
  }

  async function handleSaveClick() {
    if (!filled_transactions.length) {
      alert("⚠️ No transactions to save");
      return;
    }

    // 保存前两步检查：仅针对勾选 Save to File 的项，两步都通过才允许保存
    const { amountErrors, dateErrors } = validateTransactionsBeforeSave(filled_transactions);
    if (amountErrors.length || dateErrors.length) {
      const lines = ['❌ 保存前检查未通过，请修正以下问题后再保存：'];
      if (amountErrors.length) {
        lines.push('', `【检查一·金额符号】(${amountErrors.length})`);
        amountErrors.forEach(msg => lines.push('• ' + msg));
      }
      if (dateErrors.length) {
        lines.push('', `【检查二·日期】(${dateErrors.length})`);
        dateErrors.forEach(msg => lines.push('• ' + msg));
      }
      alert(lines.join('\n'));
      console.warn('⛔ Save blocked by pre-save checks:', { amountErrors, dateErrors });
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
      const response = await fetch('/api/save_transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filled_transactions,
          account: selectedAccount,
          year: selectedYear,
          month: selectedMonth,
        }),
      });

      const result = await response.json();
      if (!response.ok || !result.success) {
        throw new Error(result.error || 'Failed to save');
      }

      alert(`✅ Saved ${result.updated_count || 0} transaction(s) to cache`);
    } catch (error) {
      console.error('❌ Save failed:', error);
      alert(`❌ ${error.message || 'Save failed'}`);
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    }
  }

  /* =====================================================
     6️⃣ 后端API调用
  ===================================================== */
  async function sendPdfToBackend() {
    const isJson = selectedFile.name.toLowerCase().endsWith(".json");
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('account', selectedAccount);
    formData.append('year', selectedYear);
    formData.append('month', selectedMonth);

    // 2️⃣ 更新UI - 禁用按钮并显示加载状态
    const originalText = processBtn.textContent;
    setProcessingState(true);

    try {
      // 3️⃣ 发送请求到后端
      console.log(`📤 Loading selected ${isJson ? "JSON" : "PDF"} file...`);
      
      const response = await fetch(
        isJson ? '/api/load_filled_transactions' : '/api/analyze_pdf',
        {
        method: 'POST',
        body: formData,
        },
      );

      // 4️⃣ 处理响应
      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      console.log("📥 Backend response:", result);

      // 5️⃣ 处理不同的响应状态
      if (result.success) {
        if (isJson) {
          applyStatementMetadata(result);
        }
        showSuccessResult(result.data);
      } else {
        showErrorMessage(result.error || "Analysis failed");
      }

    } catch (error) {
      // 6️⃣ 错误处理
      if (error.name === 'AbortError') {
        showErrorMessage("⏱️ Request timeout - analysis took too long (>30s)");
        console.error("❌ Request timeout");
      } else if (error instanceof TypeError) {
        showErrorMessage("❌ Network error - unable to reach server");
        console.error("❌ Network error:", error);
      } else {
        showErrorMessage(error.message || "❌ Unknown error occurred");
        console.error("❌ Error:", error);
      }
    } finally {
      // 7️⃣ 恢复UI状态
      setProcessingState(false);
    }
  }

  /* =====================================================
     7️⃣ 加载状态管理
  ===================================================== */
  function setProcessingState(isProcessing) {
    if (isProcessing) {
      processBtn.disabled = true;
      processBtn.classList.add("loading");
      processBtn.innerHTML = `<span class="spinner"></span> Processing...`;
      if (saveBtn) {
        saveBtn.disabled = true;
      }
      accountSelect.disabled = true;
      uploadArea.style.pointerEvents = "none";
      uploadArea.style.opacity = "0.6";
    } else {
      processBtn.disabled = false;
      processBtn.classList.remove("loading");
      processBtn.textContent = "Process";
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save";
      }
      accountSelect.disabled = false;
      uploadArea.style.pointerEvents = "auto";
      uploadArea.style.opacity = "1";
    }
  }

  /* =====================================================
     8️⃣ 结果展示
  ===================================================== */
  function renderTransactionTable(transactions) {
    const statusText = document.getElementById('transaction_table_status');
    const tableBody = document.getElementById('transaction_table_body');
    if (!tableBody || !statusText) {
      console.error('❌ Transaction table DOM not found');
      return;
    }

    filled_transactions = Array.isArray(transactions) ? transactions : [];
    window.filled_transactions = filled_transactions;

    if (filled_transactions.length === 0) {
      statusText.textContent = 'No transactions to display.';
      tableBody.innerHTML = '';
      return;
    }

    statusText.textContent = `Loaded ${filled_transactions.length} transactions.`;
    tableBody.innerHTML = '';

    filled_transactions.forEach((transaction, index) => {
      const row = document.createElement('tr');
      row.dataset.rowIndex = index;
      if (transaction.from_cache === 'No') {
        row.classList.add('transaction-table__row--highlight');
      }

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = !!transaction.save_to_cache;
      checkbox.addEventListener('change', () => {
        transaction.save_to_cache = checkbox.checked;
        window.filled_transactions = filled_transactions;
      });

      const saveToFileCheckbox = document.createElement('input');
      saveToFileCheckbox.type = 'checkbox';
      saveToFileCheckbox.checked = transaction.save_to_file !== false;
      transaction.save_to_file = saveToFileCheckbox.checked;
      saveToFileCheckbox.addEventListener('change', () => {
        transaction.save_to_file = saveToFileCheckbox.checked;
        window.filled_transactions = filled_transactions;
      });

      const l0Select = createCategorySelect('l0', index, transaction.l0_category || '', {});
      const l1Select = createCategorySelect('l1', index, transaction.l1_category || '', { l0: transaction.l0_category });
      const l2Select = createCategorySelect('l2', index, transaction.l2_category || '', { l0: transaction.l0_category, l1: transaction.l1_category });
      const l3Select = createCategorySelect('l3', index, transaction.l3_category || '', { l0: transaction.l0_category, l1: transaction.l1_category, l2: transaction.l2_category });

      const noteText = transaction.note || '';
      const transactionDetailInput = document.createElement('input');
      transactionDetailInput.type = 'text';
      transactionDetailInput.value = transaction.transaction_detail || '';
      transactionDetailInput.className = 'transaction-table__cache-input';
      transactionDetailInput.addEventListener('input', () => {
        transaction.transaction_detail = transactionDetailInput.value;
        window.filled_transactions = filled_transactions;
      });

      const cacheKeywordInput = document.createElement('input');
      cacheKeywordInput.type = 'text';
      cacheKeywordInput.value = transaction.cache_keyword || '';
      cacheKeywordInput.className = 'transaction-table__cache-input';
      cacheKeywordInput.addEventListener('input', () => {
        transaction.cache_keyword = cacheKeywordInput.value;
        window.filled_transactions = filled_transactions;
      });

      const datePicker = document.createElement('div');
      datePicker.className = 'transaction-table__date-picker';
      const dateText = document.createElement('span');
      dateText.className = 'transaction-table__date-text';
      const dateInput = document.createElement('input');
      dateInput.type = 'date';
      dateInput.className = 'transaction-table__date-input';
      dateInput.setAttribute('aria-label', 'Choose transaction date');
      dateInput.value = String(transaction.date || '').slice(0, 10);
      dateText.textContent = dateInput.value;
      dateInput.addEventListener('change', () => {
        transaction.date = dateInput.value;
        dateText.textContent = dateInput.value;
        window.filled_transactions = filled_transactions;
      });
      datePicker.append(dateText, dateInput);

      const amountInput = document.createElement('input');
      amountInput.type = 'text';
      amountInput.value = transaction.amount ?? '';
      amountInput.className = 'transaction-table__cache-input';
      amountInput.addEventListener('input', () => {
        transaction.amount = amountInput.value;
        window.filled_transactions = filled_transactions;
      });

      row.appendChild(createCell(index + 1));
      row.appendChild(createCell(null, datePicker));
      row.appendChild(createCell(transaction.account || ''));
      row.appendChild(createCell(null, transactionDetailInput));
      row.appendChild(createCell(null, l0Select));
      row.appendChild(createCell(null, l1Select));
      row.appendChild(createCell(null, l2Select));
      row.appendChild(createCell(null, l3Select));
      row.appendChild(createCell(null, amountInput, 'transaction-table__amount'));
      row.appendChild(createCell(noteText));
      row.appendChild(createCell(null, saveToFileCheckbox));
      row.appendChild(createCell(null, checkbox));
      row.appendChild(createCell(null, cacheKeywordInput));

      tableBody.appendChild(row);
    });
  }

  function createCell(text, element = null, className = '') {
    const td = document.createElement('td');
    if (className) {
      td.className = className;
    }
    if (element) {
      td.appendChild(element);
    } else {
      td.textContent = text;
    }
    return td;
  }

  function showSuccessResult(data) {
    const existingResult = document.getElementById("analysis_result");
    if (existingResult) {
      existingResult.remove();
    }

    const resultContainer = document.createElement("div");
    resultContainer.id = "analysis_result";
    resultContainer.className = "analysis-result success";
    resultContainer.innerHTML = `
      <div class="analysis-result__content">
        <h3>✅ Analysis Complete</h3>
        <p>${Array.isArray(data) ? `Loaded ${data.length} transactions.` : 'Analysis returned no table data.'}</p>
      </div>
    `;

    uploadArea.parentNode.insertBefore(resultContainer, uploadArea.nextSibling);
    renderTransactionTable(data);
    console.log("✅ Result displayed");
  }

  function showErrorMessage(message) {
    // 清空之前的结果容器（如果存在）
    const existingResult = document.getElementById("analysis_result");
    if (existingResult) {
      existingResult.remove();
    }

    // 创建错误容器
    const resultContainer = document.createElement("div");
    resultContainer.id = "analysis_result";
    resultContainer.className = "analysis-result error";
    
    resultContainer.innerHTML = `
      <div class="analysis-result__content">
        <h3>${message}</h3>
        <button class="close-btn" onclick="this.parentElement.parentElement.remove()">✕ Dismiss</button>
      </div>
    `;

    // 添加到页面
    uploadArea.parentNode.insertBefore(resultContainer, uploadArea.nextSibling);
    
    console.error("❌ Error displayed:", message);
  }

  /* =====================================================
     6️⃣ 初始化
  ===================================================== */
  if (!initDOM()) {
    console.error("❌ Failed to initialize Load Statements");
    return;
  }

  renderAccountSelect();
  renderYearSelect();
  renderMonthSelect();
  bindEvents();
  updateUploadDestinationHint();

  console.log("✅ Load Statements initialized");
}
