/* Слайдер главной страницы: автопрокрутка, стрелки, точки */
(function () {
  const slides = document.querySelectorAll('.slide');
  const dotsBox = document.getElementById('slider-dots');
  if (!slides.length || !dotsBox) return;

  let current = 0;
  let timer = null;

  slides.forEach((_, index) => {
    const dot = document.createElement('button');
    dot.setAttribute('aria-label', 'Слайд ' + (index + 1));
    dot.addEventListener('click', () => show(index));
    dotsBox.appendChild(dot);
  });
  const dots = dotsBox.querySelectorAll('button');

  function show(index) {
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, i) => slide.classList.toggle('is-active', i === current));
    dots.forEach((dot, i) => dot.classList.toggle('active', i === current));
    restart();
  }

  function restart() {
    clearInterval(timer);
    timer = setInterval(() => show(current + 1), 6000);
  }

  document.querySelector('[data-testid="slider-prev"]')
    .addEventListener('click', () => show(current - 1));
  document.querySelector('[data-testid="slider-next"]')
    .addEventListener('click', () => show(current + 1));

  show(0);
})();

/* Плавное появление блоков при прокрутке */
(function () {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  document.querySelectorAll('[data-reveal]').forEach((el) => observer.observe(el));
})();

/* Тень шапки при прокрутке */
(function () {
  const header = document.getElementById('header');
  window.addEventListener('scroll', () => {
    header.classList.toggle('scrolled', window.scrollY > 10);
  });
})();

/* Мобильное меню */
(function () {
  const burger = document.getElementById('burger');
  const nav = document.getElementById('nav');
  if (burger && nav) {
    burger.addEventListener('click', () => nav.classList.toggle('open'));
  }
})();

/* Автоскрытие уведомлений + пульс счётчика корзины */
(function () {
  document.querySelectorAll('.flash').forEach((flash) => {
    setTimeout(() => {
      flash.classList.add('hide');
      setTimeout(() => flash.remove(), 450);
    }, 4000);
  });

  document.querySelectorAll('[data-testid="add-to-cart"]').forEach((button) => {
    button.addEventListener('click', () => {
      const badge = document.querySelector('[data-testid="cart-badge"]');
      if (badge) {
        badge.classList.remove('pulse');
        void badge.offsetWidth; /* перезапуск анимации */
        badge.classList.add('pulse');
      }
    });
  });
})();