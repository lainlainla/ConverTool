# RoboCOIN Hotel LeRobot v2.1 -> v3.0 Convert Tool

这个目录是一个可独立上传 GitHub 的转换工具，用于把 RoboCOIN 酒店领域数据从 LeRobot v2.1 转为 LeRobot v3.0，并做本地兼容性验证。工具不会上传到 Hugging Face。

迁移依据是 LeRobot 官方 `convert_dataset_v21_to_v30.py`。本工具额外封装下载、目录规范化、RoboCOIN 兼容性修复、oracle differential validation 和人工边界检查命令。

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

## 输出约定

每个数据集会输出两个目录：

```text
<output-root>/<local_name>_v21   # 原始 v2.1
<output-root>/<local_name>_v30   # 转换后的 v3.0
```

官方脚本内部会临时把原目录改成 `_old`；本工具最后会规范回 `_v21` 和 `_v30`，避免人工验证时混淆。

## 安装

```powershell
cd converTool
python -m pip install -r requirements.txt
```

还需要可用的 LeRobot 源码。推荐传入已有 `src`：

```powershell
.\run_all.ps1 -LeRobotSrc "D:\CUHK_SZ\FNii\robomem\data\lerobot\lerobot-main\src" -DryRun
```

也可以让工具自动 clone：

```powershell
.\run_all.ps1 -AutoCloneLeRobot -DryRun
```

## Hugging Face 登录

先登录：

```powershell
huggingface-cli login
```

如果数据集是 public gated repo，token 需要开启：

```text
Read access to contents of all public gated repos you can access
```

并确认你已经在 Hugging Face 数据集页面申请或同意访问。工具只读取本机 Hugging Face token，不会打印 token。

## 一键转换全部内置数据集

先做 dry-run，确认 17 个 repo 的输出位置：

```powershell
cd converTool

.\run_all.ps1 `
  -Preset all `
  -OutputRoot .\datasets `
  -LeRobotSrc "D:\CUHK_SZ\FNii\robomem\data\lerobot\lerobot-main\src" `
  -DryRun
```

确认后正式下载、转换、验证：

```powershell
.\run_all.ps1 `
  -Preset all `
  -OutputRoot .\datasets `
  -LeRobotSrc "D:\CUHK_SZ\FNii\robomem\data\lerobot\lerobot-main\src"
```

如果直连 `huggingface.co` 不稳定，工具会在 `auto` 模式下 fallback 到 `hf-mirror.com` 的 curl 下载。也可以强制使用 mirror：

```powershell
.\run_all.ps1 `
  -Preset all `
  -OutputRoot .\datasets `
  -LeRobotSrc "D:\CUHK_SZ\FNii\robomem\data\lerobot\lerobot-main\src" `
  -DownloadBackend curl `
  -MirrorEndpoint https://hf-mirror.com
```

## 单独处理一个数据集

```powershell
.\run_all.ps1 -Preset kuavo4_hotel_services -OutputRoot .\datasets -LeRobotSrc "D:\path\to\lerobot-main\src"

.\run_all.ps1 -Preset leju_robot_hotel_services_h -OutputRoot .\datasets -LeRobotSrc "D:\path\to\lerobot-main\src"

.\run_all.ps1 -Preset leju_robot_hotel_services_a -OutputRoot .\datasets -LeRobotSrc "D:\path\to\lerobot-main\src"
```

## 自定义 RoboCOIN hotel repo

如果后续出现同格式新 repo：

```powershell
python .\robocoin_hotel_convert.py `
  --repo-id RoboCOIN/your_dataset `
  --local-name your_dataset `
  --cameras observation.images.camera_head_rgb,observation.images.camera_left_wrist_rgb,observation.images.camera_right_wrist_rgb `
  --probe-episodes 0,1,2,10 `
  --output-root .\datasets `
  --lerobot-src "D:\path\to\lerobot-main\src"
```

## 工具会自动做的兼容性修复

1. 删除 stale feature 声明。
   例如 `gripper_open_scale_state/action` 在 metadata 里声明了，但 parquet 和 stats 中没有对应列。

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
.\run_all.ps1 -Preset all -LeRobotSrc "D:\path\to\lerobot-main\src" -SkipVideoValidate
```

## 人工边界检查

安装可视化依赖：

```powershell
python -m pip install -r requirements-viz.txt
```

人工检查 Kuavo 4 格式：

```powershell
$env:PYTHONPATH="D:\CUHK_SZ\FNii\robomem\data\lerobot\lerobot-main\src;$env:PYTHONPATH"
$root="D:\CUHK_SZ\FNii\robomem\data\lerobot\dataset\robocoin\converTool\datasets\Leju_Kuavo_4_hotel_services_v30"

python -m lerobot.scripts.lerobot_dataset_viz `
  --repo-id RoboCOIN/Leju_Kuavo_4_hotel_services `
  --root $root `
  --mode local `
  --episode-index 0
```

人工检查 leju_robot hotel-services 格式：

```powershell
$env:PYTHONPATH="D:\CUHK_SZ\FNii\robomem\data\lerobot\lerobot-main\src;$env:PYTHONPATH"
$root="D:\CUHK_SZ\FNii\robomem\data\lerobot\dataset\robocoin\converTool\datasets\leju_robot_hotel_services_h_v30"

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

## 常用命令

只看执行计划，不下载不转换：

```powershell
python .\robocoin_hotel_convert.py --preset all --dry-run --lerobot-src "D:\path\to\lerobot-main\src"
```

强制重跑，删除 output root 下对应旧产物：

```powershell
.\run_all.ps1 -Preset all -OutputRoot .\datasets -LeRobotSrc "D:\path\to\lerobot-main\src" -Force
```

已有下载结果，只重新转换和验证：

```powershell
.\run_all.ps1 -Preset leju_robot_hotel_services_h -OutputRoot .\datasets -LeRobotSrc "D:\path\to\lerobot-main\src" -SkipDownload
```
