#!/usr/bin/env python3
"""Fstab parser for detecting and removing encryption options."""

import re
import shutil
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import List, Optional, Tuple


# Encryption patterns to detect and remove from fstab entries
ENCRYPTION_PATTERNS = [
    r"fileencryption=[^\s,]*",
    r"forceencrypt=[^\s,]*",
    r"encryptable[^\s,]*",
]


@dataclass
class EncryptionOptions:
    """Represents encryption options found and removed from a fstab line.

    Attributes:
        fstab_path: Path to the fstab file containing this line
        original_line: The original line before modification
        modified_line: The line after removing encryption options
        removed_options: List of encryption options that were removed
    """

    fstab_path: Path
    original_line: str
    modified_line: str
    removed_options: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Return True if the line was modified (original != modified)."""
        return self.original_line != self.modified_line


class FstabParser:
    """Parser for Android fstab files to detect and remove encryption options.

    This class finds fstab files in a vendor directory, parses them to find
    encryption-related mount options, and can modify them to disable encryption.
    """

    def __init__(self, vendor_dir: Path, logger: Optional[Logger] = None):
        """Initialize the fstab parser.

        Args:
            vendor_dir: Path to the vendor directory containing etc/fstab files
            logger: Optional logger for output messages
        """
        self.vendor_dir = Path(vendor_dir)
        self.logger = logger
        self._fstab_files: List[Path] = []
        self._modifications: List[EncryptionOptions] = []

    def find_fstab_files(self) -> List[Path]:
        """Find fstab files in the vendor directory.

        Looks in vendor_dir/etc/ for common fstab names and also globs for
        fstab.* patterns.

        Returns:
            Sorted list of unique Path objects for fstab files found
        """
        etc_dir = self.vendor_dir / "etc"

        if not etc_dir.exists():
            if self.logger:
                self.logger.debug(f"etc directory not found: {etc_dir}")
            return []

        fstab_files: set[Path] = set()

        # Common fstab file names
        common_names = ["fstab.qcom", "fstab.postinstall", "fstab.ranchu"]
        for name in common_names:
            fstab_path = etc_dir / name
            if fstab_path.exists() and fstab_path.is_file():
                fstab_files.add(fstab_path)

        # Also glob for fstab.* patterns
        for fstab_path in etc_dir.glob("fstab.*"):
            if fstab_path.is_file():
                fstab_files.add(fstab_path)

        # Return sorted list
        return sorted(fstab_files)

    def parse_line(self, line: str) -> Tuple[str, List[str]]:
        """Parse a single fstab line and remove encryption options.

        Args:
            line: A single line from an fstab file

        Returns:
            Tuple of (modified_line, removed_options)
        """
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            return (line, [])

        removed_options: List[str] = []
        modified_line = line

        # Apply each encryption pattern
        for pattern in ENCRYPTION_PATTERNS:
            matches = re.findall(pattern, modified_line)
            removed_options.extend(matches)
            modified_line = re.sub(pattern, "", modified_line)

        # Clean up extra commas and spaces
        # Replace multiple consecutive commas with single comma
        modified_line = re.sub(r",+", ",", modified_line)
        # Remove leading/trailing commas in options field (4th field)
        parts = modified_line.split()
        if len(parts) >= 4:
            parts[3] = parts[3].strip(",")
            # If options field becomes empty, use "defaults"
            if not parts[3]:
                parts[3] = "defaults"
            modified_line = " ".join(parts)

        return (modified_line, removed_options)

    def analyze_fstab(self, fstab_path: Path) -> List[EncryptionOptions]:
        """Analyze a single fstab file for encryption options.

        Args:
            fstab_path: Path to the fstab file to analyze

        Returns:
            List of EncryptionOptions for lines where encryption options were found
        """
        if not fstab_path.exists():
            if self.logger:
                self.logger.warning(f"fstab file not found: {fstab_path}")
            return []

        modifications: List[EncryptionOptions] = []

        try:
            with open(fstab_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (IOError, OSError) as e:
            if self.logger:
                self.logger.error(f"Error reading {fstab_path}: {e}")
            return []

        for line in lines:
            modified_line, removed_options = self.parse_line(line)

            if removed_options:
                mod = EncryptionOptions(
                    fstab_path=fstab_path,
                    original_line=line.rstrip("\n"),
                    modified_line=modified_line.rstrip("\n"),
                    removed_options=removed_options,
                )
                modifications.append(mod)

        return modifications

    def analyze_all(self) -> List[EncryptionOptions]:
        """Analyze all fstab files in the vendor directory.

        Calls find_fstab_files() if not already done, then analyzes each file.

        Returns:
            List of all EncryptionOptions found across all fstab files
        """
        if not self._fstab_files:
            self._fstab_files = self.find_fstab_files()

        self._modifications = []

        for fstab_path in self._fstab_files:
            mods = self.analyze_fstab(fstab_path)
            self._modifications.extend(mods)

        return self._modifications

    def backup_fstab(self, fstab_path: Path) -> Optional[Path]:
        """Create a backup of the fstab file.

        Args:
            fstab_path: Path to the fstab file to backup

        Returns:
            Path to the backup file, or None if backup failed
        """
        backup_path = fstab_path.with_suffix(fstab_path.suffix + ".bak")

        try:
            shutil.copy2(fstab_path, backup_path)
            if self.logger:
                self.logger.debug(f"Created backup: {backup_path}")
            return backup_path
        except (IOError, OSError) as e:
            if self.logger:
                self.logger.error(f"Failed to create backup {backup_path}: {e}")
            return None

    def apply_modifications(self, dry_run: bool = False) -> int:
        """Apply modifications to fstab files.

        Args:
            dry_run: If True, print what would change without modifying files

        Returns:
            Count of files that were (or would be) modified
        """
        if not self._modifications:
            if self.logger:
                self.logger.info("No modifications to apply")
            return 0

        # Group modifications by file
        mods_by_file: dict[Path, List[EncryptionOptions]] = {}
        for mod in self._modifications:
            if mod.fstab_path not in mods_by_file:
                mods_by_file[mod.fstab_path] = []
            mods_by_file[mod.fstab_path].append(mod)

        modified_count = 0

        for fstab_path, mods in mods_by_file.items():
            if dry_run:
                if self.logger:
                    self.logger.info(f"\nWould modify: {fstab_path}")
                    for mod in mods:
                        self.logger.info(f"  - Original: {mod.original_line}")
                        self.logger.info(f"    Modified: {mod.modified_line}")
                        self.logger.info(f"    Removed:  {', '.join(mod.removed_options)}")
                modified_count += 1
            else:
                # Create backup
                backup_path = self.backup_fstab(fstab_path)
                if backup_path is None:
                    if self.logger:
                        self.logger.error(f"Skipping {fstab_path} due to backup failure")
                    continue

                # Read original file
                try:
                    with open(fstab_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except (IOError, OSError) as e:
                    if self.logger:
                        self.logger.error(f"Failed to read {fstab_path}: {e}")
                    continue

                # Build mapping of original lines to modified lines
                line_map: dict[str, str] = {}
                for mod in mods:
                    line_map[mod.original_line] = mod.modified_line

                # Apply modifications
                new_lines: List[str] = []
                for line in lines:
                    stripped = line.rstrip("\n")
                    if stripped in line_map:
                        new_lines.append(line_map[stripped] + "\n")
                    else:
                        new_lines.append(line)

                # Write back
                try:
                    with open(fstab_path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
                    if self.logger:
                        self.logger.info(f"Modified: {fstab_path}")
                    modified_count += 1
                except (IOError, OSError) as e:
                    if self.logger:
                        self.logger.error(f"Failed to write {fstab_path}: {e}")

        return modified_count

    @property
    def modifications(self) -> List[EncryptionOptions]:
        """Return the list of modifications found."""
        return self._modifications
