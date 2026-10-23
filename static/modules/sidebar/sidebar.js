let initialized = false;

export function initSidebar() {
  if (initialized) return;
  initialized = true;

  const tabs = {
    tab_nav_load_statements: {
      nav: 'tab_nav_load_statements',
      page: 'page_load_statements',
    },
    tab_nav_batch_load_statements: {
      nav: 'tab_nav_batch_load_statements',
      page: 'page_batch_load_statements',
    }
  };

  const all_nav_ids = Object.values(tabs).map(tab => tab.nav);
  const all_page_ids = Object.values(tabs).map(tab => tab.page);

  function showTab(selected_tab_id) {
    all_page_ids.forEach(id => {
      const page = document.getElementById(id);
      if (page) page.classList.remove('active');
    });

    all_nav_ids.forEach(id => {
      const tab_nav = document.getElementById(id);
      if (tab_nav) tab_nav.classList.remove('active');
    });

    const selected_tab = tabs[selected_tab_id];
    if (!selected_tab) return;

    document.getElementById(selected_tab.page)?.classList.add('active');
    document.getElementById(selected_tab.nav)?.classList.add('active');

    // 共享的底部 transaction table 只在 Load Statements 页显示
    const mainBottom = document.querySelector('.main-bottom');
    if (mainBottom) {
      mainBottom.style.display = selected_tab_id === 'tab_nav_load_statements' ? '' : 'none';
    }
    // console.log(`✅ Page switched to ${selected_tab_id}`);
  }

  // 绑定点击事件
  Object.keys(tabs).forEach(tab_id => {
    const navEl = document.getElementById(tab_id);
    if (!navEl) return;

    navEl.addEventListener('click', () => {
      console.log(`🔖 Navigating to ${tab_id}...`);
      showTab(tab_id);
    });
  });

  // 初始化默认页面
  showTab('tab_nav_load_statements');
}
