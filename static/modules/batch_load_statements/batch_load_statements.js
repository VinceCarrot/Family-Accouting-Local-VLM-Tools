// static/modules/batch_load_statements/batch_load_statements.js

let initialized = false;

// 复用与 Load Statements 相同的 IndexedDB 句柄库，使“estatements 文件夹”两页共享
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

// 与后端 secure_filename 对齐的账户文件夹名规整
function secureAccountFolderName(accountName) {
  return String(accountName)
    .normalize('NFKD')
    .replace(/[^\x00-\x7F]/g, '')
    .replace(/[\\/]/g, ' ')
    .replace(/ /g, '_')
    .replace(/[^A-Za-z0-9_.-]/g, '')
    .replace(/^[._]+|[._]+$/g, '');
}

// securedFolderName -> 真实账户名（用于调用后端分析时传入正确的 account）
function buildFolderToAccountMap() {
  const map = {};
  const accountNames = (window.AppData?.accountMeta || [])
    .flatMap(group => group.child_accounts || [])
    .map(account => account.name)
    .filter(Boolean);
  accountNames.forEach(name => {
    map[secureAccountFolderName(name)] = name;
  });
  return map;
}

export function initBatchLoadStatements() {
  if (initialized) return;
  initialized = true;

  console.log('🗂 Batch Load Statements init');

  const contextualPickerAvailable = typeof window.showDirectoryPicker === 'function'
    && typeof indexedDB !== 'undefined';

  let selectedYear = '';
  let selectedMonth = '';
  let rows = []; // { folderName, accountName, year, month, pdfName, pdfHandle, accountDirHandle, checkboxEl, statusCell }

  let yearSelect = null;
  let monthSelect = null;
  let folderButton = null;
  let loadBtn = null;
  let processBtn = null;
  let listBody = null;
  let listStatus = null;

  /* ===== DOM ===== */
  function initDOM() {
    yearSelect = document.getElementById('batch_year_select');
    monthSelect = document.getElementById('batch_month_select');
    folderButton = document.getElementById('batch_folder_button');
    loadBtn = document.getElementById('batch_load_btn');
    processBtn = document.getElementById('batch_process_btn');
    listBody = document.getElementById('batch_list_body');
    listStatus = document.getElementById('batch_list_status');

    if (!yearSelect || !monthSelect || !folderButton || !loadBtn || !processBtn || !listBody || !listStatus) {
      console.error('❌ Batch Load Statements: Required DOM elements not found');
      return false;
    }
    return true;
  }

  /* ===== 下拉渲染（与 Load Statements 一致，默认当前年月） ===== */
  function renderYearSelect() {
    const currentYear = new Date().getFullYear();
    yearSelect.innerHTML = '<option value="">-- Choose a year --</option>';
    for (let y = currentYear - 5; y <= currentYear + 1; y++) {
      const option = document.createElement('option');
      option.value = y;
      option.textContent = y;
      if (y === currentYear) {
        option.selected = true;
        selectedYear = String(y);
      }
      yearSelect.appendChild(option);
    }
  }

  function renderMonthSelect() {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December',
    ];
    const currentMonth = new Date().getMonth() + 1;
    monthSelect.innerHTML = '<option value="">-- Choose a month --</option>';
    months.forEach((label, idx) => {
      const value = idx + 1;
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      if (value === currentMonth) {
        option.selected = true;
        selectedMonth = String(value);
      }
      monthSelect.appendChild(option);
    });
  }

  /* ===== 权限 ===== */
  async function ensurePermission(handle, mode) {
    if (!handle) return false;
    const opts = { mode };
    if ((await handle.queryPermission(opts)) === 'granted') return true;
    return (await handle.requestPermission(opts)) === 'granted';
  }

  /* ===== Load PDF：遍历 年/月 下所有账户文件夹，读取唯一 PDF 文件名 ===== */
  async function handleLoadClick() {
    if (!contextualPickerAvailable) {
      alert('This browser does not support folder access. Please use a Chromium-based browser.');
      return;
    }
    if (!selectedYear || !selectedMonth) {
      alert('Please select a year and month first');
      return;
    }
    if (!statementRootHandle) {
      alert('Please set the estatements folder first (Change estatements folder)');
      return;
    }
    if (!(await ensurePermission(statementRootHandle, 'read'))) {
      alert('Permission to read the estatements folder was denied');
      return;
    }

    const monthStr = String(selectedMonth).padStart(2, '0');
    listStatus.textContent = 'Scanning folders...';
    listBody.innerHTML = '';
    rows = [];

    let monthDir;
    try {
      const yearDir = await statementRootHandle.getDirectoryHandle(String(selectedYear), { create: false });
      monthDir = await yearDir.getDirectoryHandle(monthStr, { create: false });
    } catch (error) {
      if (error.name === 'NotFoundError') {
        listStatus.textContent = `No statements found for ${selectedYear}-${monthStr}.`;
        return;
      }
      console.error('Could not open month folder:', error);
      listStatus.textContent = error.message || 'Could not open the month folder';
      return;
    }

    const folderToAccount = buildFolderToAccountMap();
    const collected = [];

    for await (const [name, handle] of monthDir.entries()) {
      if (handle.kind !== 'directory') continue;

      let pdfName = null;
      let pdfHandle = null;
      for await (const [fileName, fileHandle] of handle.entries()) {
        if (fileHandle.kind === 'file' && fileName.toLowerCase().endsWith('.pdf')) {
          pdfName = fileName;
          pdfHandle = fileHandle;
          break; // 每个账户文件夹只有唯一一个 pdf
        }
      }
      if (!pdfName) continue; // 没有 PDF 的文件夹跳过

      collected.push({
        folderName: name,
        accountName: folderToAccount[name] || name,
        year: String(selectedYear),
        month: monthStr,
        pdfName,
        pdfHandle,
        accountDirHandle: handle,
      });
    }

    collected.sort((a, b) => a.accountName.localeCompare(b.accountName));
    rows = collected;
    renderList();
  }

  function renderList() {
    listBody.innerHTML = '';
    if (rows.length === 0) {
      listStatus.textContent = `No statements found for ${selectedYear}-${String(selectedMonth).padStart(2, '0')}.`;
      return;
    }
    listStatus.textContent = `Found ${rows.length} statement(s).`;

    rows.forEach(rowData => {
      const tr = document.createElement('tr');

      const checkCell = document.createElement('td');
      checkCell.className = 'batch-load__col-check';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = true; // 默认勾选
      checkCell.appendChild(checkbox);
      rowData.checkboxEl = checkbox;

      const statusCell = document.createElement('td');
      statusCell.className = 'batch-load__col-status';
      rowData.statusCell = statusCell;

      const actionCell = document.createElement('td');
      actionCell.className = 'batch-load__col-action';
      const reprocessBtn = document.createElement('button');
      reprocessBtn.type = 'button';
      reprocessBtn.className = 'batch-load__reprocess-btn';
      reprocessBtn.textContent = 'Reprocess';
      reprocessBtn.addEventListener('click', () => { void handleReprocessClick(rowData); });
      actionCell.appendChild(reprocessBtn);
      rowData.reprocessBtn = reprocessBtn;

      tr.appendChild(checkCell);
      tr.appendChild(createCell(rowData.year));
      tr.appendChild(createCell(rowData.month));
      tr.appendChild(createCell(rowData.accountName));
      tr.appendChild(createCell(rowData.pdfName));
      tr.appendChild(statusCell);
      tr.appendChild(actionCell);

      listBody.appendChild(tr);
    });
  }

  function createCell(text) {
    const td = document.createElement('td');
    td.textContent = text;
    return td;
  }

  function setStatus(rowData, text, variant) {
    if (!rowData.statusCell) return;
    rowData.statusCell.innerHTML = '';
    if (!text) return;
    const label = document.createElement('span');
    label.className = `batch-load__status-label batch-load__status-label--${variant}`;
    label.textContent = text;
    rowData.statusCell.appendChild(label);
  }

  /* ===== Batch Process：逐个处理勾选的 PDF ===== */
  async function handleBatchProcess() {
    const selected = rows.filter(r => r.checkboxEl && r.checkboxEl.checked);
    if (selected.length === 0) {
      alert('Please select at least one statement to process');
      return;
    }
    if (!(await ensurePermission(statementRootHandle, 'readwrite'))) {
      alert('Write permission to the estatements folder was denied (needed to save JSON)');
      return;
    }

    setBatchProcessingState(true);

    let processed = 0;
    for (const rowData of selected) {
      const ok = await processOneRow(rowData);
      if (ok) processed += 1;
      listStatus.textContent = `Processed ${processed}/${selected.length}...`;
    }

    listStatus.textContent = `Done. Processed ${processed}/${selected.length} statement(s). Review them in Load Statements via "load json".`;
    setBatchProcessingState(false);
  }

  /* ===== 单行处理（批量与单独 Reprocess 共用） ===== */
  async function processOneRow(rowData) {
    setStatus(rowData, 'Processing…', 'processing');
    try {
      const file = await rowData.pdfHandle.getFile();
      const formData = new FormData();
      formData.append('file', file, rowData.pdfName);
      formData.append('account', rowData.accountName);
      formData.append('year', rowData.year);
      formData.append('month', String(Number(rowData.month))); // 后端按数字解析

      const response = await fetch('/api/analyze_pdf', { method: 'POST', body: formData });
      const result = await response.json();
      if (!response.ok || !result.success) {
        throw new Error(result.error || `HTTP ${response.status}`);
      }

      // 按与 main_pdf_batch_process 相同的命名把标准化 JSON 写回账户文件夹
      await writeJson(rowData, result.data);

      setStatus(rowData, 'Processed', 'processed');
      return true;
    } catch (error) {
      console.error(`❌ Process failed for ${rowData.accountName}:`, error);
      setStatus(rowData, 'Error', 'error');
      return false;
    }
  }

  /* ===== 单行 Reprocess ===== */
  async function handleReprocessClick(rowData) {
    if (!(await ensurePermission(statementRootHandle, 'readwrite'))) {
      alert('Write permission to the estatements folder was denied (needed to save JSON)');
      return;
    }
    if (rowData.reprocessBtn) rowData.reprocessBtn.disabled = true;
    await processOneRow(rowData);
    listStatus.textContent = `Reprocessed ${rowData.accountName} (${rowData.year}-${rowData.month}).`;
    if (rowData.reprocessBtn) rowData.reprocessBtn.disabled = false;
  }

  async function writeJson(rowData, data) {
    const fileName = `${rowData.folderName}.json`; // 等价于 secure_filename(account) + ".json"
    const fileHandle = await rowData.accountDirHandle.getFileHandle(fileName, { create: true });
    const writable = await fileHandle.createWritable();
    await writable.write(JSON.stringify(Array.isArray(data) ? data : [], null, 2));
    await writable.close();
  }

  function setBatchProcessingState(isProcessing) {
    processBtn.disabled = isProcessing;
    loadBtn.disabled = isProcessing;
    yearSelect.disabled = isProcessing;
    monthSelect.disabled = isProcessing;
    folderButton.disabled = isProcessing;
    rows.forEach(r => { if (r.reprocessBtn) r.reprocessBtn.disabled = isProcessing; });
    if (isProcessing) {
      processBtn.classList.add('loading');
      processBtn.innerHTML = '<span class="spinner"></span> Processing...';
    } else {
      processBtn.classList.remove('loading');
      processBtn.textContent = 'Batch Process';
    }
  }

  /* ===== 事件绑定 ===== */
  function bindEvents() {
    if (contextualPickerAvailable) {
      loadStatementRootHandle()
        .then(handle => {
          statementRootHandle = handle;
          if (handle) folderButton.textContent = 'Change estatements folder';
        })
        .catch(error => console.error('Could not restore statement folder:', error));
    }

    yearSelect.addEventListener('change', e => { selectedYear = e.target.value; });
    monthSelect.addEventListener('change', e => { selectedMonth = e.target.value; });

    folderButton.addEventListener('click', async () => {
      if (!contextualPickerAvailable) {
        alert('This browser cannot set a default folder.');
        return;
      }
      try {
        statementRootHandle = await window.showDirectoryPicker({
          id: 'spendlog-estatements-root', // 与 Load Statements 同一 id，复用同一文件夹
          mode: 'readwrite',
        });
        await saveStatementRootHandle(statementRootHandle);
        folderButton.textContent = 'Change estatements folder';
      } catch (error) {
        if (error.name !== 'AbortError') {
          console.error('Could not set statement folder:', error);
          alert(error.message || 'Could not access the statement folder');
        }
      }
    });

    loadBtn.addEventListener('click', () => { void handleLoadClick(); });
    processBtn.addEventListener('click', () => { void handleBatchProcess(); });
  }

  /* ===== 初始化 ===== */
  if (!initDOM()) {
    console.error('❌ Failed to initialize Batch Load Statements');
    return;
  }

  renderYearSelect();
  renderMonthSelect();
  bindEvents();

  console.log('✅ Batch Load Statements initialized');
}
