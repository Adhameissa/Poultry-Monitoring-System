(function () {
    const toggle = document.getElementById("chatbot-toggle");
    const panel = document.getElementById("chatbot-panel");
    const closeBtn = document.getElementById("chatbot-close");
    const messagesEl = document.getElementById("chatbot-messages");
    const input = document.getElementById("chatbot-input");
    const sendBtn = document.getElementById("chatbot-send");
    const ctxScript = document.getElementById("chatbot-page-context");

    if (!toggle || !panel || !messagesEl || !input || !sendBtn) return;

    let pageContext = {};
    try {
        pageContext = ctxScript ? JSON.parse(ctxScript.textContent || "{}") : {};
    } catch (e) {
        pageContext = { page: "unknown", parse_error: true };
    }
    var htmlLang = (document.documentElement.getAttribute("lang") || "en").toLowerCase();
    if (!pageContext.lang) {
        pageContext.lang = htmlLang || "en";
    }
    var isAr =
        (pageContext.lang && String(pageContext.lang).toLowerCase().indexOf("ar") === 0) ||
        htmlLang.indexOf("ar") === 0;

    var inputPh = isAr
        ? "اكتب سؤالك بجملة بسيطة، مثال: ما معنى هذا الرقم؟ أو اضغط أحد الاقتراحات أعلاه."
        : "Type a short question, e.g. “What does this number mean?” or tap a suggestion above.";
    input.placeholder = inputPh;

    var quickRoot = document.getElementById("chatbot-quick-prompts");
    if (quickRoot) {
        quickRoot.querySelectorAll(".chatbot-chip").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var en = btn.getAttribute("data-prompt-en") || "";
                var ar = btn.getAttribute("data-prompt-ar") || en;
                input.value = isAr ? ar : en;
                input.focus();
            });
        });
    }

    const history = [];

    function appendMsg(role, text, isError) {
        const div = document.createElement("div");
        div.className = "chatbot-msg " + (isError ? "error" : role);
        div.textContent = text;
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function setOpen(open) {
        panel.classList.toggle("chatbot-panel--open", open);
        panel.classList.toggle("chatbot-panel--closed", !open);
        panel.setAttribute("aria-hidden", open ? "false" : "true");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.classList.toggle("chatbot-toggle--active", open);
    }

    setOpen(false);

    toggle.addEventListener("click", function (e) {
        e.stopPropagation();
        var isOpen = panel.classList.contains("chatbot-panel--open");
        setOpen(!isOpen);
        if (!isOpen) input.focus();
    });
    if (closeBtn) {
        closeBtn.addEventListener("click", function () {
            setOpen(false);
        });
    }

    async function sendMessage() {
        const text = (input.value || "").trim();
        if (!text) return;
        input.value = "";
        appendMsg("user", text);
        sendBtn.disabled = true;

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    page_context: pageContext,
                    history: history,
                }),
            });
            const data = await res.json().catch(function () {
                return {};
            });
            if (!res.ok || !data.ok) {
                appendMsg("bot", data.error || "Request failed.", true);
                return;
            }
            const reply = data.reply || "";
            appendMsg("bot", reply);
            history.push({ role: "user", text: text });
            history.push({ role: "model", text: reply });
            if (history.length > 24) history.splice(0, history.length - 24);
        } catch (e) {
            appendMsg("bot", String(e.message || e), true);
        } finally {
            sendBtn.disabled = false;
        }
    }

    sendBtn.addEventListener("click", sendMessage);
    input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    if (!messagesEl.querySelector(".chatbot-msg")) {
        var welcome = isAr
            ? "مرحباً! يمكنني شرح شاشات التطبيق، معنى كل إدخال، وكيف تقرأ النتائج. اسألني عن أي مبلغ أو حقل."
            : "Hi! I can explain this app’s screens, what each input means, and how to read the results. Ask me anything.";
        appendMsg("bot", welcome);
    }
})();
