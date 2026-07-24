// Mobile nav toggle
document.getElementById('navToggle')?.addEventListener('click', () => {
  document.querySelector('.nav-links').classList.toggle('open');
});

// Animate metric bars on scroll
const observer = new IntersectionObserver((entries) => {
  entries.forEach(el => {
    if (el.isIntersecting) el.target.style.width = el.target.style.getPropertyValue('--w') || el.target.getAttribute('style').match(/--w:([^%]+%)/)?.[1];
  });
}, { threshold: 0.2 });

document.querySelectorAll('.metric-bar, .model-bar').forEach(bar => {
  const orig = bar.style.cssText;
  bar.style.cssText = orig.replace(/width[^;]+;/, 'width:0;');
  setTimeout(() => observer.observe(bar), 100);
});

// Auto-dismiss flash messages
document.querySelectorAll('.flash').forEach(f => {
  setTimeout(() => f.style.animation = 'slideOut .3s ease forwards', 4000);
  setTimeout(() => f.remove(), 4400);
});
