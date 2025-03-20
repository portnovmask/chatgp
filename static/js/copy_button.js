const copyIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-copy" viewBox="0 0 16 16">
  <path fill-rule="evenodd" d="M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm2-1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1zM2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1h1v1a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1v1z"/>
</svg>`;

const checkIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check-all" viewBox="0 0 16 16">
  <path d="M8.97 4.97a.75.75 0 0 1 1.07 1.05l-3.99 4.99a.75.75 0 0 1-1.08.02L2.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093L8.95 4.992zm-.92 5.14.92.92a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 1 0-1.091-1.028L9.477 9.417l-.485-.486z"/>
</svg>`;


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
        const targetElement = editButton.closest(".query-container");
        if (targetElement) {
            targetElement.remove(); // Удаляем элемент
            console.log("Элемент удален");
        }
        return; // Прерываем выполнение, так как нашли кнопку удаления
    }
    if (deleteButton) {
        const targetElement = deleteButton.closest(".list-button");
        if (targetElement) {
            targetElement.remove(); // Удаляем элемент
            console.log("Элемент удален");
        }
        return; // Прерываем выполнение, так как нашли кнопку удаления
    }

});


