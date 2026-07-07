# RoboCOIN Hotel LeRobot v2.1 -> v3.0 Convert Tool

这个工具用于把 RoboCOIN 酒店领域数据从 LeRobot v2.1 转为 LeRobot v3.0，并在本地做兼容性验证。流程只读写本地文件，不会上传到 Hugging Face。

工具封装了四件事：

- 下载 Hugging Face 上的 RoboCOIN hotel datasets
- 调用 LeRobot 官方 `convert_dataset_v21_to_v30.py`
- 修复 RoboCOIN hotel 数据里已发现的 v3 兼容问题
- 做 oracle differential validation 和人工边界检查

## 支持平台

支持 Windows、Linux、macOS。

| 平台 | 环境脚本 | 运行脚本 |
| --- | --- | --- |
| Windows PowerShell | `setup_env.ps1` | `run_all.ps1` |
| Linux Bash | `setup_env.sh` | `run_all.sh` |
| macOS Bash/Zsh | `setup_env.sh` | `run_all.sh` |

主逻辑在 `robocoin_hotel_convert.py` 中，平台差异只在环境初始化和入口脚本。

## 系统依赖

空机器至少需要：

- Python 3.12 或 3.13
- Git
- curl
- 足够磁盘空间。`--preset all` 会下载和转换多个视频数据集，建议准备较大的独立数据盘。

Windows 安装示例：

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
```

Ubuntu/Debian 安装示例：

```bash
sudo apt update
sudo apt install -y python3 python3-venv git curl
```

macOS 安装示例：

```bash
brew install python git curl
```

安装系统依赖后，重新打开终端。

## Windows 从零配置

```powershell
cd converTool
Set-ExecutionPolicy -Scope Process Bypass
.\setup_env.ps1 -CloneLeRobot -InstallViz
.\.venv\Scripts\Activate.ps1
```

不需要人工可视化时可以去掉 `-InstallViz`：

```powershell
.\setup_env.ps1 -CloneLeRobot
.\.venv\Scripts\Activate.ps1
```

## Linux/macOS 从零配置

如果脚本没有执行权限，可以直接用 `bash` 运行：

```bash
cd converTool
bash setup_env.sh --clone-lerobot --install-viz
source .venv/bin/activate
```

或者先加执行权限：

```bash
chmod +x setup_env.sh run_all.sh
./setup_env.sh --clone-lerobot --install-viz
source .venv/bin/activate
```

不需要人工可视化时可以去掉 `--install-viz`：

```bash
bash setup_env.sh --clone-lerobot
source .venv/bin/activate
```

默认会把 LeRobot clone 到：

```text
converTool/_deps/lerobot
```

这个目录已经在 `.gitignore` 中，不应上传到 GitHub。

## Hugging Face 登录

Windows、Linux、macOS 命令相同：

```bash
hf auth login
```

如果环境没有 `hf` 命令，也可以用：

```bash
huggingface-cli login
```

如果数据集是 public gated repo，token 需要开启：

```text
Read access to contents of all public gated repos you can access
```

并确认账号已经在 Hugging Face 数据集页面申请或同意访问。工具只读取本地 token，不会打印 token。

## 已验证格式

已经实际完成并验证过两类 RoboCOIN hotel 格式：

| 格式 | 已验证数据集 | 相机 key |
| --- | --- | --- |
| Kuavo 4 hotel services | `RoboCOIN/Leju_Kuavo_4_hotel_services` | `cam_front_head_rgb`, `cam_left_wrist_rgb`, `cam_right_wrist_rgb` |
| leju_robot hotel services | `RoboCOIN/leju_robot_hotel_services_h` | `camera_head_rgb`, `camera_left_wrist_rgb`, `camera_right_wrist_rgb` |

`leju_robot_hotel_services_*` 系列按 `_h` 的格式处理，只是 repo 后缀不同。

## 内置数据集

默认 `all` 会处理下面全部 repo：

```text
RoboCOIN/Leju_Kuavo_4_hotel_services
RoboCOIN/leju_robot_hotel_services_e
RoboCOIN/leju_robot_hotel_services_f
RoboCOIN/leju_robot_hotel_services_a
RoboCOIN/leju_robot_hotel_services_c
RoboCOIN/leju_robot_hotel_services_d
RoboCOIN/leju_robot_hotel_services_b
RoboCOIN/leju_robot_hotel_services_i
RoboCOIN/leju_robot_hotel_services_h
RoboCOIN/leju_robot_hotel_services_ad
RoboCOIN/leju_robot_hotel_services_ah
RoboCOIN/leju_robot_hotel_services_ag
RoboCOIN/leju_robot_hotel_services_ac
RoboCOIN/leju_robot_hotel_services_af
RoboCOIN/leju_robot_hotel_services_ae
RoboCOIN/leju_robot_hotel_services_aa
RoboCOIN/leju_robot_hotel_services_ab
```

查看 preset 名称：

```bash
python robocoin_hotel_convert.py --list-presets
```

## 输出目录

每个数据集会输出两个目录：

```text
<output-root>/<local_name>_v21
<output-root>/<local_name>_v30
```

例如：

```text
datasets/leju_robot_hotel_services_h_v21
datasets/leju_robot_hotel_services_h_v30
```

官方脚本内部会临时把原目录改成 `_old`；本工具最后会规范回 `_v21` 和 `_v30`。

## Dry Run

正式下载前先检查执行计划。

Windows：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets -DryRun
```

Linux/macOS：

```bash
bash run_all.sh --preset all --output-root ./datasets --dry-run
```

如果使用默认 `setup_env` 脚本 clone LeRobot，工具会自动找到 `./_deps/lerobot/src`，不需要手动传 LeRobot 路径。

如果你已经有自己的 LeRobot 源码，可以指定。

Windows：

```powershell
.\run_all.ps1 `
  -Preset all `
  -OutputRoot .\datasets `
  -LeRobotSrc "X:\path\to\lerobot\src" `
  -DryRun
```

Linux/macOS：

```bash
bash run_all.sh \
  --preset all \
  --output-root ./datasets \
  --lerobot-src /path/to/lerobot/src \
  --dry-run
```

## 一键下载、转换、验证

处理全部内置数据集。

Windows：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets
```

Linux/macOS：

```bash
bash run_all.sh --preset all --output-root ./datasets
```

单独处理一个数据集。

Windows：

```powershell
.\run_all.ps1 -Preset kuavo4_hotel_services -OutputRoot .\datasets
.\run_all.ps1 -Preset leju_robot_hotel_services_h -OutputRoot .\datasets
.\run_all.ps1 -Preset leju_robot_hotel_services_a -OutputRoot .\datasets
```

Linux/macOS：

```bash
bash run_all.sh --preset kuavo4_hotel_services --output-root ./datasets
bash run_all.sh --preset leju_robot_hotel_services_h --output-root ./datasets
bash run_all.sh --preset leju_robot_hotel_services_a --output-root ./datasets
```

如果直连 `huggingface.co` 不稳定，可以强制使用 mirror。

Windows：

```powershell
.\run_all.ps1 `
  -Preset all `
  -OutputRoot .\datasets `
  -DownloadBackend curl `
  -MirrorEndpoint https://hf-mirror.com
```

Linux/macOS：

```bash
bash run_all.sh \
  --preset all \
  --output-root ./datasets \
  --download-backend curl \
  --mirror-endpoint https://hf-mirror.com
```

## 自定义 RoboCOIN Hotel Repo

如果后续出现同格式新 repo。

Windows：

```powershell
python .\robocoin_hotel_convert.py `
  --repo-id RoboCOIN/your_dataset `
  --local-name your_dataset `
  --cameras observation.images.camera_head_rgb,observation.images.camera_left_wrist_rgb,observation.images.camera_right_wrist_rgb `
  --probe-episodes 0,1,2,10 `
  --output-root .\datasets
```

Linux/macOS：

```bash
python robocoin_hotel_convert.py \
  --repo-id RoboCOIN/your_dataset \
  --local-name your_dataset \
  --cameras observation.images.camera_head_rgb,observation.images.camera_left_wrist_rgb,observation.images.camera_right_wrist_rgb \
  --probe-episodes 0,1,2,10 \
  --output-root ./datasets
```

## 自动兼容性修复

工具会自动处理两类已发现问题：

1. 删除 stale feature 声明。
   例如 metadata 里声明了某些 feature，但 parquet 和 stats 中没有对应列。

2. 修复 length-1 list 标量列。
   例如 `scene_annotation` 在 v3 metadata 中是 scalar `int32`，但转换后 parquet 仍可能是 `[0]` 这种 `list<int32>`。工具会把 v3 输出中的该列改成 scalar，并验证与 v2.1 的 `[x]` 语义等价。

原始 `_v21` 目录不会被这些修复修改。

## 自动验证内容

默认会执行：

- `LeRobotDataset` 基础加载
- `dataset[0]` 视频解码
- v3 metadata offset / episode length / frame_index / timestamp 检查
- v2.1 vs v3 全量 `observation.state`、`action`、`timestamp` 差分
- `stats.json` 重算对比
- annotation 语义等价
- 抽样 decoded video frame MAE 对比
- `DataLoader` + `delta_timestamps` temporal window smoke test

跳过视频 oracle。

Windows：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets -SkipVideoValidate
```

Linux/macOS：

```bash
bash run_all.sh --preset all --output-root ./datasets --skip-video-validate
```

只做基础加载，不做 oracle。

Windows：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets -SkipOracleValidate
```

Linux/macOS：

```bash
bash run_all.sh --preset all --output-root ./datasets --skip-oracle-validate
```

## 人工边界检查

如果环境创建时没有安装可视化依赖，先安装。

Windows：

```powershell
python -m pip install -r requirements-viz.txt
$env:PYTHONPATH=(Resolve-Path ".\_deps\lerobot\src").Path + ";" + $env:PYTHONPATH
```

Linux/macOS：

```bash
python -m pip install -r requirements-viz.txt
export PYTHONPATH="$(pwd)/_deps/lerobot/src:${PYTHONPATH:-}"
```

人工检查 Kuavo 4 格式。

Windows：

```powershell
$root=(Resolve-Path ".\datasets\Leju_Kuavo_4_hotel_services_v30").Path

python -m lerobot.scripts.lerobot_dataset_viz `
  --repo-id RoboCOIN/Leju_Kuavo_4_hotel_services `
  --root $root `
  --mode local `
  --episode-index 0
```

Linux/macOS：

```bash
root="$(pwd)/datasets/Leju_Kuavo_4_hotel_services_v30"

python -m lerobot.scripts.lerobot_dataset_viz \
  --repo-id RoboCOIN/Leju_Kuavo_4_hotel_services \
  --root "$root" \
  --mode local \
  --episode-index 0
```

人工检查 leju_robot hotel-services 格式。

Windows：

```powershell
$root=(Resolve-Path ".\datasets\leju_robot_hotel_services_h_v30").Path

python -m lerobot.scripts.lerobot_dataset_viz `
  --repo-id RoboCOIN/leju_robot_hotel_services_h `
  --root $root `
  --mode local `
  --episode-index 0
```

Linux/macOS：

```bash
root="$(pwd)/datasets/leju_robot_hotel_services_h_v30"

python -m lerobot.scripts.lerobot_dataset_viz \
  --repo-id RoboCOIN/leju_robot_hotel_services_h \
  --root "$root" \
  --mode local \
  --episode-index 0
```

边界 episode 建议：

```text
开头: 0 / 1
中间: total_episodes // 2 附近
结尾: total_episodes - 2 / total_episodes - 1
```

已完成两个样例的边界：

```text
RoboCOIN/Leju_Kuavo_4_hotel_services: 0, 100, 483
RoboCOIN/leju_robot_hotel_services_h: 0, 100, 204
```

重点看：

- episode 末尾是否串到下一集
- 三路相机是否同步
- left/right wrist 是否交换
- state/action 曲线是否和画面一致
- 结尾是否有黑帧、跳帧或突然跳 scene

## 常用参数

强制重跑。

Windows：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets -Force
```

Linux/macOS：

```bash
bash run_all.sh --preset all --output-root ./datasets --force
```

已有下载结果，只重新转换和验证。

Windows：

```powershell
.\run_all.ps1 -Preset leju_robot_hotel_services_h -OutputRoot .\datasets -SkipDownload
```

Linux/macOS：

```bash
bash run_all.sh --preset leju_robot_hotel_services_h --output-root ./datasets --skip-download
```

已有 v3 输出，只重新验证。

Windows：

```powershell
.\run_all.ps1 -Preset leju_robot_hotel_services_h -OutputRoot .\datasets -SkipDownload -SkipConvert
```

Linux/macOS：

```bash
bash run_all.sh --preset leju_robot_hotel_services_h --output-root ./datasets --skip-download --skip-convert
```

指定 Python 解释器。

Windows：

```powershell
.\run_all.ps1 -Python ".\.venv\Scripts\python.exe" -Preset all -OutputRoot .\datasets
```

Linux/macOS：

```bash
bash run_all.sh --python ./.venv/bin/python --preset all --output-root ./datasets
```

## 目录上传建议

适合上传到 GitHub 的文件：

```text
README.md
robocoin_hotel_convert.py
run_all.ps1
run_all.sh
setup_env.ps1
setup_env.sh
requirements.txt
requirements-viz.txt
.gitignore
.gitattributes
```

不要上传：

```text
datasets/
_deps/
.venv/
__pycache__/
*.log
```
