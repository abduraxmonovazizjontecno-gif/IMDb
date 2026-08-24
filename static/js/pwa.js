// Service Worker Registration & PWA Setup
(function () {
    'use strict';

    // Register Service Worker
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/js/service-worker.js', {
            scope: '/'
        }).then(registration => {
            console.log('✅ Service Worker registered:', registration);

            // Check for updates periodically
            setInterval(() => {
                registration.update();
            }, 3600000); // Every hour
        }).catch(error => {
            console.warn('⚠️ Service Worker registration failed:', error);
        });

        // Listen for updates
        navigator.serviceWorker.addEventListener('controllerchange', () => {
            // Notify user about app update
            if (window.cinemaToast) {
                cinemaToast('🔄 Yangi versiya mavjud. Sahifani yangilang.');
            }
        });
    }

    // Install PWA Prompt
    let deferredPrompt;
    const installPrompt = document.getElementById('install-prompt');

    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        if (installPrompt) {
            installPrompt.style.display = 'flex';
        }
    });

    // Handle install button
    const installBtn = document.getElementById('install-btn');
    if (installBtn) {
        installBtn.addEventListener('click', async () => {
            if (!deferredPrompt) return;
            deferredPrompt.prompt();
            const { outcome } = await deferredPrompt.userChoice;
            console.log(`User response to install prompt: ${outcome}`);
            deferredPrompt = null;
            if (installPrompt) {
                installPrompt.style.display = 'none';
            }
        });
    }

    // Hide install prompt on app installed
    window.addEventListener('appinstalled', () => {
        console.log('✅ CINEMA app installed');
        if (installPrompt) {
            installPrompt.style.display = 'none';
        }
        if (window.cinemaToast) {
            cinemaToast('✅ CINEMA ilovasiga xush kelibsiz!');
        }
    });

    // Connection status notification
    function updateConnectionStatus() {
        if (navigator.onLine) {
            console.log('✅ Online');
        } else {
            console.log('⚠️ Offline - Using cached content');
            if (window.cinemaToast) {
                cinemaToast('📡 Siz oflayn rejimdasiz - kesh dan foydalanayapti');
            }
        }
    }

    window.addEventListener('online', updateConnectionStatus);
    window.addEventListener('offline', updateConnectionStatus);

    // Notification permission
    function requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    console.log('✅ Notification permission granted');
                }
            });
        }
    }

    // Request notification permission on first interaction
    document.addEventListener('click', requestNotificationPermission, { once: true });
})();
