const parent = document.querySelector("#article");

const submitButton = document.querySelector('#submit');
const searchButton = document.querySelector('#search-button');
// const containerMain = document.querySelector(".container-main");

const submitIcon = `<img src="/static/img/icons/send-2.svg" width="18" height="18" autofocus alt="send">`;

const stopIcon = `<img src="/static/img/icons/player-stop.svg" width="18" height="18" autofocus alt="stop">`;



async function filterText(text) {
    const response = await fetchWithAuth("/format-text/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
    });
    const data = await response.json();
    return data.formatted_text; // Возвращает HTML
}

//Регулирование высоты поля ввода

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




//Обновление списка чатов из базы

async function fetchUpdatedSummaries() {
    try {
        const response = await fetchWithAuth("/update_summaries", {
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

    summaries.forEach((summary, index) => {
        const chat_entry = document.createElement("div");
        const button = document.createElement("button");
        const deleteBtn = document.createElement("button");
        const img = document.createElement("img");
        img.src = "/static/img/icons/x.svg";
        img.width = 14;
        img.alt = "Удалить чат";
        deleteBtn.appendChild(img);
        deleteBtn.classList.add("delete-chat")
        button.classList.add("list-button");
        chat_entry.setAttribute("data-chat-id", summary.chat_id);
        chat_entry.classList.add("chat-entry");
        const smallText = document.createElement("small");
        smallText.textContent = summary.summary;

        button.appendChild(smallText);
        chat_entry.appendChild(button);
        chat_entry.appendChild(deleteBtn);
        chatList.appendChild(chat_entry);  //  Добавляем в `chat-list`

        if (index === 0) {
        document.querySelectorAll(".chat-entry").forEach(btn => btn.classList.remove("active"));
        chat_entry.classList.add("active");
            }
    });
}


if (submitButton) {
    let eventSource = null;

    submitButton.onclick = () => {
        const promptInput = document.querySelector('#prompt');
        const prompt = promptInput.value;
        let streamText = ''
        const newElement = document.getElementById('events');
        promptInput.style.height = "auto";

        if (eventSource) {
            eventSource.close();
            eventSource = null;
            submitButton.innerHTML = submitIcon;
            newElement.innerText = '';

        }

        if (isValidInput(prompt)) {
            eventSource = new EventSource(`/stream?prompt=${encodeURIComponent(prompt)}`);
            submitButton.innerHTML = stopIcon;
            //newElement.innerText += prompt;
        } else {
            return;
        }
        eventSource.onmessage = async (event) => {  // Добавляем `async`
            if (event.data !== undefined) {


                const data = JSON.parse(event.data); // Парсим JSON
                promptInput.value = "";
                const finishReason = data.finish_reason;
                const totalTokens = data.usage;
                let chunk_id = data.id;
                const userQuery = escapeHtml(data.user_query);


                if (finishReason === "End") {
                    console.log("Closing EventSource...");
                    streamText = await filterText(newElement.innerText)
                    newElement.innerText = '';
                    let chatBlock = `<div class="response-body">${streamText}</div>
                                </div><br><hr>`
                    console.log(totalTokens);
                    console.log(data.id);
                    eventSource.close();
                    eventSource = null;
                    submitButton.innerHTML = submitIcon;
                    parent.innerHTML += `<div id="${chunk_id}">
               <div class="query-body">${userQuery}<button class="edit-button">
               <img src="/static/img/icons/edit.svg" width="18" height="18" alt="edit">
                </button>
                </div>
                </div>
            `;
                    parent.innerHTML += chatBlock;
                    Prism.highlightAll();

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
}

      document.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault(); // Отмена переноса строки
        submitButton.click(); // Вызываем уже существующий обработчик
    }
});

if (searchButton) {
          searchButton.addEventListener("click", async () => {
              const searchPrompt = document.getElementById("search-input").value;
                console.log(searchPrompt);
              if (isValidInput(searchPrompt)) {

                  try {
                      const response = await fetchWithAuth(`/search?prompt=${encodeURIComponent(searchPrompt)}`);

                      if (response.redirected) {
                          window.location.href = response.url; // перенаправление на /authorize
                          return;
                      }

                      const data = await response.json();
                      let searchBlock;

                      if (data.status === "error" || data.status === "info") {
                          searchBlock = `<div class="response-body">${data.message}</div>
                                </div><br><hr>`;
                          parent.innerHTML += `<div id="${data.id}">
               <div class="query-body">${searchPrompt}<button class="edit-button">
               <img src="/static/img/icons/edit.svg" width="18" height="18" alt="edit">
                </button>
                </div>
                </div>
            `;
                          parent.innerHTML += searchBlock;
                      } else {
                          searchBlock = `<div class="response-body">${data.response}</div>
                                </div><br><hr>`;
                          parent.innerHTML += `<div id="${data.id}">
               <div class="query-body">${searchPrompt}<button class="edit-button">
               <img src="/static/img/icons/edit.svg" width="18" height="18" alt="edit">
                </button>
                </div>
                </div>
            `;
                          parent.innerHTML += searchBlock;
                      }

                  } catch (error) {
                      console.error("Ошибка при запросе поиска:", error);
                  }
              }
          });
      }


    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    function updateToggleButtonText(currentParam) {
        const button = document.getElementById("param-toggle");
        if (currentParam === "search") {
            button.innerHTML = `<img src="/static/img/icons/list-search.svg" width="18" height="18"  alt="поиск">`;
        } else {
            button.innerHTML = `<img src="/static/img/icons/send-2.svg" width="18" height="18" alt="чат">`;
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const currentParam = getCookie("param") || "stream";
        updateToggleButtonText(currentParam);

        document.getElementById("param-toggle").addEventListener("click", () => {
            const nextParam = currentParam === "stream" ? "search" : "stream";
            window.location.href = `/change_param?param=${nextParam}`;
        });
    });

