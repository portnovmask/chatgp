document.getElementById("chat-list").addEventListener("click", async (event) => {
    const selectedChat = event.target.closest("[data-chat-id]");

    if (selectedChat) {
        const chatId = selectedChat.getAttribute("data-chat-id");
        console.log("Выбранный чат ID:", chatId);

        await fetchChatData(chatId); // Загружаем чат асинхронно
    }
});


document.getElementById("new-chat-btn").addEventListener("click", async () => {
    try {
        // Удаляем chat_id_cookie
        document.cookie = "chat_id_cookie=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;";

        // Обновляем страницу, чтобы создать новый чат
        window.location.href = "/reset_chat?new_chat=1";
    } catch (error) {
        console.error("Ошибка при создании нового чата:", error);
    }
});




async function fetchChatData(chatId) {
    try {
        const response = await fetch(`/get_chat_body?chat_id=${chatId}`);

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
        let processedMessages = data.chat_body.map(message => `
            <div class="query-body">${message.prompt}<button class="edit-button"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-pencil-square" viewBox="0 0 16 16">
                      <path d="M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z"/>
                      <path fill-rule="evenodd" d="M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5z"/>
                    </svg></button></div>
            <div class="response-body">${message.body}</div>
            <hr>
        `).join(""); // Вставляем HTML в `#article`
        chatArticle.innerHTML = processedMessages;
        console.log("Чат загружен:", data.chat_body);

         // Прокручиваем страницу после загрузки чата
        setTimeout(() => {
            chatArticle.scrollIntoView({ behavior: "smooth", block: "end" });
        }, 100);

        document.cookie = `chat_id_cookie=${data.chat_id}; path=/; max-age=3600`;

    } catch (error) {
        console.error("Ошибка при загрузке чата:", error);
    }
}


