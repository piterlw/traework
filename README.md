# Personal Gallery Sync

个人图片库管理与同步工具。静默扫描你自己电脑上的图片目录，建立索引、生成缩略图，提供本地 Web 画廊（可在局域网内用其他设备访问），并可选择性地备份到你自己的云存储。

## 功能

- 扫描本地指定目录下的图片，建立 SQLite 索引
- 自动生成缩略图，加快浏览速度
- Web 画廊：浏览器中按文件夹浏览、点击查看大图
- 可选备份到 S3 兼容存储或 WebDAV（你自己的账号）
- 静默后台运行，日志写入文件，可配合计划任务 / systemd / 任务计划程序使用

## 快速开始

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
# 编辑 config.yaml，填写 scan_dirs

python main.py scan     # 扫描并建立索引
python main.py serve    # 启动 Web 画廊，访问 http://localhost:8080
```

局域网内其他设备访问：用运行电脑的 IP 代替 localhost（需 `web.host` 设为 `0.0.0.0`）。

## 备份到云存储

编辑 `config.yaml` 的 `backup` 段，启用后：

```bash
python main.py backup   # 备份索引中的图片到你的云存储
python main.py full     # 扫描 + 备份
```

支持 S3 兼容存储（AWS S3、阿里云 OSS、MinIO）和 WebDAV（坚果云、Nextcloud 等）。

## 配置

参见 `config.example.yaml`。所有路径、凭据均由你在本地配置文件中填写，不会外传。

## 说明

本工具仅用于管理你自己设备上的图片文件。运行时所有扫描、索引、备份操作均在你明确配置的目录和存储账号内进行，操作记录写入日志文件。
