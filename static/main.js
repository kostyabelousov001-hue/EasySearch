document.addEventListener("DOMContentLoaded", () => {
    
    // --- 1. Эффект "Дыма" (слежение за курсором) ---
    const smokeTrail = document.getElementById("smoke-trail");
    
    if (smokeTrail) {
        document.addEventListener("mousemove", (e) => {
            if (smokeTrail.style.opacity === '0') {
                smokeTrail.style.opacity = '1';
            }
            smokeTrail.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
        });

        document.addEventListener("mouseleave", () => {
            smokeTrail.style.opacity = '0';
        });
    }

    // --- 2. Логика вкладок ---
    const tabContainer = document.querySelector(".tabs");
    if (tabContainer) {
        const tabs = tabContainer.querySelectorAll(".tab-link");
        const contents = document.querySelectorAll(".tab-content");

        tabs.forEach(tab => {
            tab.addEventListener("click", () => {
                const targetId = tab.dataset.tab;
                const targetContent = document.getElementById(targetId);

                tabs.forEach(t => t.classList.remove("active"));
                contents.forEach(c => c.classList.remove("active"));

                tab.classList.add("active");
                if (targetContent) {
                    targetContent.classList.add("active");
                }
            });
        });
    }

    // --- 3. Клиент Socket.IO (на всех страницах) ---
    const socket = io();

    socket.on('connect', () => {
        console.log('Socket.IO Подключен');
    });
    
    socket.on('connect_error', (err) => {
        console.error('Ошибка подключения Socket.IO:', err.message);
    });

    socket.on('disco_update', (data) => {
        if (data.active) {
            document.body.classList.add('disco-mode');
        } else {
            document.body.classList.remove('disco-mode');
        }
    });

    socket.on('admin_message_broadcast', (data) => {
        const popup = document.getElementById('admin-message-popup');
        if (popup) {
            popup.textContent = data.message;
            popup.style.display = 'block';

            setTimeout(() => {
                popup.style.display = 'none';
            }, 5000);
        }
    });

    // --- 4. Логика Админ-панели (Только на admin.html) ---
    const discoBtn = document.getElementById('toggle-disco-btn');
    const msgForm = document.getElementById('admin-message-form');

    if (discoBtn) {
        discoBtn.addEventListener('click', () => {
            const isActive = document.body.classList.contains('disco-mode');
            socket.emit('toggle_disco_event', { active: !isActive });
        });
    }

    if (msgForm) {
        msgForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const input = document.getElementById('admin-message-input');
            const message = input.value;
            if (message) {
                socket.emit('send_admin_message_event', { message: message });
                input.value = '';
            }
        });
    }

    // --- 5. Логика Чат-бота Gemini (Только на gemini.html) ---
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatHistory = document.getElementById('chat-history');

    if (chatForm) {

        function appendMessage(user, text, isUser) {
            const msgDiv = document.createElement('div');
            msgDiv.classList.add('message');
            msgDiv.classList.add(isUser ? 'user-message' : 'ai-message');
            
            const strong = document.createElement('strong');
            strong.textContent = isUser ? 'Вы:' : `${user}:`;
            
            // НОВОЕ: Используем innerHTML и замену \n на <br> для поддержки форматирования
            const textContent = document.createElement('div');
            textContent.innerHTML = text.replace(/\n/g, '<br>');

            msgDiv.appendChild(strong); // Заголовок (Вы/Gemini)
            msgDiv.appendChild(textContent); // Текст с форматированием
            
            chatHistory.appendChild(msgDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const message = chatInput.value.trim();
            if (message) {
                appendMessage('Вы', message, true);
                socket.emit('send_gemini_message', { message: message });
                chatInput.value = '';
            }
        });

        socket.on('receive_gemini_message', (data) => {
            appendMessage(data.user, data.text, false);
        });
    }
});