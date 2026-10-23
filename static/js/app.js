// static/js/app.js

import { loadAllData } from './data_loader.js';

import { initHeader } from '../modules/header/header.js';
import { initSidebar } from '../modules/sidebar/sidebar.js';
import { initLoadStatement } from '../modules/load_statements/load_statements.js';
import { initBatchLoadStatements } from '../modules/batch_load_statements/batch_load_statements.js';
// import { initDashboard } from '../modules/dash_board/dash_board.js';
// import { initMonthlyReport } from '../modules/monthly_report/monthly_report.js';
// import { initStatistics } from '../modules/statistics/statistics.js';
// import { initTools } from '../modules/tools/tools.js';
// import { initTransactionHistory } from '../modules/transaction_history/transaction_history.js';


async function fetchAppDataFromA() {
  try {
    // 假设网页A在局域网 IP: http://192.168.1.100:5000
    const res = await fetch('http://192.168.1.33:5000/get_appdata');
    // const res = await fetch('http://127.0.0.1:5000/get_appdata');
    if (!res.ok) throw new Error("Failed to fetch AppData from A");

    const data = await res.json();

    // 保存到前端全局变量
    window.AppData = data;

    // 1️⃣ 加载全量数据
    await loadAllData();

    console.log("📥 AppData fetched from A:", data);

    // 同步到网页B后端
    await fetch('/upload_appdata', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    console.log("💾 AppData synced to B backend");

    console.log('✅ AppData ready', window.AppData);

  } catch (err) {
    console.error("❌ Error fetching AppData from A:", err);
    window.AppData = null;
  }

  syncAppData(window.AppData);
}

export async function syncAppData(AppData) {
  await fetch('/upload_appdata', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(AppData)
  });
}


async function bootstrap() {
  console.log('🚀 App starting');

  // 1️⃣ 加载全量数据
  // await loadAllData();
  await fetchAppDataFromA();

  console.log('📊 Data ready', window.AppData);

  // 2️⃣ 初始化模块
  initHeader();
  initSidebar();
  initLoadStatement();
  initBatchLoadStatements();
  // initDashboard();
  // initMonthlyReport();
  // initStatistics();
  // initTools();
  // initTransactionHistory();

  console.log('✅ App ready');
}

bootstrap();
