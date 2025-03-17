 const submitButton = document.querySelector('#submit');
      const hr = document.createElement("hr");

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




      let eventSource;

      submitButton.onclick = () => {
          const promptInput = document.querySelector('#prompt');
          const prompt = promptInput.value;
          let streamText = ''
          let unique_id = "#"
          const newQuery = document.createElement("div");
          newQuery.classList.add("query-body");
          const newResponse = document.createElement("div");
          newResponse.id = unique_id;
          const newResponseBody = document.createElement("div");
          newResponseBody.classList.add("response-body");
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
                    const userQuery = data.user_query;

                    newQuery.innerText = userQuery + '\n';

                    if (finishReason === "End") {
                        console.log("Closing EventSource...");
                        streamText = newElement.innerText
                        newResponseBody.innerHTML = streamText;
                        newElement.innerText = '';
                        console.log(totalTokens);
                        console.log(data.id);
                        eventSource.close();
                        newResponse.id = data.id;

                        newResponse.append(newQuery);
                        newResponse.append(newResponseBody);
                        newResponse.append(hr);
                        parent.append(newResponse);
                        newResponse.focus();
                    } else if (finishReason === "stop") {
                        newElement.innerText += ' ';
                    } else {
                        //await streamToContainer(data.content, newElement);
                        newElement.innerText += data.content;
                        // Прокручиваем страницу после загрузки чата
                         setTimeout(() => {
                            newElement.scrollIntoView({ behavior: "smooth", block: "end" });
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
//       function focusLastTextarea() {
//     const textareas = document.querySelectorAll("textarea");
//     if (textareas.length > 0) {
//         textareas[textareas.length - 1].focus();
//     }
// }
