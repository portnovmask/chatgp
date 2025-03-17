function processResponseBodies() {
    const responseBodies = document.querySelectorAll(".response-body");
    for (const body of responseBodies) {
        if (!body.dataset.processed) {  // 🔹 Проверяем, обработан ли уже блок
            body.innerHTML = replaceCodeBlocks(body.innerHTML);
            body.dataset.processed = "true";  // ✅ Помечаем блок как обработанный
        }
    }
}

// ✅ Вызываем обработку при загрузке страницы
document.addEventListener("DOMContentLoaded", processResponseBodies);

// ✅ Наблюдаем за `#article`, но избегаем бесконечного обновления
const observer = new MutationObserver((mutations) => {
    let needsProcessing = false;
    mutations.forEach((mutation) => {
        if (mutation.type === "childList") {
            needsProcessing = true;
        }
    });
    if (needsProcessing) {
        processResponseBodies()
    }
});

const chatContainer = document.querySelector("#article");
if (chatContainer) {
    observer.observe(chatContainer, { childList: true, subtree: true });
}
setTimeout(() => {
            chatContainer.scrollIntoView({ behavior: "smooth", block: "end" });
        }, 100);



function replaceCodeBlocks(text) {


    let parts = text.split(/```([\s\S]*?)```/g);

    return parts.map((part, index) => {
        if (index % 2 === 1) {
            // Это код -> Оставляем переносы строк
            return `
                <div class="code-snippet">
                <pre class="language-css"><code>${part}</code></pre>
                <button class="copy-button"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-copy" viewBox="0 0 16 16">
                <path fill-rule="evenodd" d="M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm2-1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1zM2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1h1v1a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1v1z"/>
                </svg></button>
                </pre>
                     </div>`;
        } else {

             // return `<div class="response-body-plain"><pre>${part.replace(/^###\s*(.+)$/gm, "<strong>$1</strong>")}</pre></div>`;
             return `<pre class="response-body-plain no-keep-markup">${part.replace(/^###\s*(.+)$/gm, "<strong>$1</strong>").replace(/\*\*(.*?)\*\*/g, "<u>$1</u>").replace(/ {3,}/g, "  ").replace(/\n{2,}/g, "\n")}</pre><br>`;
            // return part;
        }
    }).join("");
}



function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")   // Защита от HTML-инъекций
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;")
        // .replace(/\n/g, "<br>")   // Сохраняем переводы строк
        // .replace(/\t/g, "&#009;") // Сохраняем табуляцию
        // .replace(/ {2}/g, " &nbsp;"); // Сохраняем двойные пробелы
}

