const submitButton = document.querySelector('#submit');
// const containerMain = document.querySelector(".container-main");


    document.addEventListener("input", function (event) {
    if (event.target.tagName.toLowerCase() === "textarea") {
        event.target.style.height = "auto"; // Сбрасываем высоту, чтобы пересчитать
        event.target.style.height = event.target.scrollHeight + "px"; // Устанавливаем новую высоту
    }
});

// Функция проверки содержимого поля
function isValidInput(text) {
    return text.trim() !== "";    //!/^[^a-zA-Z0-9а-яА-Я]+$/.test(text)
}



async function replaceCodeBlocksStream(text) {


    let parts = text.split(/```([\s\S]*?)```/g);

    return parts.map((part, index) => {
        if (index % 2 === 1) {
            // Это код -> Оставляем переносы строк
            return `
                <div class="code-snippet">
                <pre class="code-body"><code class="no-keep-markup">${escapeHtml(part)}</code></pre>
                <button class="copy-button"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-copy" viewBox="0 0 16 16">
                <path fill-rule="evenodd" d="M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm2-1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1zM2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1h1v1a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1v1z"/>
                </svg></button>
                </div>
                    `;
        } else {

             // return `<div class="response-body-plain"><pre>${part.replace(/^###\s*(.+)$/gm, "<strong>$1</strong>")}</pre></div>`;
             return `<pre class="response-body-plain no-keep-markup">${part.replace(/^###\s*(.+)$/gm, "<strong>$1</strong>")
                 .replace(/\*\*(.*?)\*\*/g, "<u>$1</u>")
                 .replace(/ {3,}/g, "  ")
                 .replace(/\n{2,}/g, "\n")}</pre>`;
            // return part;
        }
    }).join("");
}


async function fetchUpdatedSummaries() {
    try {
        const response = await fetch("/update_summaries", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error("Ошибка при обновлении summaries");
        }

        updateSummariesUI(data.summaries);

    } catch (error) {
        console.error("Ошибка:", error);
    }
}



function updateSummariesUI(summaries) {
    const chatList = document.getElementById("chat-list");
    chatList.innerHTML = "";  // Очищаем список перед обновлением

    summaries.forEach(summary => {
        const button = document.createElement("button");
        button.classList.add("list-button");  // ✅ Добавляем нужный стиль
        button.setAttribute("data-chat-id", summary.chat_id);

        const smallText = document.createElement("small");
        smallText.textContent = summary.summary;

        button.appendChild(smallText);
        chatList.appendChild(button);  // ✅ Добавляем в `chat-list`
        chatList.appendChild(document.createElement("br")); // ✅ Перенос строки (если нужен)
    });
}



      let eventSource;

      submitButton.onclick = () => {
          const promptInput = document.querySelector('#prompt');
          const prompt = promptInput.value;
          let streamText = ''
          promptInput.style.height = "auto";

          if (eventSource) {
              eventSource.close();
          }

          if (isValidInput(prompt)) {
              eventSource = new EventSource(`/stream?prompt=${encodeURIComponent(prompt)}`);
          }
          else {
              return;
          }
          eventSource.onmessage = async (event) => {  // Добавляем `async`
                if (event.data !== undefined) {
                    const parent = document.querySelector("#article");
                    const newElement = document.getElementById('events');
                    const data = JSON.parse(event.data); // Парсим JSON
                    promptInput.value = "";
                    const finishReason = data.finish_reason;
                    const totalTokens = data.usage;
                    let chunk_id = data.id;
                    const userQuery = escapeHtml(data.user_query);
                    parent.innerHTML = `<div id="${chunk_id}"<div class="query-body">${userQuery}</div>`;

                    if (finishReason === "End") {
                        console.log("Closing EventSource...");
                        streamText = newElement.innerText
                        newElement.innerText = '';
                        let chatBlock = `<div class="response-body">${escapeHtml(streamText)}</div>
                                        </div><hr><br>`
                        console.log(totalTokens);
                        console.log(data.id);
                        eventSource.close();

                        parent.innerHTML += chatBlock;
                        // promptInput.style.height = "auto";
                        // setTimeout(() => {
                        //     document.querySelector(".container-main").style.display = "block";
                        // }, 100);

                        setTimeout(async () => {
                            await fetchUpdatedSummaries();
                        }, 5000);
                    // window.location.reload();
                    } else if (finishReason === "stop") {
                        newElement.innerText += ' ';
                    } else {

                        //await streamToContainer(data.content, newElement);
                        newElement.innerText += data.content;


                        //Прокручиваем страницу после загрузки чата
                        //  setTimeout(() => {
                        //     newElement.scrollIntoView({ behavior: "smooth", block: "end" });
                        //     }, 100);

                        setTimeout(() => {
                            const container = document.querySelector(".container-main"); // Родитель с overflow-y: scroll;
                            container.scrollTop = container.scrollHeight; //  Прокручиваем к последнему элементу
                        }, 100);

                    }
            }
        };

      };

      document.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault(); // Отмена переноса строки
        submitButton.click(); // Вызываем уже существующий обработчик
    }
});

