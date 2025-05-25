const newChat = document.getElementById("new-chat-btn")

document.getElementById("chat-list").addEventListener("click", async (event) => {
    const deleteBtn = event.target.closest(".delete-chat");
    const chatEntry = event.target.closest("[data-chat-id]");


    // 👉 Удаление чата
    if (deleteBtn && chatEntry) {
        const chatId = chatEntry.getAttribute("data-chat-id");

        const confirmDelete = confirm("Вы уверены, что хотите удалить этот чат?");
        if (!confirmDelete) return;

        try {
            const response = await fetchWithAuth("/delete-chat/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ chat_id: chatId }),
            });

            const result = await response.json();

            if (result.deletion_status === "deleted") {
                chatEntry.remove();
            } else {
                alert("Не удалось удалить чат.");
            }
        } catch (error) {
            console.error("Ошибка удаления чата:", error);
            alert("Произошла ошибка при удалении чата.");
        }
        return;
    }

    // 👉 Переключение чата
    if (chatEntry) {
        // Убираем класс "active" у всех кнопок
        document.querySelectorAll(".chat-entry").forEach(btn => btn.classList.remove("active"));

        // Назначаем новый активный чат
        chatEntry.classList.add('active');

        const chatId = chatEntry.getAttribute("data-chat-id");
        console.log("Выбранный чат ID:", chatId);
        await fetchChatData(chatId);
    }
});



if (newChat) {
    newChat.addEventListener("click", async () => {
        try {
            // Удаляем chat_id_cookie
            document.cookie = "chat_id_cookie=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;";

            // Обновляем страницу, чтобы создать новый чат
            window.location.href = "/reset_chat?new_chat=1";
        } catch (error) {
            console.error("Ошибка при создании нового чата:", error);
        }
    });
}



async function fetchChatData(chatId) {
    try {
        const response = await fetchWithAuth(`/get_chat_body?chat_id=${chatId}`);

        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.status}`);
        }

        const data = await response.json();

        // const chatContainer = document.getElementById("chat-container");
        const chatArticle = document.getElementById("article");
        if (!chatArticle) {
            console.error("Chat container не найден!");
            return;
        }

        // Если сервер вернул ошибку
        if (data.error) {
            chatArticle.innerHTML = `<p>${data.error}</p>`;
            return;
        }
        //  Очистка контейнера перед загрузкой нового чата
        chatArticle.innerHTML = "";

        // Обрабатываем `message.body` асинхронно
        let processedMessages = await Promise.all(
        data.chat_body.map(async (message) => {
            let filteredText = await filterText(message.body); // Ждем обработку текста
            return `
                <div class="query-body">${message.prompt}
   
                </div>
                <div class="response-body">${filteredText}</div>
                <hr>
            `;
        })
    );

    // Вставляем HTML после обработки всех сообщений
    chatArticle.innerHTML = processedMessages.join("");
    console.log("Чат загружен:", data.chat_body);
    Prism.highlightAll();
         // Прокручиваем страницу после загрузки чата
        setTimeout(() => {
            chatArticle.scrollIntoView({ behavior: "smooth", block: "end" });
        }, 100);

        document.cookie = `chat_id_cookie=${data.chat_id}; path=/; max-age=3600`;

    } catch (error) {
        console.error("Ошибка при загрузке чата:", error);
    }
}


