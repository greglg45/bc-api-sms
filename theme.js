(function(){
  function applyTheme(theme){
    document.documentElement.setAttribute('data-bs-theme', theme);
    var btn = document.getElementById('themeToggle');
    if(btn){
      btn.textContent = theme === 'dark' ? '☀' : '🌙';
    }
  }
  function init(){
    var stored = localStorage.getItem('theme');
    if(stored){
      applyTheme(stored);
    } else if(window.matchMedia('(prefers-color-scheme: dark)').matches){
      applyTheme('dark');
    }
  }
  window.toggleTheme = function(){
    var current = document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
    var next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', next);
    applyTheme(next);
  };
  window.addEventListener('DOMContentLoaded', init);
})();
