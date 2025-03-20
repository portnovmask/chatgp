const submitButton = document.querySelector('#submit');
// const containerMain = document.querySelector(".container-main");

const submitIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-send" viewBox="0 0 16 16">
  <path d="M15.854.146a.5.5 0 0 1 .11.54l-5.819 14.547a.75.75 0 0 1-1.329.124l-3.178-4.995L.643 7.184a.75.75 0 0 1 .124-1.33L15.314.037a.5.5 0 0 1 .54.11ZM6.636 10.07l2.761 4.338L14.13 2.576zm6.787-8.201L1.591 6.602l4.339 2.76z"/>
</svg>`;

const stopIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-stop-fill" viewBox="0 0 16 16">
  <path d="M5 3.5h6A1.5 1.5 0 0 1 12.5 5v6a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 11V5A1.5 1.5 0 0 1 5 3.5"/>
</svg>`;


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

    summaries.forEach((summary, index) => {
        const button = document.createElement("button");
        button.classList.add("list-button");  //  Добавляем нужный стиль
        button.setAttribute("data-chat-id", summary.chat_id);

        const smallText = document.createElement("small");
        smallText.textContent = summary.summary;

        button.appendChild(smallText);
        chatList.appendChild(button);  //  Добавляем в `chat-list`
        chatList.appendChild(document.createElement("br"));

        if (index === 0) {
        button.classList.add("active");
            }
    });
}



      let eventSource=null;

      submitButton.onclick = () => {
          const promptInput = document.querySelector('#prompt');
          const prompt = promptInput.value;
          let streamText = ''
          const newElement = document.getElementById('events');
          promptInput.style.height = "auto";

          if (eventSource) {
              eventSource.close();
              eventSource=null;
              submitButton.innerHTML=submitIcon;
              newElement.innerText = '';
          }

          if (isValidInput(prompt)) {
              eventSource = new EventSource(`/stream?prompt=${encodeURIComponent(prompt)}`);
              submitButton.innerHTML=stopIcon;
          }
          else {
              return;
          }
          eventSource.onmessage = async (event) => {  // Добавляем `async`
                if (event.data !== undefined) {
                    const parent = document.querySelector("#article");

                    const data = JSON.parse(event.data); // Парсим JSON
                    promptInput.value = "";
                    const finishReason = data.finish_reason;
                    const totalTokens = data.usage;
                    let chunk_id = data.id;
                    const userQuery = escapeHtml(data.user_query);
                    parent.innerHTML = `<div id="${chunk_id}">
                       <div class="query-body">${userQuery}<button class="edit-button"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-pencil-square" viewBox="0 0 16 16">
                      <path d="M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z"/>
                      <path fill-rule="evenodd" d="M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5z"/>
                    </svg></button></div></div>
                    `;

                    if (finishReason === "End") {
                        console.log("Closing EventSource...");
                        streamText = newElement.innerText
                        newElement.innerText = '';
                        let chatBlock = `<div class="response-body">${escapeHtml(streamText)}</div>
                                        </div><hr>`
                        console.log(totalTokens);
                        console.log(data.id);
                        eventSource.close();
                        eventSource=null;
                        submitButton.innerHTML=submitIcon;

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

