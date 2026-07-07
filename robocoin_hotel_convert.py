#!/usr/bin/env python
"""Download RoboCOIN hotel datasets and convert LeRobot v2.1 data to v3.0.

The tool wraps the official LeRobot v2.1 -> v3.0 converter and applies the two
compatibility fixes observed in RoboCOIN hotel-service datasets:

1. Remove stale feature declarations that are not present in data parquet files.
2. Rewrite length-1 list columns to scalar columns when LeRobot v3 metadata maps
   them to scalar features, e.g. ``scene_annotation``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import get_token, snapshot_download


LEJU_ROBOT_CAMERA_KEYS = [
    "observation.images.camera_head_rgb",
    "observation.images.camera_left_wrist_rgb",
    "observation.images.camera_right_wrist_rgb",
]

LEJU_ROBOT_HOTEL_SUFFIXES = [
    "e",
    "f",
    "a",
    "c",
    "d",
    "b",
    "i",
    "h",
    "ad",
    "ah",
    "ag",
    "ac",
    "af",
    "ae",
    "aa",
    "ab",
]


def leju_robot_preset(suffix: str) -> dict[str, Any]:
    local_name = f"leju_robot_hotel_services_{suffix}"
    return {
        "repo_id": f"RoboCOIN/{local_name}",
        "local_name": local_name,
        "cameras": LEJU_ROBOT_CAMERA_KEYS,
        "probe_episodes": [0, 1, 2, 10, 100, 204],
    }


PRESETS: dict[str, dict[str, Any]] = {
    "kuavo4_hotel_services": {
        "repo_id": "RoboCOIN/Leju_Kuavo_4_hotel_services",
        "local_name": "Leju_Kuavo_4_hotel_services",
        "cameras": [
            "observation.images.cam_front_head_rgb",
            "observation.images.cam_left_wrist_rgb",
            "observation.images.cam_right_wrist_rgb",
        ],
        "probe_episodes": [0, 1, 2, 10, 100, 250, 483],
    },
    **{f"leju_robot_hotel_services_{suffix}": leju_robot_preset(suffix) for suffix in LEJU_ROBOT_HOTEL_SUFFIXES},
}


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatasetJob:
    repo_id: str
    local_name: str
    cameras: list[str]
    probe_episodes: list[int]


def log(message: str) -> None:
    print(message, flush=True)


def ok(message: str) -> None:
    log(f"[OK] {message}")


def info(message: str) -> None:
    log(f"[INFO] {message}")


def fail(message: str) -> None:
    raise ToolError(message)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    tmp.replace(path)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safe_rmtree(path: Path, root: Path) -> None:
    path = path.resolve()
    root = root.resolve()
    if path == root or not is_relative_to(path, root):
        fail(f"Refusing to remove path outside output root: {path}")
    if path.exists():
        shutil.rmtree(path)


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_csv_ints(value: str | None) -> list[int]:
    return [int(item) for item in parse_csv(value)]


def make_job_from_args(args: argparse.Namespace) -> list[DatasetJob]:
    if args.repo_id:
        if not args.local_name:
            args.local_name = args.repo_id.split("/")[-1]
        if not args.cameras:
            fail("--cameras is required when --repo-id is used without a preset")
        probes = parse_csv_ints(args.probe_episodes)
        return [
            DatasetJob(
                repo_id=args.repo_id,
                local_name=args.local_name,
                cameras=parse_csv(args.cameras),
                probe_episodes=probes,
            )
        ]

    if args.preset == "all":
        selected = list(PRESETS)
    else:
        selected = [args.preset]

    jobs: list[DatasetJob] = []
    for name in selected:
        preset = PRESETS[name]
        jobs.append(
            DatasetJob(
                repo_id=preset["repo_id"],
                local_name=preset["local_name"],
                cameras=list(preset["cameras"]),
                probe_episodes=list(preset["probe_episodes"]),
            )
        )
    return jobs


def curl_binary() -> str:
    exe = shutil.which("curl.exe") or shutil.which("curl")
    if not exe:
        fail("curl is required for curl fallback download, but it was not found on PATH")
    return exe


def run_command(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> None:
    shown = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    info(f"run: {shown}")
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env)
    if proc.returncode != 0:
        fail(f"Command failed with exit code {proc.returncode}: {shown}")


def run_curl(args: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [curl_binary(), *args],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def auth_header(token: str) -> str:
    return f"Authorization: Bearer {token}"


def api_json(endpoint: str, repo_id: str, token: str) -> dict[str, Any]:
    url = f"{endpoint.rstrip('/')}/api/datasets/{repo_id}"
    proc = run_curl(["-sSL", "--max-time", "120", "-H", auth_header(token), url])
    if proc.returncode != 0:
        fail(f"curl API failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout.encode("utf-8").decode("utf-8-sig"))


def resolve_url(endpoint: str, repo_id: str, revision: str, filename: str) -> str:
    parts = [quote(part) for part in filename.replace("\\", "/").split("/")]
    return f"{endpoint.rstrip('/')}/datasets/{repo_id}/resolve/{revision}/{'/'.join(parts)}"


def remote_size(endpoint: str, repo_id: str, revision: str, filename: str, token: str) -> int | None:
    url = resolve_url(endpoint, repo_id, revision, filename)
    proc = run_curl(["-sSIL", "--max-time", "120", "-H", auth_header(token), url])
    if proc.returncode != 0:
        return None
    sizes: list[int] = []
    for line in proc.stdout.splitlines():
        key, _, raw_value = line.partition(":")
        if key.lower() in {"content-length", "x-linked-size"}:
            try:
                sizes.append(int(raw_value.strip()))
            except ValueError:
                pass
    return sizes[-1] if sizes else None


def download_one_with_curl(
    endpoint: str,
    repo_id: str,
    revision: str,
    filename: str,
    local_dir: Path,
    token: str,
    check_size: bool,
) -> tuple[str, str]:
    target = local_dir / Path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)

    size = remote_size(endpoint, repo_id, revision, filename, token) if check_size else None
    if size is not None and target.exists():
        local_size = target.stat().st_size
        if local_size == size:
            return filename, "skip"
        if local_size > size:
            target.unlink()

    proc = run_curl(
        [
            "-fL",
            "-sS",
            "--retry",
            "8",
            "--retry-delay",
            "2",
            "--retry-all-errors",
            "--connect-timeout",
            "60",
            "-H",
            auth_header(token),
            "-C",
            "-",
            "-o",
            str(target),
            resolve_url(endpoint, repo_id, revision, filename),
        ]
    )
    if proc.returncode != 0:
        return filename, f"fail: {proc.stderr.strip() or proc.stdout.strip()}"
    if size is not None and target.stat().st_size != size:
        return filename, f"fail: size mismatch {target.stat().st_size} != {size}"
    return filename, "download"


def download_with_curl(
    repo_id: str,
    local_dir: Path,
    revision: str,
    endpoint: str,
    workers: int,
    check_size: bool = True,
) -> None:
    token = get_token()
    if not token:
        fail("No Hugging Face token found. Run `huggingface-cli login` first.")

    local_dir.mkdir(parents=True, exist_ok=True)
    dataset_info = api_json(endpoint, repo_id, token)
    siblings = [item["rfilename"] for item in dataset_info.get("siblings", []) if "rfilename" in item]
    if not siblings:
        fail(f"No files found for {repo_id} from {endpoint}")

    info(f"curl download repo={repo_id} sha={dataset_info.get('sha')} files={len(siblings)}")
    done = 0
    failed: list[tuple[str, str]] = []
    counts = {"skip": 0, "download": 0}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [
            executor.submit(
                download_one_with_curl,
                endpoint,
                repo_id,
                revision,
                filename,
                local_dir,
                token,
                check_size,
            )
            for filename in siblings
        ]
        for future in as_completed(futures):
            filename, status = future.result()
            done += 1
            if status in counts:
                counts[status] += 1
            else:
                failed.append((filename, status))
                log(f"[FAIL] {filename}: {status}")
            if done % 25 == 0 or done == len(futures):
                info(
                    f"download progress={done}/{len(futures)} "
                    f"skip={counts['skip']} download={counts['download']} fail={len(failed)}"
                )

    if failed:
        sample = "\n".join(f"{name}: {status}" for name, status in failed[:20])
        fail(f"{len(failed)} file(s) failed during curl download:\n{sample}")
    ok(f"download complete: {local_dir}")


def download_dataset(
    repo_id: str,
    local_dir: Path,
    revision: str,
    backend: str,
    hf_endpoint: str,
    mirror_endpoint: str,
    workers: int,
) -> None:
    local_dir.mkdir(parents=True, exist_ok=True)
    if (local_dir / "meta" / "info.json").exists():
        ok(f"download skipped; local v2.1 dataset exists: {local_dir}")
        return

    if backend in {"auto", "hub"}:
        old_endpoint = os.environ.get("HF_ENDPOINT")
        os.environ["HF_ENDPOINT"] = hf_endpoint
        try:
            snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                revision=revision,
                local_dir=local_dir,
                max_workers=workers,
            )
            ok(f"huggingface_hub download complete: {local_dir}")
            return
        except Exception as exc:
            if backend == "hub":
                raise
            info(f"huggingface_hub download failed, falling back to curl mirror: {type(exc).__name__}: {exc}")
        finally:
            if old_endpoint is None:
                os.environ.pop("HF_ENDPOINT", None)
            else:
                os.environ["HF_ENDPOINT"] = old_endpoint

    download_with_curl(repo_id, local_dir, revision, mirror_endpoint, workers)


def default_lerobot_src_candidates(tool_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get("LEROBOT_SRC")
    if env_value:
        candidates.append(Path(env_value))
    for parent in [tool_dir, *tool_dir.parents]:
        candidates.append(parent / "lerobot-main" / "src")
        candidates.append(parent / "lerobot" / "src")
        candidates.append(parent / "_deps" / "lerobot" / "src")
    return candidates


def auto_clone_lerobot(tool_dir: Path) -> Path:
    deps = tool_dir / "_deps"
    repo = deps / "lerobot"
    src = repo / "src"
    if src.exists():
        return src
    deps.mkdir(parents=True, exist_ok=True)
    run_command(["git", "clone", "https://github.com/huggingface/lerobot.git", str(repo)])
    if not src.exists():
        fail(f"LeRobot clone did not contain src directory: {src}")
    return src


def locate_lerobot_src(tool_dir: Path, explicit: str | None, auto_clone: bool) -> Path:
    candidates = [Path(explicit)] if explicit else default_lerobot_src_candidates(tool_dir)
    for candidate in candidates:
        converter = candidate / "lerobot" / "scripts" / "convert_dataset_v21_to_v30.py"
        if converter.exists():
            return candidate.resolve()
    if auto_clone:
        return auto_clone_lerobot(tool_dir).resolve()
    fail(
        "Could not locate LeRobot source. Pass --lerobot-src, set LEROBOT_SRC, "
        "place lerobot-main/src near this tool, or use --auto-clone-lerobot."
    )


def dataset_version(root: Path) -> str | None:
    info_path = root / "meta" / "info.json"
    if not info_path.exists():
        return None
    return read_json(info_path).get("codebase_version")


def prepare_work_dir(v21_dir: Path, work_dir: Path, output_root: Path, force: bool) -> None:
    if work_dir.exists():
        version = dataset_version(work_dir)
        if version == "v2.1":
            return
        if force:
            safe_rmtree(work_dir, output_root)
        else:
            fail(f"Work directory exists and is not v2.1: {work_dir}")

    if v21_dir.exists():
        if dataset_version(v21_dir) != "v2.1":
            fail(f"Existing v21 directory is not v2.1: {v21_dir}")
        shutil.move(str(v21_dir), str(work_dir))


def normalize_after_conversion(
    work_dir: Path,
    v21_dir: Path,
    v30_dir: Path,
    output_root: Path,
    force: bool,
) -> None:
    old_dir = work_dir.parent / f"{work_dir.name}_old"
    if dataset_version(work_dir) != "v3.0":
        fail(f"Expected converted v3.0 at {work_dir}, got {dataset_version(work_dir)!r}")
    if dataset_version(old_dir) != "v2.1":
        fail(f"Expected original v2.1 at {old_dir}, got {dataset_version(old_dir)!r}")

    for target in [v21_dir, v30_dir]:
        if target.exists():
            if force:
                safe_rmtree(target, output_root)
            else:
                fail(f"Target already exists: {target}. Use --force to replace it.")

    shutil.move(str(old_dir), str(v21_dir))
    shutil.move(str(work_dir), str(v30_dir))
    ok(f"normalized directories: v21={v21_dir.name}, v30={v30_dir.name}")


def run_lerobot_converter(
    repo_id: str,
    work_dir: Path,
    lerobot_src: Path,
    data_file_size_mb: int,
    video_file_size_mb: int,
) -> None:
    converter = lerobot_src / "lerobot" / "scripts" / "convert_dataset_v21_to_v30.py"
    if not converter.exists():
        fail(f"Missing converter script: {converter}")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(lerobot_src) + os.pathsep + env.get("PYTHONPATH", "")
    run_command(
        [
            sys.executable,
            str(converter),
            "--repo-id",
            repo_id,
            "--root",
            str(work_dir),
            "--push-to-hub",
            "false",
            "--data-file-size-in-mb",
            str(data_file_size_mb),
            "--video-file-size-in-mb",
            str(video_file_size_mb),
        ],
        env=env,
    )


def first_data_parquet(root: Path) -> Path:
    files = sorted((root / "data").glob("*/*.parquet"))
    if not files:
        fail(f"No v3 data parquet files found under {root / 'data'}")
    return files[0]


def fix_missing_feature_declarations(v3_root: Path) -> list[str]:
    info_path = v3_root / "meta" / "info.json"
    info_data = read_json(info_path)
    data_columns = set(pq.read_table(first_data_parquet(v3_root)).column_names)
    removed: list[str] = []
    for key, feature in list(info_data.get("features", {}).items()):
        if feature.get("dtype") == "video":
            continue
        if key not in data_columns:
            removed.append(key)
            del info_data["features"][key]

    if removed:
        write_json(info_path, info_data)
        ok(f"removed stale feature declarations: {removed}")
    return removed


def scalarize_length_one_columns(v3_root: Path) -> list[str]:
    info_data = read_json(v3_root / "meta" / "info.json")
    changed_columns: set[str] = set()
    parquet_files = sorted((v3_root / "data").glob("*/*.parquet"))
    for path in parquet_files:
        table = pq.read_table(path)
        names = table.column_names
        new_table = table
        for key, feature in info_data.get("features", {}).items():
            if feature.get("dtype") == "video" or feature.get("shape") != [1] or key not in names:
                continue
            field = new_table.schema.field(key)
            if not pa.types.is_list(field.type) and not pa.types.is_large_list(field.type):
                continue
            values = []
            for item in new_table.column(key).to_pylist():
                if isinstance(item, list):
                    if len(item) != 1:
                        fail(f"Cannot scalarize {key}: encountered non length-1 value {item!r}")
                    values.append(item[0])
                else:
                    values.append(item)
            arrow_type = pa.from_numpy_dtype(np.dtype(feature["dtype"]))
            new_col = pa.array(values, type=arrow_type)
            new_table = new_table.set_column(names.index(key), key, new_col)
            changed_columns.add(key)
        if new_table is not table:
            tmp = path.with_suffix(path.suffix + ".tmp")
            pq.write_table(new_table, tmp)
            tmp.replace(path)
    if changed_columns:
        ok(f"scalarized length-1 columns: {sorted(changed_columns)}")
    return sorted(changed_columns)


def apply_v3_compatibility_fixes(v3_root: Path) -> None:
    removed = fix_missing_feature_declarations(v3_root)
    scalarized = scalarize_length_one_columns(v3_root)
    if not removed and not scalarized:
        ok("no v3 compatibility fixes needed")


def read_parquets(root: Path, pattern: str) -> pd.DataFrame:
    files = sorted(root.glob(pattern))
    if not files:
        fail(f"No parquet files matched {root / pattern}")
    return pd.concat([pq.read_table(path).to_pandas() for path in files], ignore_index=True)


def stack_array_col(df: pd.DataFrame, col: str) -> np.ndarray:
    return np.stack([np.asarray(item) for item in df[col].to_numpy()])


def assert_close(name: str, actual: np.ndarray, expected: np.ndarray, rtol: float, atol: float) -> float:
    if actual.shape != expected.shape:
        fail(f"{name} shape mismatch: {actual.shape} vs {expected.shape}")
    diff = float(np.max(np.abs(actual - expected))) if actual.size else 0.0
    if not np.allclose(actual, expected, rtol=rtol, atol=atol):
        fail(f"{name} mismatch: max_abs_diff={diff}")
    return diff


def validate_basic_v3(v3_root: Path, repo_id: str, lerobot_src: Path) -> None:
    sys.path.insert(0, str(lerobot_src))
    info_data = read_json(v3_root / "meta" / "info.json")
    if info_data.get("codebase_version") != "v3.0":
        fail(f"Expected v3.0 dataset, got {info_data.get('codebase_version')!r}")

    episodes = read_parquets(v3_root, "meta/episodes/**/*.parquet")
    data_file = first_data_parquet(v3_root)
    data_rows = pq.read_metadata(data_file).num_rows
    video_files = sorted((v3_root / "videos").glob("*/*/*.mp4"))
    if len(episodes) != int(info_data["total_episodes"]):
        fail("v3 episode metadata row count does not match info.json")
    if data_rows != int(info_data["total_frames"]):
        fail("v3 data row count does not match info.json")

    from lerobot.datasets import LeRobotDataset

    dataset = LeRobotDataset(repo_id, root=v3_root, revision="v3.0")
    if len(dataset) != int(info_data["total_frames"]):
        fail("LeRobotDataset frame count does not match info.json")
    if dataset.num_episodes != int(info_data["total_episodes"]):
        fail("LeRobotDataset episode count does not match info.json")
    if len(dataset) > 0:
        _ = dataset[0]
    ok(
        f"basic v3 load ok: episodes={dataset.num_episodes}, frames={len(dataset)}, "
        f"video_shards={len(video_files)}"
    )


def find_v21_episode_files(v21_root: Path) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for path in sorted((v21_root / "data").glob("**/episode_*.parquet")):
        stem = path.stem.removeprefix("episode_")
        result[int(stem)] = path
    if not result:
        fail(f"No v2.1 episode parquet files found: {v21_root}")
    return result


def validate_metadata_and_numeric(v21_root: Path, v3_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    v21_info = read_json(v21_root / "meta" / "info.json")
    v3_info = read_json(v3_root / "meta" / "info.json")
    for key in ["total_episodes", "total_frames", "fps"]:
        if v21_info.get(key) != v3_info.get(key):
            fail(f"{key} mismatch: v21={v21_info.get(key)} v3={v3_info.get(key)}")

    episodes = read_parquets(v3_root, "meta/episodes/**/*.parquet").sort_values("episode_index").reset_index(drop=True)
    v3_data = read_parquets(v3_root, "data/**/*.parquet").sort_values("index").reset_index(drop=True)
    if len(v3_data) != int(v3_info["total_frames"]):
        fail("v3 data rows do not match total_frames")
    if len(episodes) != int(v3_info["total_episodes"]):
        fail("v3 episode rows do not match total_episodes")

    lengths = episodes["length"].astype(int).to_numpy()
    if int(lengths.sum()) != int(v3_info["total_frames"]):
        fail("episode length sum does not match total_frames")
    if {"dataset_from_index", "dataset_to_index"}.issubset(episodes.columns):
        expected_from = np.concatenate([[0], np.cumsum(lengths)[:-1]])
        expected_to = np.cumsum(lengths)
        if not np.array_equal(episodes["dataset_from_index"].astype(int).to_numpy(), expected_from):
            fail("dataset_from_index mismatch")
        if not np.array_equal(episodes["dataset_to_index"].astype(int).to_numpy(), expected_to):
            fail("dataset_to_index mismatch")

    for ep_idx, group in v3_data.groupby("episode_index", sort=True):
        group = group.sort_values("frame_index")
        if not np.array_equal(group["frame_index"].astype(int).to_numpy(), np.arange(len(group))):
            fail(f"bad frame_index in episode {ep_idx}")
        expected_ts = np.arange(len(group), dtype=np.float64) / float(v3_info["fps"])
        assert_close(
            f"timestamp episode {ep_idx}",
            group["timestamp"].to_numpy(dtype=np.float64),
            expected_ts,
            rtol=0,
            atol=0.51 / float(v3_info["fps"]),
        )

    files = find_v21_episode_files(v21_root)
    max_diffs = {"observation.state": 0.0, "action": 0.0, "timestamp": 0.0}
    groups = {
        int(ep): group.sort_values("frame_index").reset_index(drop=True)
        for ep, group in v3_data.groupby("episode_index", sort=True)
    }
    for count, episode_index in enumerate(sorted(files), start=1):
        old = pq.read_table(files[episode_index]).to_pandas().sort_values("frame_index").reset_index(drop=True)
        new = groups[episode_index]
        if len(old) != len(new):
            fail(f"episode {episode_index} length mismatch")
        for col in ["frame_index", "episode_index", "task_index", "index"]:
            if col in old.columns and col in new.columns and not np.array_equal(old[col].to_numpy(), new[col].to_numpy()):
                fail(f"{col} mismatch in episode {episode_index}")
        diff = assert_close(
            f"timestamp episode {episode_index}",
            old["timestamp"].to_numpy(dtype=np.float64),
            new["timestamp"].to_numpy(dtype=np.float64),
            rtol=1e-6,
            atol=1e-7,
        )
        max_diffs["timestamp"] = max(max_diffs["timestamp"], diff)
        for col in ["observation.state", "action"]:
            diff = assert_close(
                f"{col} episode {episode_index}",
                stack_array_col(old, col).astype(np.float64),
                stack_array_col(new, col).astype(np.float64),
                rtol=1e-6,
                atol=1e-7,
            )
            max_diffs[col] = max(max_diffs[col], diff)
        if count % 100 == 0:
            info(f"numeric diff progress={count}/{len(files)}")
    ok(f"numeric oracle passed: {max_diffs}")
    return episodes, v3_data


def validate_stats(v3_root: Path, v3_data: pd.DataFrame) -> None:
    stats = read_json(v3_root / "meta" / "stats.json")
    diffs: dict[str, dict[str, float]] = {}
    for col in ["observation.state", "action"]:
        arr = stack_array_col(v3_data, col).astype(np.float64)
        diffs[col] = {}
        for key, actual in {
            "mean": arr.mean(axis=0),
            "std": arr.std(axis=0),
            "min": arr.min(axis=0),
            "max": arr.max(axis=0),
        }.items():
            diffs[col][key] = assert_close(
                f"stats {col}/{key}",
                actual,
                np.asarray(stats[col][key], dtype=np.float64),
                rtol=1e-5,
                atol=1e-6,
            )
    ok(f"stats match: {diffs}")


def validate_annotation_equivalence(v21_root: Path, v3_data: pd.DataFrame) -> None:
    files = find_v21_episode_files(v21_root)
    old = pd.concat([pq.read_table(path).to_pandas() for path in files.values()], ignore_index=True)
    old = old.sort_values("index").reset_index(drop=True)
    checks: list[str] = []
    if "subtask_annotation" in old.columns and "subtask_annotation" in v3_data.columns:
        a = stack_array_col(old, "subtask_annotation")
        b = stack_array_col(v3_data, "subtask_annotation")
        if not np.array_equal(a, b):
            fail("subtask_annotation mismatch")
        checks.append("subtask_annotation")
    if "scene_annotation" in old.columns and "scene_annotation" in v3_data.columns:
        old_values = np.asarray(
            [np.asarray(item).reshape(-1)[0] for item in old["scene_annotation"].to_numpy()],
            dtype=np.int64,
        )
        new_values = []
        for item in v3_data["scene_annotation"].to_numpy():
            arr = np.asarray(item)
            new_values.append(arr.reshape(-1)[0])
        if not np.array_equal(old_values, np.asarray(new_values, dtype=np.int64)):
            fail("scene_annotation mismatch")
        checks.append("scene_annotation")
    if checks:
        ok(f"annotation equivalence passed: {checks}")


def v21_video_path(root: Path, video_key: str, episode_index: int) -> Path:
    matches = sorted((root / "videos").glob(f"**/{video_key}/episode_{episode_index:06d}.mp4"))
    if not matches:
        fail(f"Missing v2.1 video for {video_key} episode {episode_index}")
    return matches[0]


def v3_video_path(root: Path, row: pd.Series, video_key: str) -> Path:
    chunk = int(row[f"videos/{video_key}/chunk_index"])
    file_index = int(row[f"videos/{video_key}/file_index"])
    return root / "videos" / video_key / f"chunk-{chunk:03d}" / f"file-{file_index:03d}.mp4"


def validate_video_and_temporal(
    v21_root: Path,
    v3_root: Path,
    repo_id: str,
    lerobot_src: Path,
    episodes: pd.DataFrame,
    cameras: list[str],
    probe_episodes: list[int],
) -> None:
    sys.path.insert(0, str(lerobot_src))
    import torch
    from lerobot.datasets import LeRobotDataset
    from lerobot.datasets.video_utils import decode_video_frames

    fps = float(read_json(v3_root / "meta" / "info.json")["fps"])
    tolerance_s = 0.51 / fps
    rows = {int(row["episode_index"]): row for _, row in episodes.iterrows()}
    total_episodes = len(rows)
    dynamic_probes = [0, 1, 2, 10, total_episodes // 2, max(0, total_episodes - 2), max(0, total_episodes - 1)]
    probe_episodes = sorted({ep for ep in [*probe_episodes, *dynamic_probes] if ep in rows})
    max_mae = {cam: 0.0 for cam in cameras}
    for ep in probe_episodes:
        if ep not in rows:
            continue
        row = rows[ep]
        length = int(row["length"])
        frame_indices = sorted(set([0, 1, length // 2, max(0, length - 2), length - 1]))
        for cam in cameras:
            old_path = v21_video_path(v21_root, cam, ep)
            new_path = v3_video_path(v3_root, row, cam)
            old_ts = [idx / fps for idx in frame_indices]
            new_from = float(row[f"videos/{cam}/from_timestamp"])
            new_ts = [new_from + idx / fps for idx in frame_indices]
            old_frames = decode_video_frames(old_path, old_ts, tolerance_s, backend="pyav", return_uint8=True)
            new_frames = decode_video_frames(new_path, new_ts, tolerance_s, backend="pyav", return_uint8=True)
            if tuple(old_frames.shape) != tuple(new_frames.shape):
                fail(f"video shape mismatch for {cam} episode {ep}")
            mae = (old_frames.float() - new_frames.float()).abs().mean(dim=(1, 2, 3))
            max_mae[cam] = max(max_mae[cam], float(mae.max()))
    if any(value > 3.0 for value in max_mae.values()):
        fail(f"decoded video MAE too high: {max_mae}")
    ok(f"decoded video oracle passed: {max_mae}")

    delta_timestamps = {cam: [-2 / fps, -1 / fps, 0.0] for cam in cameras}
    delta_timestamps["observation.state"] = [-2 / fps, -1 / fps, 0.0]
    delta_timestamps["action"] = [0.0, 1 / fps, 2 / fps]
    dataset = LeRobotDataset(repo_id, root=v3_root, revision="v3.0", delta_timestamps=delta_timestamps)
    loader = torch.utils.data.DataLoader(dataset, batch_size=2, shuffle=False, num_workers=0)
    for idx, batch in enumerate(loader):
        for key in delta_timestamps:
            if key not in batch:
                fail(f"temporal batch missing key {key}")
        if idx >= 2:
            break
    ok("temporal DataLoader passed")


def run_validation(
    job: DatasetJob,
    v21_dir: Path,
    v30_dir: Path,
    lerobot_src: Path,
    skip_video: bool,
    skip_oracle: bool,
) -> None:
    validate_basic_v3(v30_dir, job.repo_id, lerobot_src)
    if skip_oracle:
        return
    episodes, v3_data = validate_metadata_and_numeric(v21_dir, v30_dir)
    validate_stats(v30_dir, v3_data)
    validate_annotation_equivalence(v21_dir, v3_data)
    if not skip_video:
        validate_video_and_temporal(v21_dir, v30_dir, job.repo_id, lerobot_src, episodes, job.cameras, job.probe_episodes)


def run_job(args: argparse.Namespace, job: DatasetJob, tool_dir: Path, lerobot_src: Path) -> None:
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    work_dir = output_root / f"{job.local_name}_work"
    v21_dir = output_root / f"{job.local_name}_v21"
    v30_dir = output_root / f"{job.local_name}_v30"

    info(f"dataset={job.repo_id}")
    info(f"v21_dir={v21_dir}")
    info(f"v30_dir={v30_dir}")

    if args.dry_run:
        return

    if args.force:
        for path in [work_dir, work_dir.parent / f"{work_dir.name}_old", work_dir.parent / f"{work_dir.name}_v30", v21_dir, v30_dir]:
            if path.exists():
                safe_rmtree(path, output_root)

    if not args.skip_download and not v21_dir.exists() and not work_dir.exists():
        download_dataset(
            job.repo_id,
            work_dir,
            args.revision,
            args.download_backend,
            args.hf_endpoint,
            args.mirror_endpoint,
            args.workers,
        )

    if not args.skip_convert:
        if v30_dir.exists() and v21_dir.exists():
            ok(f"conversion skipped; v21 and v30 outputs already exist for {job.local_name}")
        else:
            prepare_work_dir(v21_dir, work_dir, output_root, args.force)
            if dataset_version(work_dir) != "v2.1":
                fail(f"Cannot convert; missing v2.1 work directory: {work_dir}")
            run_lerobot_converter(
                job.repo_id,
                work_dir,
                lerobot_src,
                args.data_file_size_in_mb,
                args.video_file_size_in_mb,
            )
            normalize_after_conversion(work_dir, v21_dir, v30_dir, output_root, args.force)

    if dataset_version(v30_dir) != "v3.0":
        fail(f"Missing converted v3.0 output: {v30_dir}. Run without --skip-convert or check the output root.")
    if not args.skip_validate and not args.skip_oracle_validate and dataset_version(v21_dir) != "v2.1":
        fail(f"Missing original v2.1 output for oracle validation: {v21_dir}")

    apply_v3_compatibility_fixes(v30_dir)
    if not args.skip_validate:
        run_validation(job, v21_dir, v30_dir, lerobot_src, args.skip_video_validate, args.skip_oracle_validate)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-presets", action="store_true", help="List built-in dataset presets and exit.")
    parser.add_argument("--preset", choices=["all", *PRESETS.keys()], default="all")
    parser.add_argument("--repo-id", help="Custom Hugging Face dataset repo id.")
    parser.add_argument("--local-name", help="Custom local output stem for --repo-id.")
    parser.add_argument("--cameras", help="Comma-separated camera feature keys for --repo-id.")
    parser.add_argument("--probe-episodes", help="Comma-separated probe episodes for --repo-id.")
    parser.add_argument("--output-root", default="datasets")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--hf-endpoint", default="https://huggingface.co")
    parser.add_argument("--mirror-endpoint", default="https://hf-mirror.com")
    parser.add_argument("--download-backend", choices=["auto", "hub", "curl"], default="auto")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--lerobot-src", help="Path to LeRobot source src directory.")
    parser.add_argument("--auto-clone-lerobot", action="store_true")
    parser.add_argument("--data-file-size-in-mb", type=int, default=100)
    parser.add_argument("--video-file-size-in-mb", type=int, default=500)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-convert", action="store_true")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--skip-oracle-validate", action="store_true")
    parser.add_argument("--skip-video-validate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.list_presets:
        for name, preset in PRESETS.items():
            print(f"{name}: {preset['repo_id']}")
        return 0

    tool_dir = Path(__file__).resolve().parent
    jobs = make_job_from_args(args)
    lerobot_src = locate_lerobot_src(tool_dir, args.lerobot_src, args.auto_clone_lerobot)
    ok(f"using LeRobot src: {lerobot_src}")

    for job in jobs:
        run_job(args, job, tool_dir, lerobot_src)
    ok("all requested datasets processed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ToolError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
