"""Собирает index.html (PWA для iPhone) из app.html. Запуск: python3 build.py"""
from pathlib import Path
here = Path(__file__).parent
body = (here / "app.html").read_text(encoding="utf-8")
head = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Перекуп">
<meta name="theme-color" content="#EDEFF2" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#101216" media="(prefers-color-scheme: dark)">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" href="icon-192.png">
<style>[hidden]{display:none!important}img{max-width:100%}</style>
"""
tail = """
<script>if("serviceWorker" in navigator){addEventListener("load",()=>navigator.serviceWorker.register("sw.js").catch(()=>{}));}</script>
</body>
</html>
"""
# <title>/<style> из app.html остаются в head, разметка — в body
idx = body.index("</style>") + len("</style>")
html = head + body[:idx] + "\n</head>\n<body>\n" + body[idx:] + tail
(here / "index.html").write_text(html, encoding="utf-8")
print("index.html собран")
