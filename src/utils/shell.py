import subprocess
import platform
import os
import logging
from pathlib import Path
from typing import List, Union, Optional, Callable


class ToolNotFoundError(Exception):
    """当找不到必要的二进制工具时抛出"""
    pass


class ShellRunner:
    # 官方工具目录常量
    OFFICIAL_BIN_DIR = "offical"  # 注意拼写保持一致

    def __init__(self):
        self.logger = logging.getLogger("Shell")

        system = platform.system().lower()
        if system == "darwin":
            self.os_name = "darwin"  # macOS
        elif system == "linux":
            self.os_name = "linux"
        else:
            self.os_name = "windows"

        machine = platform.machine().lower()
        if machine in ["x86_64", "amd64"]:
            self.arch = "x86_64"
        elif machine in ["aarch64", "arm64"]:
            self.arch = "aarch64"
        else:
            self.arch = "x86_64"  # 默认 fallback

        project_root = Path(__file__).resolve().parent.parent.parent

        # 官方工具目录（最高优先级）
        self.official_bin_dir = project_root / "bin" / self.OFFICIAL_BIN_DIR / self.os_name / self.arch

        # 平台特定工具目录（兼容）
        self.bin_dir = project_root / "bin" / self.os_name / self.arch

        # OTATools 目录
        self.otatools_bin = project_root / "otatools" / "bin"

        # 检查官方目录是否存在
        if not self.official_bin_dir.exists():
            self.logger.warning(f"Official binary directory not found: {self.official_bin_dir}")

    def get_binary_path(self, tool_name: str, required: bool = True) -> Path:
        """
        Get the absolute path of the tool.

        Search Order:
        1. bin/offical/{os}/{arch}/ (Official tools - highest priority)
        2. bin/offical/{os}/{arch}/android-lptools-static-*/ (lptools)
        3. bin/{os}/{arch}/ (Platform specific tools)
        4. otatools/bin/ (Google OTA tools)
        5. bin/ (Common tools)

        Args:
            tool_name: Name of the binary tool
            required: If True, raises ToolNotFoundError when tool not found.
                      If False, returns Path(tool_name) as fallback.

        Returns:
            Path to the tool binary

        Raises:
            ToolNotFoundError: When required=True and tool is not found
        """
        # 1. Official tools directory (highest priority)
        official_path = self.official_bin_dir / tool_name
        if official_path.exists():
            return official_path

        # 2. Check android-lptools-static subdirectory (lpmake, lpunpack, etc.)
        lptools_dirs = list(self.official_bin_dir.glob("android-lptools-static-*"))
        for lptools_dir in lptools_dirs:
            lptools_path = lptools_dir / tool_name
            if lptools_path.exists():
                return lptools_path

        # 3. Platform specific bin directory (legacy)
        bin_path = self.bin_dir / tool_name
        if bin_path.exists():
            return bin_path

        # 4. OTATools
        ota_path = self.otatools_bin / tool_name
        if ota_path.exists():
            return ota_path

        # 5. Common bin directory
        common_bin = self.bin_dir.parent.parent / tool_name
        if common_bin.exists():
            return common_bin

        # 6. Tool not found
        if required:
            raise ToolNotFoundError(
                f"Required binary tool '{tool_name}' not found!\n"
                f"Searched locations:\n"
                f"  - {self.official_bin_dir}/{tool_name}\n"
                f"  - {self.official_bin_dir}/android-lptools-static-*/{tool_name}\n"
                f"  - {self.bin_dir}/{tool_name}\n"
                f"  - {self.otatools_bin}/{tool_name}\n"
                f"  - {self.bin_dir.parent.parent}/{tool_name}\n"
                f"Please download the official tool and place it in bin/offical/{self.os_name}/{self.arch}/"
            )

        # Fallback for non-required tools
        return Path(tool_name)

    def run(self, cmd: Union[str, List[str]], cwd: Optional[Path] = None,
            check: bool = True, capture_output: bool = False,
            env: Optional[dict] = None, logger: Optional[logging.Logger] = None,
            on_line: Optional[Callable[[str], None]] = None,
            shell: bool = False, tool_required: bool = True) -> subprocess.CompletedProcess:
        """
        Core method to execute commands
        :param cmd: List of commands (recommended) or string. e.g. ["lpunpack", "super.img"]
        :param cwd: Working directory for execution
        :param check: If True, raise exception when command returns non-zero
        :param capture_output: Whether to capture stdout/stderr (do not print directly to console)
        :param env: Environment variables dict (will merge with system env)
        :param logger: Optional logger to stream output to (forces capture_output=True)
        :param on_line: Optional callback function called for each line of output
        :param shell: If True, execute the command through the shell
        :param tool_required: If True, raise ToolNotFoundError when binary not found
        """

        # Binary search logic (skipped if shell=True and cmd is a string)
        if not shell and isinstance(cmd, list):
            tool = cmd[0]
            tool_path = self.get_binary_path(tool, required=tool_required)
            if tool_path.is_absolute() and tool_path.exists():
                cmd[0] = str(tool_path)
                if not os.access(tool_path, os.X_OK):
                    os.chmod(tool_path, 0o755)
        
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
            
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
        self.logger.debug(f"Running: {cmd_str}")

        # If a logger or on_line is provided, we must capture output
        should_capture = capture_output or (logger is not None) or (on_line is not None)

        try:
            if logger or on_line:
                # Streaming mode
                process = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    shell=shell if shell else (isinstance(cmd, str)),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=run_env
                )
                
                output_lines = []
                if process.stdout:
                    for line in process.stdout:
                        clean_line = line.strip()
                        if on_line:
                            # If callback provided, it's responsible for logging/filtering
                            on_line(clean_line)
                        elif logger and clean_line:
                            # Standard streaming log
                            logger.info(f"  [SHELL] {clean_line}")
                        output_lines.append(line)
                
                returncode = process.wait()
                stdout = "".join(output_lines)
                
                if check and returncode != 0:
                    raise subprocess.CalledProcessError(returncode, cmd, output=stdout)
                
                return subprocess.CompletedProcess(cmd, returncode, stdout, "")
            else:
                # Normal mode
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    check=check,
                    shell=shell if shell else (isinstance(cmd, str)),
                    text=True,
                    capture_output=should_capture,
                    env=run_env
                )
                return result
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed with return code {e.returncode}")
            self.logger.error(f"Command: {cmd_str}")
            if hasattr(e, 'stderr') and e.stderr:
                self.logger.error(f"Stderr: {e.stderr.strip()}")
            elif hasattr(e, 'output') and e.output:
                self.logger.error(f"Output: {e.output.strip()}")
            raise e

    def run_java_jar(self, jar_path: Union[str, Path], args: List[str], **kwargs):
        """Helper method specifically for executing java -jar commands"""
        full_jar_path = self.get_binary_path(str(jar_path))
        cmd = ["java", "-jar", str(full_jar_path)] + args
        return self.run(cmd, **kwargs)
