// Универсальная функция для синхронизации авторизации между вкладками
let sendAuthEvent;
let listenAuthEvents;

function isAuthenticated() {
    return document.cookie.includes("has_auth=true");
}


// Проверяем поддержку BroadcastChannel
if ("BroadcastChannel" in window) {
    // ✅ BroadcastChannel поддерживается
    const channel = new BroadcastChannel("auth");

    sendAuthEvent = (type) => {
        channel.postMessage({ type, timestamp: Date.now() });
    };

    listenAuthEvents = (callback) => {
        channel.onmessage = (event) => {
            callback(event.data);
        };
    };
} else {
    // ❌ BroadcastChannel не поддерживается — fallback на localStorage
    sendAuthEvent = (type) => {
        localStorage.setItem("auth_event", JSON.stringify({ type, timestamp: Date.now() }));
    };

    listenAuthEvents = (callback) => {
        window.addEventListener("storage", (event) => {
            if (event.key === "auth_event" && event.newValue) {
                callback(JSON.parse(event.newValue));
            }
        });
    };
}

// Главная логика, которая срабатывает при загрузке страницы
document.addEventListener("DOMContentLoaded", async () => {
    // Слушаем события, связанные с авторизацией
    listenAuthEvents(({ type }) => {
        if (type === "token_refreshed") {
            //console.log("🔁 Токен обновлён в другой вкладке");
        }
        if (type === "logout") {
            // console.log("🚪 Выход в другой вкладке");
            window.location.replace("/api/logout");
        }
    });
    // ✅ Проверяем: если у пользователя нет access_token, не обновляем
    if (!isAuthenticated()) {
        // console.log("👤 Гость. Пропускаем refresh.");
        return;
    }

    // Немедленно обновляем токен, если он устарел
    const refreshResponse = await fetch("/api/refresh", {
        method: "POST",
        credentials: "include"
    });
    if (refreshResponse.ok) {
        sendAuthEvent("token_refreshed");
    } else {
        sendAuthEvent("logout");
        return window.location.replace("/api/logout");
    }

    // Запрашиваем данные о пользователе после обновления токена
    const response = await fetchWithAuth("/api/me");
    if (response.ok) {
        const data = await response.json();
        //console.log("✅ Данные пользователя:", data);
    }

    // Таймер для регулярного обновления access_token каждые 10 минут
    setInterval(async () => {
        const refreshResponse = await fetch("/api/refresh", {
            method: "POST",
            credentials: "include"
        });
        if (refreshResponse.ok) {
            sendAuthEvent("token_refreshed");
        } else {
            sendAuthEvent("logout");
            window.location.replace("/api/logout");
        }
    }, 10 * 60 * 1000); // каждые 10 минут
});

        async function fetchWithAuth(url, options = {}) {
    try {
        if (!options.headers) options.headers = {};

        let response = await fetch(url, {
            ...options,
            credentials: "include"
        });

        if (response.status === 401) {
            // console.log("Access token expired, refreshing...");
            const refreshResponse = await fetch("/api/refresh", {
                method: "POST",
                credentials: "include"
            });

            if (refreshResponse.ok) {
                localStorage.setItem("token-refreshed", Date.now());
                // Повторяем исходный запрос
                response = await fetch(url, {
                    ...options,
                    credentials: "include"
                });
            } else {
                // console.warn("Refresh token expired. Redirecting...");
                window.location.replace("/api/logout");
                return;
            }
        }

        return response;
    } catch (err) {
        console.error(" Network error:", err);
        alert("Ошибка соединения. Попробуйте позже.");
        throw err;
    }
}
