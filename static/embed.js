/* Add to the UAIT website:  <script src="https://YOUR-HOST/static/embed.js" defer></script>
   Shows a green "UAIT AI" launcher (bottom-right). Click it to open the assistant panel.
   Optional attributes on the script tag:
     data-font-size="15"      match the website text size (12-24)
     data-theme="auto|light|dark"   default "light" (matches most websites); "auto" follows the visitor's OS setting */
(function () {
  if (window.__uaitAssistantLoaded) return;
  window.__uaitAssistantLoaded = true;
  var script = document.currentScript;
  var host = new URL(script.src).origin;
  var GREEN = "#2f913b", GREEN_D = "#1f6f2a";
  var fs = script.getAttribute("data-font-size");
  var theme = script.getAttribute("data-theme") || "light";
  var params = [];
  if (fs && /^\d{2}$/.test(fs)) params.push("fs=" + fs);
  if (theme === "light" || theme === "dark") params.push("theme=" + theme);
  var query = params.length ? "?" + params.join("&") : "";

  var style = document.createElement("style");
  style.textContent =
    "#uait-btn{position:fixed;right:20px;bottom:20px;z-index:2147483000;height:52px;min-width:52px;padding:0 20px 0 16px;gap:9px;border-radius:999px;background:" + GREEN + ";color:#fff;border:0;cursor:pointer;display:flex;align-items:center;justify-content:center;" +
    "font:600 15px/1 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;letter-spacing:.01em;box-shadow:0 8px 24px rgba(31,111,42,.38),0 2px 6px rgba(0,0,0,.18);transition:transform .15s ease,background .15s ease,padding .2s ease}" +
    "#uait-btn:hover{background:" + GREEN_D + ";transform:translateY(-1px)}#uait-btn:active{transform:scale(.97)}" +
    "#uait-btn:focus-visible{outline:3px solid #fff;outline-offset:2px;box-shadow:0 0 0 6px " + GREEN + "}" +
    "#uait-btn[data-open=true]{padding:0}#uait-btn[data-open=true] .uait-label{display:none}" +
    "#uait-frame{position:fixed;right:20px;bottom:84px;z-index:2147483000;width:min(410px,calc(100vw - 24px));height:min(740px,calc(100vh - 104px));border:0;border-radius:20px;background:#fff;" +
    "box-shadow:0 0 0 1px rgba(20,40,25,.08),0 24px 60px rgba(10,25,15,.28);transform-origin:bottom right;animation:uait-in .22s cubic-bezier(.2,.8,.2,1)}" +
    "@keyframes uait-in{from{opacity:0;transform:translateY(12px) scale(.97)}to{opacity:1;transform:none}}" +
    "@media (max-width:520px){#uait-frame{right:0;bottom:0;width:100vw;height:100dvh;border-radius:0}#uait-btn[data-open=true]{display:none}}" +
    "@media (prefers-reduced-motion:reduce){#uait-frame{animation:none}#uait-btn{transition:none}}";
  document.head.appendChild(style);

  var btn = document.createElement("button");
  btn.id = "uait-btn";
  btn.type = "button";
  btn.title = "UAIT AI";
  btn.setAttribute("aria-label", "Open UAIT AI assistant");
  btn.setAttribute("aria-expanded", "false");
  var chatIcon = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.5 8.5 0 0 1-12.2 7.6L3 21l1.9-5.6A8.5 8.5 0 1 1 21 11.5z"/></svg>';
  var closeIcon = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  var iconBox = document.createElement("span");
  iconBox.style.cssText = "display:flex;";
  iconBox.innerHTML = chatIcon;
  var label = document.createElement("span");
  label.className = "uait-label";
  label.textContent = "UAIT AI";
  btn.append(iconBox, label);

  var frame = document.createElement("iframe");
  frame.id = "uait-frame";
  frame.title = "UAIT AI assistant";
  frame.hidden = true;

  var loaded = false;
  function setOpen(open) {
    if (open && !loaded) { frame.src = host + "/" + query; loaded = true; }  // load the chat only when first opened
    frame.hidden = !open;
    btn.dataset.open = open ? "true" : "false";
    iconBox.innerHTML = open ? closeIcon : chatIcon;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.setAttribute("aria-label", open ? "Close UAIT AI assistant" : "Open UAIT AI assistant");
  }
  btn.onclick = function () { setOpen(frame.hidden); };
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !frame.hidden) setOpen(false); });
  window.addEventListener("message", function (e) { if (e.origin === host && e.data && e.data.uaitClose) { setOpen(false); btn.focus(); } });

  function mount() {
    document.body.append(frame, btn);
    if (script.hasAttribute("data-open")) setOpen(true); // Useful for the bundled preview; omit this attribute on the live site.
  }
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
})();
