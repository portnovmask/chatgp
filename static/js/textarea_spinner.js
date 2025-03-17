var textarea = document.getElementsByTagName('textarea')[0];
        /*
         Чтобы получить необходимы результат (автоматическая высота textarea)
         и исключить костыльный подход с setTimeout в теле инструкции обработчика
         resize, лучше подписать на событие input вместо keydown
        */
          textarea.addEventListener('input', resize);

          function resize(_e) {
            var event = _e || event || window.event;
            var getElement = event.target || event.srcElement; // var el = this;
        /* для сброса фантомной высоты от бордера :) и если направление на уменьшение строк  */
            getElement.style.height = "auto";
            /* вычисление и присвоение высоты */
            getElement.style.height = Math.max(getElement.scrollHeight, getElement.offsetHeight)+"px";
            }

        const form = document.querySelector('#myForm');
        const spinner = document.querySelector('#spinner');

        // добавляем обработчик события "submit" на форму
        form.addEventListener('submit', function() {
        // отображаем спинер
        spinner.style.display = 'block';
        form.classList.add('disabled');
        // задержка перед отправкой формы (в данном случае - 3 секунды)
        setTimeout(() => {
            // отправляем форму
            form.submit();

            // скрываем спинер после отправки
            spinner.style.display = 'none';
            form.classList.remove('disabled');
        }, 102000);
        });