// 模块内部的私有状态
let initialized = false;

export function initHeader() {
  if (initialized) return;
  initialized = true;

  console.log('Header init');

  bindEvents();
  render();
}

/* ---------- 私有函数 ---------- */

function bindEvents() {
  const btn = document.querySelector('#refresh-header');
  if (!btn) return;

  btn.addEventListener('click', () => {
    render();
  });
}

function render() {

  if (!AppData) {
    console.warn('Header: no data');
    return;
  }

  // const data_transactions = AppData.transactions;
  // const data_category = AppData.categories;
  // const data_account_meta = AppData.accountMeta;

  // 渲染图表 / DOM
  console.log('render header', AppData);
}
