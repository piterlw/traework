"""本地 Web 画廊服务：用浏览器查看索引中的图片。

可绑定到 0.0.0.0，在同一局域网内用手机/平板/其他电脑访问。
所有图片均来自你在 config.yaml 中配置的本地目录。
"""

import os
import logging
from functools import wraps

from flask import (
    Flask, send_file, jsonify, request, Response, render_template_string, abort
)

from .config import Config
from .index import ImageIndex
from .thumbnail import thumbnail_path

logger = logging.getLogger(__name__)

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>我的图库</title>
<style>
  body { margin: 0; background: #111; color: #eee; font-family: system-ui, sans-serif; }
  header { padding: 12px 20px; background: #1a1a1a; position: sticky; top: 0; z-index: 10; }
  header select { padding: 6px; background: #222; color: #eee; border: 1px solid #444; border-radius: 4px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; padding: 16px; }
  .item { aspect-ratio: 1; overflow: hidden; background: #222; cursor: pointer; border-radius: 6px; }
  .item img { width: 100%; height: 100%; object-fit: cover; }
  .lightbox { position: fixed; inset: 0; background: rgba(0,0,0,.92); display: none; align-items: center; justify-content: center; z-index: 100; }
  .lightbox.active { display: flex; }
  .lightbox img { max-width: 95vw; max-height: 92vh; }
  .lightbox .close { position: absolute; top: 16px; right: 24px; font-size: 32px; cursor: pointer; color: #fff; }
</style>
</head>
<body>
<header>
  我的图库 · 共 <span id="cnt">0</span> 张
  <select id="folder" onchange="load()">
    <option value="">全部文件夹</option>
  </select>
</header>
<div class="grid" id="grid"></div>
<div class="lightbox" id="lb" onclick="closeLb()">
  <span class="close">&times;</span>
  <img id="lbImg" src="">
</div>
<script>
async function load(){
  const f = document.getElementById('folder').value;
  const res = await fetch('/api/images?folder=' + encodeURIComponent(f));
  const data = await res.json();
  document.getElementById('cnt').textContent = data.count;
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  data.images.forEach(img => {
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = '<img src="/thumb/' + img.id + '" loading="lazy">';
    div.onclick = () => { document.getElementById('lbImg').src = '/image/' + img.id; document.getElementById('lb').classList.add('active'); };
    grid.appendChild(div);
  });
}
function closeLb(){ document.getElementById('lb').classList.remove('active'); }
(async () => {
  const fs = await fetch('/api/folders').then(r => r.json());
  const sel = document.getElementById('folder');
  fs.forEach(f => { const o = document.createElement('option'); o.value = f; o.textContent = f; sel.appendChild(o); });
  load();
})();
</script>
</body>
</html>"""


def create_app(cfg: Config, index: ImageIndex) -> Flask:
    app = Flask(__name__)

    password = cfg.web.password

    def check_auth(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if password:
                token = request.args.get("token") or request.headers.get("X-Auth-Token")
                if token != password:
                    return Response("需要授权", 401)
            return f(*args, **kwargs)
        return wrapped

    @app.route("/")
    @check_auth
    def home():
        return render_template_string(INDEX_HTML)

    @app.route("/api/images")
    @check_auth
    def api_images():
        folder = request.args.get("folder", "")
        if folder:
            rows = index.by_folder(folder, limit=500)
        else:
            rows = index.all(limit=500)
        return jsonify({
            "count": index.count(),
            "images": [
                {"id": r["id"], "folder": r["folder"], "filename": r["filename"],
                 "width": r["width"], "height": r["height"]}
                for r in rows
            ],
        })

    @app.route("/api/folders")
    @check_auth
    def api_folders():
        return jsonify(index.folders())

    @app.route("/thumb/<int:image_id>")
    @check_auth
    def thumb(image_id):
        row = index.get(image_id)
        if not row:
            abort(404)
        tpath = thumbnail_path(cfg.thumbnail_dir, row["file_hash"])
        if not os.path.exists(tpath):
            # 没有缩略图时直接返回原图（浏览器会缩放）
            return send_file(row["path"])
        return send_file(tpath, mimetype="image/jpeg")

    @app.route("/image/<int:image_id>")
    @check_auth
    def full_image(image_id):
        row = index.get(image_id)
        if not row:
            abort(404)
        return send_file(row["path"])

    return app


def run_server(cfg: Config, index: ImageIndex):
    app = create_app(cfg, index)
    logger.info("启动 Web 画廊: http://%s:%d", cfg.web.host, cfg.web.port)
    print(f"[gallery] Web 画廊已启动: http://{cfg.web.host}:{cfg.web.port}")
    print(f"[gallery] 局域网内其他设备可通过本机 IP 访问（如 http://<本机IP>:{cfg.web.port}）")
    app.run(host=cfg.web.host, port=cfg.web.port, debug=False, threaded=True)
