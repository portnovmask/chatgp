document.getElementById("chat-list").addEventListener("click", async (event) => {
    // Убираем класс "active" у всех кнопок перед назначением нового активного элемента
    document.querySelectorAll(".list-button").forEach(btn => btn.classList.remove("active"));

    // Определяем, был ли клик на элемент с data-chat-id
    const selectedChat = event.target.closest("[data-chat-id]");

    if (selectedChat) {
        const chatId = selectedChat.getAttribute("data-chat-id");
        console.log("Выбранный чат ID:", chatId);

        // Делаем кликнутую кнопку активной
        selectedChat.classList.add('active');

        // Загружаем данные чата асинхронно
        await fetchChatData(chatId);
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
        let processedMessages = await Promise.all(
        data.chat_body.map(async (message) => {
            let filteredText = await filterText(message.body); // Ждем обработку текста
            return `
                <div class="query-body">${message.prompt}
   
                </div>
                <div class="response-body">${filteredText}<button class="copy-button"><img src="static/img/icons/copy.svg" width="20" height="20" autofocus></button></div>
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


