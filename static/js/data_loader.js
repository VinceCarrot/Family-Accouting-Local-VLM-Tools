// js/data_loader.js

/* ---------- 工具函数 ---------- */

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}`);
  return res.json();
}

/* ---------- 主入口 ---------- */

export async function loadAllData() {
  console.log('📦 Loading local data...');

  // 加载 pdf_pwd.json
  const pdfPwd = await loadJSON('/static/data/pdf_pwd.json');
  const accountFormat = await loadJSON('/static/data/account_format.json');
  const categoryCache = await loadJSON('/static/data/category_cache.json');
  
  // 添加到现有的 AppData 对象
  window.AppData.pdf_pwd = pdfPwd;
  window.AppData.account_format = accountFormat;
  window.AppData.category_cache = categoryCache;
  // console.log('📥 pdf_pwd.json loaded:', pdfPwd);
  console.log('✅ All local data loaded');
  return window.AppData;
}
