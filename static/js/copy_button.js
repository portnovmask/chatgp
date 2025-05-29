const copyIcon = `<img src="/static/img/icons/copy.svg" width="20" height="20" alt="copy">`;

const checkIcon = `<img src="/static/img/icons/copy-check.svg" width="20" height="20" alt="copied">`;


document.addEventListener("click", async event => {
    const copyButton = event.target.closest(".copy-button");
    const editButton = event.target.closest(".edit-button");
    const deleteButton = event.target.closest(".delete-button");
    // Обработка кнопки для копирования

    if (copyButton) {
        // Первый блок для копирования (из блока с кодом)
        const codeBlock = copyButton.closest(".code-snippet")?.querySelector("code");
        if (codeBlock) {
            const codeText = codeBlock.innerText;
            try {
                await navigator.clipboard.writeText(codeText);
                copyButton.innerHTML = checkIcon; // Меняем иконку на успешное копирование
            } catch (err) {
                console.warn("Ошибка копирования:", err);
                copyButton.innerHTML = copyIcon; // Если ошибка, оставляем иконку копирования
            }
            setTimeout(() => copyButton.innerHTML = copyIcon, 1500); // Восстанавливаем иконку через 1.5 секунды
            return; // Прерываем выполнение, так как нашли блок для копирования кода
        }

        // Второй блок для копирования (например, из текстового блока)
        const textBlock = copyButton.closest(".response-body-plain");
        if (textBlock) {
            const textContent = textBlock.innerText;
            try {
                await navigator.clipboard.writeText(textContent);
                copyButton.innerHTML = checkIcon; // Меняем иконку на успешное копирование
            } catch (err) {
                console.warn("Ошибка копирования:", err);
                copyButton.innerHTML = copyIcon; // Если ошибка, оставляем иконку копирования
            }
            setTimeout(() => copyButton.innerHTML = copyIcon, 1500); // Восстанавливаем иконку через 1.5 секунды
            return; // Прерываем выполнение, так как нашли блок для копирования текста
        }
    }

    if (editButton) {
        const targetElement = editButton.closest(".query-body");
        const editQuery = document.querySelector("#prompt");
        const editSearch = document.getElementById("search-input");
        if (targetElement && editQuery){
            const targetValue = targetElement.innerText;
            targetElement.remove();
            editQuery.value += targetValue;// Вставляем редактируемое значение в поле ввода
            console.log("Элемент добавлен на редактирование");
        }
        if (targetElement && editSearch){
            const targetValue = targetElement.innerText;
            targetElement.remove();
            editSearch.value += targetValue;// Вставляем редактируемое значение в поле ввода
            console.log("Элемент добавлен на редактирование");
        }
        return; // Прерываем выполнение, так как нашли кнопку удаления
    }
    // if (deleteButton) {
    //     const targetElement = deleteButton.closest(".list-button");
    //     if (targetElement) {
    //         targetElement.remove(); // Удаляем элемент
    //         console.log("Элемент удален");
    //     }
    //     return; // Прерываем выполнение, так как нашли кнопку удаления
    // }

});



