const parent = document.querySelector("#article");
const csrfToken = document.getElementById('csrf_token');
const submitButton = document.querySelector('#submit');
const searchButton = document.querySelector('#search-button');
const showUploadBtn = document.getElementById("show-upload-btn");
const uploadWrapper = document.getElementById("upload-wrapper");
const uploadInput = document.getElementById("upload-input");
const uploadButton = document.getElementById("upload-btn");
const previewDiv = document.getElementById("image-preview");
const deleteIconButton = document.getElementById("delete-icon-button");
const textarea = document.querySelector(".text-area");
const paramButton = document.getElementById("param-toggle");
const uploadInfo = document.getElementById("upload-info");
let imagePath = null;
let imgLink = null;
const fallbackPath = "/static/img/icons/user.svg";
// const containerMain = document.querySelector(".container-main");

const submitIcon = `<img src="/static/img/icons/send-2.svg" width="18" height="18" autofocus alt="send">`;

const stopIcon = `<img src="/static/img/icons/player-stop.svg" class="blink" width="18" height="18" autofocus alt="stop">`;

function generateId() {
  return 'id-' + Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
}

const uniqueId = generateId(); // Например: id-lkfn8r1ggkx


async function filterText(text) {
    const response = await fetchWithAuth("/api/format-text/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
    });
    const data = await response.json();
    return data.formatted_text; // Возвращает HTML
}

function validateImage(imagePath, fallbackPath, callback) {
  const img = new Image();
  img.onload = () => callback('/image-preview/' + imagePath);         // если загрузилось — используем оригинал
  img.onerror = () => callback(fallbackPath);     // если ошибка — используем заглушку
  img.src = '/image-preview/' + imagePath;
}

//Регулирование высоты поля ввода

//     document.addEventListener("input", function (event) {
//     if (event.target.tagName.toLowerCase() === "textarea") {
//         event.target.style.height = "auto"; // Сбрасываем высоту, чтобы пересчитать
//         event.target.style.height = event.target.scrollHeight + "px"; // Устанавливаем новую высоту
//     }
// });

if (textarea) {
    textarea.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = this.scrollHeight + "px";
    });
}

// Функция проверки содержимого поля
function isValidInput(text) {
    return text.trim() !== "";    //!/^[^a-zA-Z0-9а-яА-Я]+$/.test(text)
}




//Обновление списка чатов из базы

async function fetchUpdatedSummaries() {
    try {
        const response = await fetchWithAuth("/api/update_summaries", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            }
        });

        const data = await response.json();

        if (!response.ok) {
            console.error("Ошибка при запросе поиска:", response.statusText);
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

    submitButton.onclick = async () => {
        const promptInput = document.querySelector('#prompt');
        const prompt = promptInput.value;
        const newElement = document.getElementById('events');
        let streamText = '';

        promptInput.style.height = "auto";
        newElement.innerText = '';

        if (!isValidInput(prompt)) return;

        submitButton.disabled = true;
        submitButton.innerHTML = stopIcon;

        //удаляем картинку
        if (previewDiv) {
        const icon = previewDiv.querySelector("img");
        if (icon) icon.remove();
        deleteIconButton.style.display = "none";
        showUploadBtn.disabled = false;
        }

        try {
            const response = await fetchWithAuth("/api/stream", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    prompt: prompt,
                    csrf_token: csrfToken.value,
                    extras: imgLink || ""

                })
            });

            if (response.redirected) {
                window.location.href = response.url;
                return;
            }

            if (!response.ok) {
                if (response.status === 403) {
                            window.location.replace("/api/logout");
                        }
                parent.innerHTML += `<div class="response-body">Ошибка соединения, повторите попытку позже</div>`;
                imagePath = null;
                showUploadBtn.style.display = "flex";
            }

            // ⬇️ Очищаем поле ВВОДА, как только убедились, что всё пошло
            promptInput.value = "";
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let partial = "";
            if (imagePath) {
                validateImage(imagePath, fallbackPath, (finalSrc) => {
                imagePath.src = finalSrc;
            });
                imagePath.style.display = "block";
            }
            parent.innerHTML += `
                                <div id="${generateId()}">
                                    <div class="query-body">${escapeHtml(prompt)}<button class="edit-button" disabled>
                                        <img src="/static/img/icons/edit.svg" width="18" height="18" alt="edit">
                                    </button></div>
                                </div>
                            `;
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                partial += decoder.decode(value, { stream: true });

                // Можно разбивать на события (если приходят по `\n\n`)
                const lines = partial.split("\n\n");
                partial = lines.pop(); // сохранить неоконченный фрагмент

                for (let line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const jsonString = line.replace("data: ", "").trim();

                    try {
                        const data = JSON.parse(jsonString);

                        const finishReason = data.finish_reason;
                        const totalTokens = data.usage;
                        let chunk_id = data.id;
                        const userQuery = escapeHtml(data.user_query);

                        if (finishReason === "End") {
                            streamText = await filterText(newElement.innerText);
                            newElement.innerText = '';

                            let chatBlock = `<div class="response-body">${streamText}</div><br><hr>`;
                            // parent.innerHTML += `
                            //     <div id="${chunk_id}">
                            //         <div class="query-body">${userQuery}<button class="edit-button">
                            //             <img src="/static/img/icons/edit.svg" width="18" height="18" alt="edit">
                            //         </button></div>
                            //     </div>
                            // `;
                            parent.innerHTML += chatBlock;
                            Prism.highlightAll();

                            // Активируем последнюю добавленную кнопку .edit-button
                            const buttons = parent.querySelectorAll(".edit-button");
                            const lastButton = buttons[buttons.length - 1];
                            if (lastButton) {
                              lastButton.disabled = false;
                            }

                            setTimeout(fetchUpdatedSummaries, 5000);
                        } else if (finishReason === "stop") {
                            newElement.innerText += ' ';
                        } else {
                            newElement.innerText += data.content;
                            setTimeout(() => {
                                const container = document.querySelector(".container-main");
                                container.scrollTop = container.scrollHeight;
                            }, 100);
                        }
                    } catch (err) {
                        console.error("Ошибка парсинга JSON из потока:", err, line);
                    }
                }
            }

        } catch (error) {
            console.error("Ошибка при потоке:", error);
        } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = submitIcon;
            showUploadBtn.style.display = "flex";
            paramButton.style.display = "flex";
        }
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
              const searchPrompt = document.getElementById("search-input");
              const sPrompt = searchPrompt.value;
              // console.log(sPrompt);
              const label = searchButton.querySelector(".search-label");
              const spinner = searchButton.querySelector(".spinner");
              if (isValidInput(sPrompt)) {

                  searchButton.disabled = true;
                  label.style.display = "none";
                  spinner.style.display = "inline-block";
                  parent.innerHTML += `<div id="${generateId()}">
               <div class="query-body">${escapeHtml(sPrompt)}<button class="edit-button" disabled>
               <img src="/static/img/icons/edit.svg" width="18" height="18" alt="edit">
                </button>
                </div>
                </div>
            `;

                  try {
                                  const response = await fetchWithAuth("/api/search", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                prompt: sPrompt,
                                csrf_token: csrfToken.value,
                                extras: ""

                            })
                        });

                        if (response.redirected) {
                            window.location.href = response.url;
                            return;
                        }

                        if (!response.ok) {
                            if (response.status === 403) {
                                        window.location.replace("/api/logout");
                                    }
                            parent.innerHTML += `<div class="response-body">Ошибка соединения, повторите попытку позже</div>`;
                        }

                      const data = await response.json();
                      let searchBlock;

                      if (data.status === "error" || data.status === "info") {
                          searchBlock = `<div class="response-body">${data.message}</div>
                                </div><br><hr>`;
            //               parent.innerHTML += `<div id="${data.id}">
            //    <div class="query-body">${escapeHtml(sPrompt)}<button class="edit-button" disabled>
            //    <img src="/static/img/icons/edit.svg" width="18" height="18" alt="edit">
            //     </button>
            //     </div>
            //     </div>
            // `;
                          parent.innerHTML += searchBlock;
                          searchPrompt.value = "";
                      } else {
                          let filteredText = await filterText(data.response)
                          searchBlock = `<div class="response-body">${filteredText}</div>
                                </div><br><hr>`;
            //               parent.innerHTML += `<div id="${data.id}">
            //    <div class="query-body">${sPrompt}<button class="edit-button">
            //    <img src="/static/img/icons/edit.svg" width="18" height="18" alt="edit">
            //     </button>
            //     </div>
            //     </div>
            // `;
                          parent.innerHTML += searchBlock;
                          searchPrompt.value = "";
                          Prism.highlightAll();
                          // Активируем последнюю добавленную кнопку .edit-button
                            const buttons = parent.querySelectorAll(".edit-button");
                            const lastButton = buttons[buttons.length - 1];
                            if (lastButton) {
                              lastButton.disabled = false;
                            }

                          setTimeout(async () => {
                        await fetchUpdatedSummaries();
                    }, 5000);
                    // window.location.reload();

                      }
                       setTimeout(() => {
                        const container = document.querySelector(".container-main"); // Родитель с overflow-y: scroll;
                        container.scrollTop = container.scrollHeight; //  Прокручиваем к последнему элементу
                    }, 100);

                  } catch (error) {
                      console.error("Ошибка при запросе поиска:", error);
                  }
                  finally {
                              searchButton.disabled = false;
                              label.style.display = "inline";
                              spinner.style.display = "none";
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

        if (currentParam === "search") {
            paramButton.innerHTML = `чат<img src="/static/img/icons/message.svg" width="18" height="18"  alt="чат">`;
        } else {
            paramButton.innerHTML = `поиск<img src="/static/img/icons/world.svg" width="18" height="18" alt="поиск">`;
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const currentParam = getCookie("param") || "stream";
        updateToggleButtonText(currentParam);

        document.getElementById("param-toggle").addEventListener("click", () => {
            const nextParam = currentParam === "stream" ? "search" : "stream";
            window.location.href = `/api/change_param?param=${nextParam}`;
        });
    });

if (showUploadBtn) {
    showUploadBtn.addEventListener("click", () => {
        uploadWrapper.style.display = "block";
        uploadInfo.innerText='Из файла';
        showUploadBtn.style.display = "none";
        textarea.style.display = "none";
        paramButton.style.display = "none";
        submitButton.style.display = "none";
    });
}

if (uploadButton) {
    uploadButton.addEventListener("click", async () => {
        const file = uploadInput.files[0];
        if (!file) {
          console.log("Нет файла");
          uploadInfo.innerText='Выберите файл!';
        return;
        }



        const formData = new FormData();
        formData.append("file", file);
        formData.append("csrf_token", csrfToken.value);

        try {
            const response = await fetchWithAuth("/api/upload-image/", {
                method: "POST",
                body: formData
            });

            if (response.redirected) {
                window.location.href = response.url;
                return;
            }

            if (!response.ok) {
                alert("Ошибка загрузки изображения");
                showUploadBtn.style.display = "flex";
                return;
            }

            const result = await response.json();

            if (result.path) {
                uploadWrapper.style.display = "none";
                // showUploadBtn.style.display = "block";
                // showUploadBtn.disabled = true;
                textarea.style.display = "block";
                paramButton.style.display = "none";
                submitButton.style.display = "flex";
                const thumbImg = document.createElement('img');
                imgLink = result.path;
                thumbImg.src = '/api/image-preview/' + result.path;
                thumbImg.style.height = "40px";
                thumbImg.style.width = "auto";
                previewDiv.prepend(thumbImg);
                deleteIconButton.style.display = "block";
                const imageWrapper = document.createElement("div");
                imageWrapper.classList.add("image-wrapper");
                imagePath = document.createElement('img');
                imagePath.src = '/api/image-preview/' + result.path;
                imagePath.classList.add("image-wrapper-img");
                imageWrapper.appendChild(imagePath);
                parent.append(imageWrapper);



                // `
                //     <img src="${result.path}" alt="uploaded" style=" width: 40px; height: auto;" />
                //
                // `;

                const img = previewDiv.querySelector("img");
                img.onerror = () => {
                    img.style.display = "none";
                    imagePath = null;
                                        if (deleteIconButton) {
                        deleteIconButton.style.display = "none";
                        showUploadBtn.style.display = "flex";
                        paramButton.style.display = "flex";
                    }
                    console.log("Картинка удалена или путь указан неверный - Йодо.");

                };

                setTimeout(() => {
                                const container = document.querySelector(".container-main");
                                container.scrollTop = container.scrollHeight;
                            }, 100);
            }

        } catch (error) {
            console.error("Ошибка при загрузке изображения:", error);
            showUploadBtn.style.display = "flex";
            paramButton.style.display = "flex";
            imagePath = null;
        }
    });
}


if (deleteIconButton) {
    deleteIconButton.addEventListener("click", async (e) => {
        e.preventDefault();
        console.log("deleteIconButton");
        const csrfToken = getCookie("csrf_token");
        const formData = new FormData();
        formData.append("csrf_token", csrfToken);

        const response = await fetchWithAuth("/api/delete-image/", {
            method: "POST",
            body: formData
        });

        if (response.ok) {
            // Удалить иконку с DOM
            console.log("delete-image ok");
            const icon = previewDiv.querySelector("img");
            if (icon) icon.remove();
            deleteIconButton.style.display = "none";
            showUploadBtn.style.display = "flex";
            paramButton.style.display = "flex";
            imagePath = null;
        } else {
            console.error("Ошибка удаления изображения");
        }
    });
}
