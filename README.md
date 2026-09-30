# Personal Gallery Sync

个人图片库管理与同步工具。静默扫描你自己电脑上的图片目录，建立索引、生成缩略图，提供本地 Web 画廊（可在局域网内用其他设备访问），并可选择性地备份到你自己的云存储。

## 功能

- **自动检索图片目录**：一键扫描系统常见图片目录，或全盘搜索含图片的文件夹
- 扫描本地指定目录下的图片，建立 SQLite 索引
- 自动生成缩略图，加快浏览速度
- Web 画廊：浏览器中按文件夹浏览、点击查看大图
- 可选备份到 S3 兼容存储或 WebDAV（你自己的账号）
- 静默后台运行，日志写入文件，可配合计划任务 / systemd / 任务计划程序使用

## 快速开始

```bash
pip install -r requirements.txt

# 方式一：自动检索图片目录并写入配置（推荐首次使用）
python main.py discover --write

# 方式二：手动配置
cp config.example.yaml config.yaml
# 编辑 config.yaml，填写 scan_dirs

python main.py scan     # 扫描并建立索引
python main.py serve    # 启动 Web 画廊，访问 http://localhost:8080
```

## 自动检索图片目录

```bash
# 快速模式：只扫描系统常见图片目录（~/Pictures、~/Downloads 等）
python main.py discover

# 全盘搜索：从指定根目录查找含 >= N 张图片的文件夹
python main.py discover --root / --min-images 10

# 自动写入 config.yaml（合并现有目录，去重）
python main.py discover --root /home --min-images 5 --write

# 覆盖现有 scan_dirs（不合并）
python main.py discover --root D:\\ --min-images 1 --write --no-merge
```

参数说明：

| 参数 | 说明 |
|------|------|
| `--root <路径>` | 全盘搜索的根目录；不指定则只扫系统常见目录 |
| `--min-images <N>` | 目录至少包含 N 张图片才计入（默认 1） |
| `--max-depth <N>` | 全盘搜索的最大递归深度（默认 8） |
| `--write` | 将发现的目录写入 `config.yaml` 的 `scan_dirs` |
| `--no-merge` | 覆盖现有 `scan_dirs` 而非合并 |

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
