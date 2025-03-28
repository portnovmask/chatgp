/*!
 * Minimal theme switcher
 *
 * Pico.css - https://picocss.com
 * Copyright 2019-2024 - Licensed under MIT
 */

const themeSwitcher = {
  // Config
  _scheme: "auto",
  menuTarget: "details.dropdown",
  buttonsTarget: "a[data-theme-switcher]",
  buttonAttribute: "data-theme-switcher",
  rootAttribute: "data-theme",
  localStorageKey: "picoPreferredColorScheme",

  // Init
  init() {
    this.scheme = this.schemeFromLocalStorage;
    this.initSwitchers();
  },

  // Get color scheme from local storage
  get schemeFromLocalStorage() {
    return window.localStorage?.getItem(this.localStorageKey) ?? this._scheme;
  },

  // Preferred color scheme
  get preferredColorScheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  },

  // Init switchers
  initSwitchers() {
    const button = document.querySelector(this.buttonsTarget);
    if (!button) return;

    const icon = button.querySelector("img"); // Получаем <img> внутри кнопки

    // Объект с иконками для разных тем
    const icons = {
        light: "static/img/icons/brightness-up.svg",
        dark: "static/img/icons/brightness-fill.svg",
        auto: "static/img/icons/brightness-auto.svg",
    };

    button.addEventListener("click", (event) => {
        event.preventDefault();

        // Циклическое переключение тем
        if (this.scheme === "light") {
            this.scheme = "dark";
        } else if (this.scheme === "dark") {
            this.scheme = "auto";
        } else {
            this.scheme = "light";
        }

        // Меняем иконку
        icon.src = icons[this.scheme];
        icon.alt = this.scheme;
    });
},


  // Set scheme
  set scheme(scheme) {
    if (scheme == "auto") {
      this._scheme = this.preferredColorScheme;
    } else if (scheme == "dark" || scheme == "light") {
      this._scheme = scheme;
    }
    this.applyScheme();
    this.schemeToLocalStorage();
  },

  // Get scheme
  get scheme() {
    return this._scheme;
  },

  // Apply scheme
  applyScheme() {
    document.querySelector("html")?.setAttribute(this.rootAttribute, this.scheme);
  },

  // Store scheme to local storage
  schemeToLocalStorage() {
    window.localStorage?.setItem(this.localStorageKey, this.scheme);
  },
};

// Init
themeSwitcher.init();