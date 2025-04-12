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