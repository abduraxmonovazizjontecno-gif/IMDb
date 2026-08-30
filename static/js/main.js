(function () {
    'use strict';

    // Render-bloklovchi bo'lmasligi uchun shrift CSS ini JS orqali (CSP-safe) ulaymiz.
    // CSP inline script'larni taqiqlaydi, shuning uchun tashqi fayldan qo'shamiz.
    (function loadFonts() {
        if (!window.matchMedia) return;
        var href = 'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap';
        if (document.querySelector('link[href="' + href + '"]')) return;
        var l = document.createElement('link');
        l.rel = 'stylesheet';
        l.href = href;
        document.head.appendChild(l);
    })();

    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!reduced) {
        document.documentElement.classList.add('js-motion');

        var header = document.querySelector('header');
        if (header) {
            function onScroll() {
                header.classList.toggle('scrolled', window.scrollY > 12);
            }
            window.addEventListener('scroll', onScroll, { passive: true });
            onScroll();
        }

        document.querySelectorAll('.poster img, .film-poster img, .person-photo img, .cast-ph img')
            .forEach(function (img) {
                if (img.complete) {
                    img.classList.add('loaded');
                } else {
                    img.addEventListener('load', function () { img.classList.add('loaded'); });
                }
            });

        var revealEls = document.querySelectorAll('.reveal');
        if ('IntersectionObserver' in window && revealEls.length) {
            var io = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                        io.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });
            revealEls.forEach(function (el) { io.observe(el); });
        } else {
            revealEls.forEach(function (el) { el.classList.add('visible'); });
        }
    }

    var burger = document.getElementById('nav-burger');
    var drawer = document.getElementById('drawer');
    var overlay = document.getElementById('drawer-overlay');
    if (burger && drawer && overlay) {
        function closeDrawer() {
            drawer.classList.remove('open');
            overlay.hidden = true;
            burger.setAttribute('aria-expanded', 'false');
        }
        burger.addEventListener('click', function () {
            var open = drawer.classList.toggle('open');
            burger.setAttribute('aria-expanded', String(open));
            overlay.hidden = !open;
        });
        overlay.addEventListener('click', closeDrawer);
        drawer.querySelectorAll('a, button').forEach(function (el) {
            el.addEventListener('click', closeDrawer);
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeDrawer();
        });
    }

    var toastWrap = null;
    window.cinemaToast = function (msg) {
        if (!toastWrap) {
            toastWrap = document.createElement('div');
            toastWrap.className = 'toast-wrap';
            document.body.appendChild(toastWrap);
        }
        var t = document.createElement('div');
        t.className = 'toast';
        t.textContent = msg;
        toastWrap.appendChild(t);
        requestAnimationFrame(function () { t.classList.add('in'); });
        setTimeout(function () {
            t.classList.remove('in');
            setTimeout(function () { t.remove(); }, 300);
        }, 2400);
    };
})();
