(function () {
    const saved = localStorage.getItem("theme");
    if (saved === "dark") document.documentElement.classList.add("dark");
    window.toggleTheme = function () {
        const dark = document.documentElement.classList.toggle("dark");
        localStorage.setItem("theme", dark ? "dark" : "light");
    };
})();

window.showToast = function (msg, kind = "success") {
    const t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText = `
        position: fixed; top: 24px; left: 50%; transform: translateX(-50%) translateY(-20px);
        background: ${kind === "error" ? "#dc2626" : "#059669"};
        color: white; padding: 14px 26px; border-radius: 12px;
        font-weight: 600; font-size: 14px; z-index: 10000;
        box-shadow: 0 10px 40px rgba(0,0,0,0.25); opacity: 0;
        transition: all 0.3s ease; font-family: Inter, sans-serif;
        max-width: 90vw; text-align: center;
    `;
    document.body.appendChild(t);
    requestAnimationFrame(() => {
        t.style.opacity = "1";
        t.style.transform = "translateX(-50%) translateY(0)";
    });
    setTimeout(() => {
        t.style.opacity = "0";
        t.style.transform = "translateX(-50%) translateY(-20px)";
        setTimeout(() => t.remove(), 300);
    }, 3200);
};
