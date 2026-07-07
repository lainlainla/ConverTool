# RoboCOIN Hotel LeRobot v2.1 -> v3.0 Convert Tool

这个工具用于把 RoboCOIN 酒店领域数据从 LeRobot v2.1 转为 LeRobot v3.0，并在本地做兼容性验证。流程只读写本地文件，不会上传到 Hugging Face。

工具封装了四件事：

- 下载 Hugging Face 上的 RoboCOIN hotel datasets
- 调用 LeRobot 官方 `convert_dataset_v21_to_v30.py`
- 修复 RoboCOIN hotel 数据里已发现的 v3 兼容问题
- 做 oracle differential validation 和人工边界检查

## 从空机器开始

下面以 Windows PowerShell 为例。新机器至少需要：

- Python 3.12 或 3.13
- Git
- curl
- 足够磁盘空间。`--preset all` 会下载和转换多个视频数据集，建议准备较大的独立数据盘。

如果机器没有 Python 和 Git，可以先用 `winget` 安装：

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
```

安装后重新打开 PowerShell。

进入工具目录：

```powershell
cd converTool
```

创建虚拟环境、安装本工具依赖、clone LeRobot、安装 LeRobot dataset/viz 依赖：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_env.ps1 -CloneLeRobot -InstallViz
.\.venv\Scripts\Activate.ps1
```

如果不需要人工可视化，可以去掉 `-InstallViz`：

```powershell
.\setup_env.ps1 -CloneLeRobot
.\.venv\Scripts\Activate.ps1
```

脚本默认会把 LeRobot clone 到：

```text
converTool/_deps/lerobot
```

这个目录已经在 `.gitignore` 中，不应上传到 GitHub。

## Hugging Face 登录

登录 Hugging Face：

```powershell
hf auth login
```

如果你的环境没有 `hf` 命令，也可以用：

```powershell
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

默认 `--preset all` 会处理下面全部 repo：

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

```powershell
python .\robocoin_hotel_convert.py --list-presets
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

正式下载前先检查执行计划：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets -DryRun
```

如果使用 `setup_env.ps1 -CloneLeRobot`，工具会自动找到 `.\_deps\lerobot\src`，不需要手动传 `-LeRobotSrc`。

如果你已经有自己的 LeRobot 源码，可以指定：

```powershell
.\run_all.ps1 `
  -Preset all `
  -OutputRoot .\datasets `
  -LeRobotSrc "X:\path\to\lerobot\src" `
  -DryRun
```

## 一键下载、转换、验证

处理全部内置数据集：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets
```

单独处理一个数据集：

```powershell
.\run_all.ps1 -Preset kuavo4_hotel_services -OutputRoot .\datasets
.\run_all.ps1 -Preset leju_robot_hotel_services_h -OutputRoot .\datasets
.\run_all.ps1 -Preset leju_robot_hotel_services_a -OutputRoot .\datasets
```

如果直连 `huggingface.co` 不稳定，可以强制使用 mirror：

```powershell
.\run_all.ps1 `
  -Preset all `
  -OutputRoot .\datasets `
  -DownloadBackend curl `
  -MirrorEndpoint https://hf-mirror.com
```

## 自定义 RoboCOIN Hotel Repo

如果后续出现同格式新 repo：

```powershell
python .\robocoin_hotel_convert.py `
  --repo-id RoboCOIN/your_dataset `
  --local-name your_dataset `
  --cameras observation.images.camera_head_rgb,observation.images.camera_left_wrist_rgb,observation.images.camera_right_wrist_rgb `
  --probe-episodes 0,1,2,10 `
  --output-root .\datasets
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

如果只想快速转换，跳过视频 oracle：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets -SkipVideoValidate
```

如果只做基础加载，不做 oracle：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets -SkipOracleValidate
```

## 人工边界检查

如果环境创建时没有安装可视化依赖，先安装：

```powershell
python -m pip install -r requirements-viz.txt
```

如果 LeRobot 是通过 `setup_env.ps1 -CloneLeRobot` 安装的：

```powershell
$env:PYTHONPATH=(Resolve-Path ".\_deps\lerobot\src").Path + ";" + $env:PYTHONPATH
```

人工检查 Kuavo 4 格式：

```powershell
$root=(Resolve-Path ".\datasets\Leju_Kuavo_4_hotel_services_v30").Path

python -m lerobot.scripts.lerobot_dataset_viz `
  --repo-id RoboCOIN/Leju_Kuavo_4_hotel_services `
  --root $root `
  --mode local `
  --episode-index 0
```

人工检查 leju_robot hotel-services 格式：

```powershell
$root=(Resolve-Path ".\datasets\leju_robot_hotel_services_h_v30").Path

python -m lerobot.scripts.lerobot_dataset_viz `
  --repo-id RoboCOIN/leju_robot_hotel_services_h `
  --root $root `
  --mode local `
  --episode-index 0
```

边界 episode 建议：

```text
开头: 0 / 1
中间: total_episodes // 2 附近
结尾: total_episodes - 2 / total_episodes - 1
```

重点看：

- episode 末尾是否串到下一集
- 三路相机是否同步
- left/right wrist 是否交换
- state/action 曲线是否和画面一致
- 结尾是否有黑帧、跳帧或突然跳 scene

## 常用参数

强制重跑，删除 output root 下对应旧产物：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets -Force
```

已有下载结果，只重新转换和验证：

```powershell
.\run_all.ps1 -Preset leju_robot_hotel_services_h -OutputRoot .\datasets -SkipDownload
```

已有 v3 输出，只重新验证：

```powershell
.\run_all.ps1 -Preset leju_robot_hotel_services_h -OutputRoot .\datasets -SkipDownload -SkipConvert
```

指定 Python 解释器：

```powershell
.\run_all.ps1 -Python ".\.venv\Scripts\python.exe" -Preset all -OutputRoot .\datasets
```

__pycache__/
*.log
```
