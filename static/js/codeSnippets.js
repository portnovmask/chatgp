
 window.addEventListener("DOMContentLoaded", () => {
  setTimeout(() => {
                                const container = document.querySelector(".container-main");
                                container.scrollTop = container.scrollHeight;
                            }, 100);
});



function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")   // Защита от HTML-инъекций
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;")
        // .replace(/\n/g, "<br>")   // Сохраняем переводы строк
         .replace(/\t/g, "&#009;") // Сохраняем табуляцию
         .replace(/ {2}/g, " &nbsp;"); // Сохраняем двойные пробелы
}

