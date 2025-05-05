document.addEventListener("DOMContentLoaded",
            async () => {
                console.log("🚀 Страница загружена, вызываем fetchWithAuth...");
                const response = await fetchWithAuth("/me");
                if (response.ok) {
                    console.log("✅ Данные пользователя загружены!");
                    const data = await response.json();
                    //document.getElementById("username").textContent = data.email;  // Например, вставляем имя пользователя в HTML
                } else {
                    console.error("Ошибка загрузки профиля");
                }

                // ⏱️ Таймер: каждые 10 минут обновляем access_token
                setInterval(async () => {
                    console.log("⏳ Таймер: обновление access_token...");
                    const refreshResponse = await fetch("/refresh", {
                        method: "POST",
                        credentials: "include"
                    });
                    console.log(`🔁 /refresh через таймер: ${refreshResponse.status}`);
                    if (!refreshResponse.ok) {
                        console.warn("⚠️ Refresh не удался. Перенаправление на авторизацию...");
                        window.location.replace("/authorize");
                    }
                }, 10 * 60 * 1000); // каждые 10 минут
                 });



        async function fetchWithAuth(url, options = {}) {
            console.log(`📡 Запрос: ${url}`);
            if (!options.headers) options.headers = {};
            let response = await fetch(url, {
                ...options,
                credentials: "include" // Передаём куки
            });
            console.log(`🔹 Ответ от сервера: ${response.status}`);
            if (response.status === 401) {
                console.log("Access token expired, refreshing...");
                const refreshResponse = await fetch("/refresh", { method: "POST", credentials: "include" });
                console.log(`🔹 Ответ от /refresh: ${refreshResponse.status}`);
            if (refreshResponse.ok) {
                // Повторяем запрос после обновления токена
                response = await fetch(url, {
                    ...options,
                    credentials: "include"
                });
            } else {
                console.log("Refresh token expired, logging out...");
                window.location.replace("/authorize")
                return;
            }
                    }

                    return response;
    }