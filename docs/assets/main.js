(() => {
  "use strict";
  const content = window.NOTE_CRAFT_CONTENT;
  if (!content || !content.zh || !content.en) return;

  const storageKey = "note-craft.language";
  const commandField = document.getElementById("install-command");
  const copyButtons = Array.from(document.querySelectorAll("[data-copy-install]"));
  const languageButtons = Array.from(document.querySelectorAll("[data-lang]"));
  const tabs = Array.from(document.querySelectorAll("[data-example]"));
  const navigation = document.getElementById("site-nav");
  const menuButton = document.getElementById("menu-toggle");
  const toast = document.getElementById("copy-status");
  let example = "original";
  let toastTimer;
  let language = "zh";

  const validLanguage = (value) => value === "zh" || value === "en";
  const t = (key) => content[language].text[key] || content.zh.text[key] || key;

  function resizeCommand() {
    commandField.style.height = "auto";
    commandField.style.height = `${commandField.scrollHeight + 2}px`;
  }

  function renderExample() {
    const selected = content[language].examples[example];
    document.getElementById("example-filename").textContent = selected.filename;
    const code = document.getElementById("example-code");
    const fragment = document.createDocumentFragment();
    selected.content.split("\n").forEach((line, index, lines) => {
      if (line.startsWith("#")) {
        const heading = document.createElement("span");
        heading.className = "example-heading";
        heading.textContent = line;
        fragment.appendChild(heading);
      } else {
        fragment.appendChild(document.createTextNode(line));
      }
      if (index < lines.length - 1) fragment.appendChild(document.createTextNode("\n"));
    });
    code.replaceChildren(fragment);
    const observations = document.getElementById("example-observations");
    observations.replaceChildren(...selected.observations.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    }));
    tabs.forEach((tab) => {
      const active = tab.dataset.example === example;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    document.getElementById("example-panel").setAttribute("aria-labelledby", `tab-${example}`);
  }

  function setLanguage(nextLanguage, updateUrl = false) {
    language = validLanguage(nextLanguage) ? nextLanguage : "zh";
    const selected = content[language];
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    document.title = selected.meta.title;
    document.querySelector('meta[name="description"]').content = selected.meta.description;
    document.querySelector('meta[property="og:title"]').content = selected.meta.title;
    document.querySelector('meta[property="og:description"]').content = selected.meta.description;
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
      element.setAttribute("aria-label", t(element.dataset.i18nAria));
    });
    languageButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.lang === language));
    });
    commandField.value = selected.installCommand;
    renderExample();
    resizeCommand();
    try { localStorage.setItem(storageKey, language); } catch (_) { /* Storage is optional. */ }
    if (updateUrl) {
      try {
        const url = new URL(window.location.href);
        if (language === "en") url.searchParams.set("lang", "en");
        else url.searchParams.delete("lang");
        history.replaceState(null, "", url);
      } catch (_) { /* Local file previews may restrict history updates. */ }
    }
    toast.hidden = true;
    clearTimeout(toastTimer);
  }

  function showStatus(key) {
    clearTimeout(toastTimer);
    toast.textContent = t(key);
    toast.hidden = false;
    toastTimer = setTimeout(() => { toast.hidden = true; }, 5000);
  }

  function legacyCopy(text) {
    const temporary = document.createElement("textarea");
    temporary.value = text;
    temporary.setAttribute("aria-hidden", "true");
    temporary.style.cssText = "position:fixed;left:-9999px;top:0;font-size:16px";
    document.body.appendChild(temporary);
    temporary.select();
    let copied = false;
    try { copied = document.execCommand("copy"); } catch (_) { /* Use manual selection below. */ }
    temporary.remove();
    return copied;
  }

  async function copyInstall(event) {
    const trigger = event.currentTarget;
    const text = content[language].installCommand;
    copyButtons.forEach((button) => { button.disabled = true; });
    let copied = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        try { await navigator.clipboard.writeText(text); copied = true; } catch (_) { /* Try a compatible fallback. */ }
      }
      if (!copied) copied = legacyCopy(text);
      if (copied) {
        showStatus("toast.copied");
      } else {
        document.getElementById("start").scrollIntoView({ block: "start" });
        commandField.focus({ preventScroll: true });
        commandField.select();
        showStatus("toast.manual");
      }
    } catch (_) {
      showStatus("toast.unavailable");
    } finally {
      copyButtons.forEach((button) => { button.disabled = false; });
      if (copied) trigger.focus({ preventScroll: true });
    }
  }

  function closeMenu(returnFocus = false) {
    navigation.classList.remove("is-open");
    menuButton.setAttribute("aria-expanded", "false");
    if (returnFocus) menuButton.focus();
  }

  copyButtons.forEach((button) => button.addEventListener("click", copyInstall));
  languageButtons.forEach((button) => button.addEventListener("click", () => setLanguage(button.dataset.lang, true)));
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => { example = tab.dataset.example; renderExample(); });
    tab.addEventListener("keydown", (event) => {
      let next;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      example = tabs[next].dataset.example;
      renderExample();
      tabs[next].focus();
    });
  });
  menuButton.addEventListener("click", () => {
    const expanded = menuButton.getAttribute("aria-expanded") !== "true";
    menuButton.setAttribute("aria-expanded", String(expanded));
    navigation.classList.toggle("is-open", expanded);
  });
  navigation.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => closeMenu()));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navigation.classList.contains("is-open")) closeMenu(true);
  });
  window.matchMedia("(min-width: 761px)").addEventListener("change", (event) => {
    if (event.matches) closeMenu();
  });
  window.addEventListener("resize", resizeCommand);

  const urlLanguage = new URLSearchParams(window.location.search).get("lang");
  let savedLanguage;
  try { savedLanguage = localStorage.getItem(storageKey); } catch (_) { /* Chinese remains the default. */ }
  setLanguage(validLanguage(urlLanguage) ? urlLanguage : (validLanguage(savedLanguage) ? savedLanguage : "zh"));
})();
