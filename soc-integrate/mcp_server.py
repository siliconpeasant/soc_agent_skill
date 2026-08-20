#!/usr/bin/env python3
"""SoC Integrate MCP server (stdio / optional SSE)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

from mcp.server.fastmcp import FastMCP

SCRIPT_DIR = Path(__file__).resolve().parent / "scripts"
CLI = SCRIPT_DIR / "soc_integrate.py"

mcp = FastMCP(
    name="soc-integrate",
    instructions=(
        "SoC RTL 端口提取、实例化、wrapper、顶层集成和接口变更追踪工具。"
        "soc_update 仅在 .integrate.json 所列子模块端口变化时刷新生成顶；"
        "口未变时用 snapshot/csv，不要为关账重生顶。"
    ),
)


def _run_cli(*args: str, timeout: int = 120) -> str:
    command: Sequence[str] = [sys.executable, str(CLI), *[str(a) for a in args]]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"python not found while running soc_integrate.py") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"soc_integrate.py timed out after {timeout}s") from exc

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if result.returncode != 0:
        detail = (stdout + "\n" + stderr).strip() or f"exit {result.returncode}"
        raise RuntimeError(detail)
    if stdout and stderr:
        return stdout.rstrip() + "\n[stderr]\n" + stderr.rstrip()
    return (stdout or stderr).rstrip()


@mcp.tool()
def soc_extract(verilog_file: str, module_name: str = "") -> str:
    """提取 Verilog 模块的端口信息（方向、位宽、参数）。"""
    args = ["extract", verilog_file]
    if module_name:
        args += ["-m", module_name]
    return _run_cli(*args)


@mcp.tool()
def soc_instantiate(verilog_file: str, instance_name: str = "") -> str:
    """生成 Verilog 模块的实例化代码（.port(signal) 格式）。"""
    args = ["instantiate", verilog_file]
    if instance_name:
        args += ["-n", instance_name]
    return _run_cli(*args)


@mcp.tool()
def soc_integrate(
    module_files: list[str],
    top_name: str,
    output_file: str,
    port_map: str = "",
) -> str:
    """将多个 Verilog 模块集成到一个顶层模块中。"""
    args = ["integrate"] + list(module_files) + ["-n", top_name, "-o", output_file]
    if port_map:
        args += ["--map", port_map]
    return _run_cli(*args)


@mcp.tool()
def soc_wrap(
    verilog_file: str,
    module_name: str = "",
    wrapper_name: str = "",
    output: str = "",
) -> str:
    """生成 Verilog 模块的 wrapper（信号透传 + 可选逻辑注入点）。"""
    args = ["wrap", verilog_file]
    if module_name:
        args += ["-m", module_name]
    if wrapper_name:
        args += ["-n", wrapper_name]
    if output:
        args += ["-o", output]
    return _run_cli(*args)


@mcp.tool()
def soc_csv(verilog_file: str, module_name: str = "", output: str = "ports.csv") -> str:
    """将 Verilog 模块端口导出为 CSV。"""
    args = ["csv", verilog_file, "-o", output]
    if module_name:
        args += ["-m", module_name]
    return _run_cli(*args)


@mcp.tool()
def soc_snapshot(
    verilog_file: str,
    module_name: str = "",
    output: str = "",
    format_type: str = "both",
    version: str = "1.0.0",
    changelog: str = "",
) -> str:
    """保存 Verilog 模块端口快照（JSON + CSV）。"""
    args = ["snapshot", verilog_file, "-f", format_type, "-v", version]
    if module_name:
        args += ["-m", module_name]
    if output:
        args += ["-o", output]
    if changelog:
        args += ["-c", changelog]
    return _run_cli(*args)


@mcp.tool()
def soc_diff(verilog_file: str, snapshot_file: str, module_name: str = "") -> str:
    """对比当前 Verilog 模块与历史快照的端口差异。"""
    args = ["diff", verilog_file, snapshot_file]
    if module_name:
        args += ["-m", module_name]
    return _run_cli(*args)


@mcp.tool()
def soc_extract_map(
    top_file: str,
    output: str = "",
    verify_modules: Optional[list[str]] = None,
) -> str:
    """从顶层 Verilog 提取实例化连接，生成 port map JSON。"""
    args = ["extract-map", top_file]
    if output:
        args += ["-o", output]
    if verify_modules:
        args += ["--verify"] + list(verify_modules)
    return _run_cli(*args)


@mcp.tool()
def soc_update(
    config_file: str,
    output: str = "",
    port_map: str = "",
    top_name: str = "",
) -> str:
    """子模块端口变化后，按 .integrate.json 刷新已生成顶层。口未变时不要调用。"""
    args = ["update", config_file]
    if output:
        args += ["-o", output]
    if port_map:
        args += ["--map", port_map]
    if top_name:
        args += ["-n", top_name]
    return _run_cli(*args)


@mcp.tool()
def soc_remove(config_file: str, module_name: str) -> str:
    """从集成配置中删除指定模块并刷新顶层。"""
    return _run_cli("remove", config_file, module_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SoC Integrate MCP Server")
    parser.add_argument("--sse", action="store_true", help="Use SSE (HTTP) transport")
    args = parser.parse_args()
    mcp.run(transport="sse" if args.sse else "stdio")
