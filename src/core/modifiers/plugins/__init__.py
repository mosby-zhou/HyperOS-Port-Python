"""Built-in modifier plugins.

This module contains plugins for common modification tasks.
"""
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.modifiers.plugin_system import ModifierPlugin, ModifierRegistry
from src.utils.download import AssetDownloader


@ModifierRegistry.register
class WildBoostPlugin(ModifierPlugin):
    """Plugin to install and configure wild_boost performance modules."""
    
    name = "wild_boost"
    description = "Install wild_boost kernel modules and apply device spoofing"
    priority = 10  # Run early
    
    def __init__(self, context, **kwargs):
        super().__init__(context, **kwargs)
        self.downloader = AssetDownloader()
        self.shell = None  # Will be initialized on demand
    
    def check_prerequisites(self) -> bool:
        """Check if wild_boost is enabled in config."""
        return self.get_config("wild_boost", {}).get("enable", False)
    
    def modify(self) -> bool:
        """Execute wild_boost installation."""
        from src.utils.shell import ShellRunner
        self.shell = ShellRunner()
        
        self.logger.info("Wild Boost is enabled...")
        
        # 1. Install kernel modules
        if not self._install_kernel_modules():
            self.logger.error("Failed to install kernel modules")
            return False
        
        # 2. Apply HexPatch to libmigui.so
        hexpatch_success = self._apply_libmigui_hexpatch()
        
        # 3. Fallback: Add persist.sys.feas.enable=true
        if not hexpatch_success:
            self.logger.info("Adding persist.sys.feas.enable=true as fallback...")
            self._add_feas_property()
        
        return True
    
    def _get_kernel_version(self) -> str:
        """
        Detect kernel/KMI version from boot image.
        Prioritizes full KMI string (e.g., android14-5.15) over simple version (5.15).
        """
        boot_img = self.ctx.repack_images_dir / "boot.img"
        if not boot_img.exists():
            return "unknown"
        
        kmi = self._analyze_kmi(boot_img)
        if kmi:
            self.logger.info(f"Detected full KMI version: {kmi}")
            return kmi
        return "unknown"
    
    def _analyze_kmi(self, boot_img: Path) -> str:
        """Analyze kernel image to extract KMI version (e.g., android14-5.15)."""
        from src.utils.shell import ShellRunner
        
        # Ensure shell is initialized
        if self.shell is None:
            self.shell = ShellRunner()
        
        with tempfile.TemporaryDirectory(prefix="ksu_kmi_") as tmp:
            tmp_path = Path(tmp)
            shutil.copy(boot_img, tmp_path / "boot.img")
            
            try:
                self.shell.run([str(self.ctx.tools.magiskboot), "unpack", "boot.img"], cwd=tmp_path)
            except Exception:
                return ""
            
            kernel_file = tmp_path / "kernel"
            if not kernel_file.exists():
                return ""
            
            try:
                with open(kernel_file, 'rb') as f:
                    content = f.read()
                
                # Extract strings from binary
                strings = []
                current = []
                for b in content:
                    if 32 <= b <= 126:
                        current.append(chr(b))
                    else:
                        if len(current) >= 4:
                            strings.append("".join(current))
                        current = []
                
                # Pattern for KMI detection
                # Examples: "5.10.101-android12-9", "5.15.78-android14-11"
                pattern = re.compile(r'(?:^|\s)(\d+\.\d+)\S*(android\d+)')
                for s in strings:
                    if "Linux version" in s or "android" in s:
                        match = pattern.search(s)
                        if match:
                            # Return in standard KMI format: android14-5.15
                            return f"{match.group(2)}-{match.group(1)}"
            except Exception:
                pass
        return ""
    
    def _install_kernel_modules(self, custom_source: Path = None) -> bool:
        """Install wild_boost kernel modules with KMI matching."""
        kmi_version = self._get_kernel_version()
        if kmi_version == "unknown":
            self.logger.error("Cannot detect kernel version, wild_boost modules skipped.")
            return False
        
        # Extract main version (e.g., 5.15) for fallback
        main_version = ""
        version_match = re.search(r'(\d+\.\d+)', kmi_version)
        if version_match:
            main_version = version_match.group(1)
            
        # Determine search paths
        zip_dir = custom_source.parent if custom_source else Path("devices/common")
        base_name = custom_source.stem if custom_source else "wild_boost"
        
        # Multi-level matching strategy
        # 1. Full KMI match (wild_boost_android14-5.15.zip)
        # 2. Main version match (wild_boost_5.15.zip)
        candidates = [
            zip_dir / f"{base_name}_{kmi_version}.zip",
            zip_dir / f"{base_name}_{main_version}.zip"
        ]
        
        matching_zip = None
        for cand in candidates:
            if cand.exists():
                matching_zip = cand
                break
        
        if not matching_zip:
            self.logger.error(f"No matching wild_boost package found for {kmi_version}")
            self.logger.error(f"Searched for: {[c.name for c in candidates]}")
            return False
        
        self.logger.info(f"Using wild_boost package: {matching_zip.name} (match for {kmi_version})")
        
        with tempfile.TemporaryDirectory(prefix="wild_boost_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            try:
                with zipfile.ZipFile(matching_zip, 'r') as z:
                    z.extractall(tmp_path)
            except Exception as e:
                self.logger.error(f"Failed to extract wild_boost zip: {e}")
                return False
            
            ko_files = list(tmp_path.rglob("*.ko"))
            if not ko_files:
                self.logger.error("No kernel modules (*.ko) found in zip.")
                return False
            
            self.logger.info(f"Found {len(ko_files)} modules: {[f.name for f in ko_files]}")
            
            # Auto-detect installation location
            vendor_dlkm_dir = self.ctx.target_dir / "vendor_dlkm"
            
            if any(v in kmi_version for v in ["5.10", "6.12"]):
                return self._install_vendor_boot(ko_files)
            elif vendor_dlkm_dir.exists():
                return self._install_vendor_dlkm(ko_files)
            else:
                self.logger.error("No suitable location (vendor_boot/vendor_dlkm) found.")
                return False

    def _install_vendor_boot(self, ko_files: List[Path]) -> bool:
        """Install wild_boost modules to vendor_boot ramdisk."""
        self.logger.info(f"Installing {len(ko_files)} modules to vendor_boot ramdisk...")
        
        vendor_boot_img = self.ctx.repack_images_dir / "vendor_boot.img"
        if not vendor_boot_img.exists():
            self.logger.error("vendor_boot.img not found.")
            return False
        
        # Create temp directory for unpacking
        work_dir = self.ctx.target_dir.parent / "temp" / "vendor_boot_work"
        if work_dir.exists(): shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vendor_boot_img, work_dir / "vendor_boot.img")
        
        try:
            # Unpack
            self.shell.run([str(self.ctx.tools.magiskboot), "unpack", "vendor_boot.img"], cwd=work_dir)
            ramdisk_cpio = work_dir / "ramdisk.cpio"
            
            # Decompress
            self.shell.run([str(self.ctx.tools.magiskboot), "decompress", "ramdisk.cpio", "ramdisk.cpio.decomp"], cwd=work_dir)
            if (work_dir / "ramdisk.cpio.decomp").exists():
                ramdisk_cpio.unlink()
                (work_dir / "ramdisk.cpio.decomp").rename(ramdisk_cpio)

            # Extract to find paths
            self.shell.run([str(self.ctx.tools.magiskboot), "cpio", "ramdisk.cpio", "extract"], cwd=work_dir)

            # Find modules directory
            modules_load_files = list(work_dir.rglob("modules.load*"))
            if not modules_load_files:
                modules_dir_rel = Path("lib/modules")
            else:
                modules_dir_rel = modules_load_files[0].parent.relative_to(work_dir)
            
            self.logger.info(f"Modules directory in ramdisk: {modules_dir_rel}")

            # 1. Add/Replace modules in CPIO
            for ko_file in ko_files:
                dest_path = modules_dir_rel / ko_file.name
                self.logger.info(f"  Adding/Replacing: {dest_path}")
                self.shell.run([str(self.ctx.tools.magiskboot), "cpio", "ramdisk.cpio", f"add 0644 {dest_path} {ko_file}"], cwd=work_dir)

            # 2. Update modules.load*
            for load_file in modules_load_files:
                load_rel = load_file.relative_to(work_dir)
                content = load_file.read_text(errors='ignore')
                lines = content.splitlines()
                
                modified = False
                for ko_file in ko_files:
                    if ko_file.name not in content:
                        # Append new modules to the end
                        lines.append(ko_file.name)
                        modified = True
                
                if modified:
                    self.logger.info(f"  Updating load file: {load_rel}")
                    load_file.write_text("\n".join(lines) + "\n")
                    self.shell.run([str(self.ctx.tools.magiskboot), "cpio", "ramdisk.cpio", f"add 0644 {load_rel} {load_file}"], cwd=work_dir)

            # 3. Update modules.dep
            dep_file = work_dir / modules_dir_rel / "modules.dep"
            if dep_file.exists():
                self.logger.info("  Updating modules.dep...")
                content = dep_file.read_text(errors='ignore')
                lines = content.splitlines()
                
                # Dynamic dependency line generation for perfmgr.ko
                prefix = f"/{modules_dir_rel}/" if str(modules_dir_rel).startswith("lib") else "lib/modules/"
                
                # Check kernel version for specific dependency chain
                kmi = self._get_kernel_version()
                if "6.12" in kmi: # fixme not working
                    perfmgr_deps = [
                        "qcom-dcvs.ko", "dcvs_fp.ko", "qcom_rpmh.ko", "cmd-db.ko", "crm-v2.ko",
                        "qcom_ipc_logging.ko", "minidump.ko", "smem.ko", "qcom_dma_heaps.ko",
                        "deferred-free-helper.ko", "msm_dma_iommu_mapping.ko", "mem_buf_dev.ko",
                        "gh_mem_notifier.ko", "gh_rm_heap_manager.ko", "mem-prot.ko",
                        "secure_buffer.ko", "qcom-scm.ko", "qcom_tzmem.ko", "gh_rm_drv.ko",
                        "gh_msgq.ko", "gh_dbl.ko", "gh_arm_drv.ko", "debug_symbol.ko"
                    ]
                else: # Default/5.10
                    perfmgr_deps = [
                        "qcom-dcvs.ko", "dcvs_fp.ko", "qcom_rpmh.ko", "cmd-db.ko", "qcom_ipc_logging.ko",
                        "minidump.ko", "smem.ko", "sched-walt.ko", "qcom-cpufreq-hw.ko", "metis.ko",
                        "mi_schedule.ko"
                    ]
                
                perfmgr_dep_line = f"{prefix}perfmgr.ko: " + " ".join([f"{prefix}{d}" for d in perfmgr_deps])
                
                new_lines = []
                perfmgr_found = False
                for line in lines:
                    if "perfmgr.ko:" in line:
                        new_lines.append(perfmgr_dep_line)
                        perfmgr_found = True
                    else:
                        new_lines.append(line)
                
                if not perfmgr_found:
                    new_lines.append(perfmgr_dep_line)
                
                dep_file.write_text("\n".join(new_lines) + "\n")
                self.shell.run([str(self.ctx.tools.magiskboot), "cpio", "ramdisk.cpio", f"add 0644 {dep_file.relative_to(work_dir)} {dep_file}"], cwd=work_dir)

            # 4. Repack
            self.logger.info("Repacking vendor_boot.img...")
            self.shell.run([str(self.ctx.tools.magiskboot), "repack", "vendor_boot.img"], cwd=work_dir)
            
            new_img = work_dir / "new-boot.img"
            if new_img.exists():
                shutil.copy2(new_img, vendor_boot_img)
                self.logger.info("vendor_boot.img updated successfully.")
            else:
                self.logger.error("Failed to repack vendor_boot.img - no output file found.")
                return False
            
            return True
        except Exception as e:
            self.logger.error(f"Error installing to vendor_boot: {e}")
            return False
        finally:
            if work_dir.exists():
                shutil.rmtree(work_dir)

    def _install_vendor_dlkm(self, ko_files: List[Path]) -> bool:
        """Install wild_boost modules to vendor_dlkm."""
        self.logger.info(f"Installing {len(ko_files)} modules to vendor_dlkm...")
        
        target_dir = self.ctx.target_dir / "vendor_dlkm" / "lib" / "modules"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 1. Copy modules
            for ko_file in ko_files:
                dest_ko = target_dir / ko_file.name
                self.logger.info(f"  Copying {ko_file.name} to {dest_ko}")
                shutil.copy2(ko_file, dest_ko)
            
            # 2. Update modules.load
            modules_load = target_dir / "modules.load"
            if modules_load.exists():
                content = modules_load.read_text(encoding='utf-8', errors='ignore')
                lines = content.splitlines()
                modified = False
                for ko_file in ko_files:
                    if ko_file.name not in content:
                        lines.append(ko_file.name)
                        modified = True
                if modified:
                    modules_load.write_text("\n".join(lines) + "\n", encoding='utf-8')
            else:
                modules_load.write_text("\n".join([f.name for f in ko_files]) + "\n", encoding='utf-8')
            
            # 3. Update modules.dep
            modules_dep = target_dir / "modules.dep"
            dep_prefix = "/vendor/lib/modules/"
            if modules_dep.exists():
                content = modules_dep.read_text(encoding='utf-8', errors='ignore')
                lines = content.splitlines()
                
                perfmgr_dep = f"{dep_prefix}perfmgr.ko: {dep_prefix}qcom-dcvs.ko {dep_prefix}dcvs_fp.ko {dep_prefix}qcom_rpmh.ko {dep_prefix}cmd-db.ko {dep_prefix}qcom_ipc_logging.ko {dep_prefix}minidump.ko {dep_prefix}smem.ko {dep_prefix}sched-walt.ko {dep_prefix}qcom-cpufreq-hw.ko {dep_prefix}metis.ko {dep_prefix}mi_schedule.ko"
                
                new_lines = []
                perfmgr_found = False
                for line in lines:
                    if "perfmgr.ko:" in line:
                        new_lines.append(perfmgr_dep)
                        perfmgr_found = True
                    else:
                        new_lines.append(line)
                
                if not perfmgr_found:
                    new_lines.append(perfmgr_dep)
                
                modules_dep.write_text("\n".join(new_lines) + "\n", encoding='utf-8')
            else:
                # If no dep file, at least create the entry for perfmgr
                modules_dep.write_text(f"{dep_prefix}perfmgr.ko:\n", encoding='utf-8')
            
            self.logger.info("wild_boost installation completed for vendor_dlkm.")
            return True
        except Exception as e:
            self.logger.error(f"Error installing to vendor_dlkm: {e}")
            return False
    
    def _apply_libmigui_hexpatch(self) -> bool:
        """Apply HexPatch to libmigui.so for device spoofing."""
        self.logger.info("Applying HexPatch to libmigui.so...")
        
        target_dir = self.ctx.target_dir
        libmigui_files = list(target_dir.rglob("libmigui.so"))
        
        if not libmigui_files:
            self.logger.debug("libmigui.so not found, HexPatch skipped.")
            return False
        
        patches = [
            {
                "old": bytes.fromhex("726F2E70726F647563742E70726F647563742E6E616D65"),
                "new": bytes.fromhex("726F2E70726F647563742E73706F6F6665642E6E616D65")
            },
            {
                "old": bytes.fromhex("726F2E70726F647563742E646576696365"),
                "new": bytes.fromhex("726F2E73706F6F6665642E646576696365")
            }
        ]
        
        patched_count = 0
        for libmigui in libmigui_files:
            try:
                content = libmigui.read_bytes()
                modified = False
                
                for patch in patches:
                    if patch["old"] in content:
                        content = content.replace(patch["old"], patch["new"])
                        modified = True
                
                if modified:
                    libmigui.write_bytes(content)
                    patched_count += 1
            except Exception as e:
                self.logger.error(f"Failed to patch {libmigui}: {e}")
        
        self.logger.info(f"HexPatch applied to {patched_count} libmigui.so file(s).")
        return patched_count > 0
    
    def _add_feas_property(self):
        """Add persist.sys.feas.enable=true to mi_ext/etc/build.prop."""
        prop_file = self.ctx.target_dir / "mi_ext" / "etc" / "build.prop"
        prop_file.parent.mkdir(parents=True, exist_ok=True)
        
        content = ""
        lines = []
        if prop_file.exists():
            content = prop_file.read_text(encoding='utf-8', errors='ignore')
            lines = content.splitlines()
        
        if "persist.sys.feas.enable=true" in content:
            self.logger.info("persist.sys.feas.enable=true already exists.")
            return
        
        lines.append("persist.sys.feas.enable=true")
        prop_file.write_text("\n".join(lines) + "\n", encoding='utf-8')
        self.logger.info("Added persist.sys.feas.enable=true to mi_ext/build.prop")


@ModifierRegistry.register
class EULocalizationPlugin(ModifierPlugin):
    """Plugin to apply EU localization bundle."""
    
    name = "eu_localization"
    description = "Apply EU localization bundle to target ROM"
    priority = 50
    dependencies = ["wild_boost"]  # Run after wild_boost
    
    def check_prerequisites(self) -> bool:
        """Check if EU bundle is available."""
        return (
            getattr(self.ctx, "is_port_eu_rom", False) and 
            getattr(self.ctx, "eu_bundle", None) is not None
        )
    
    def modify(self) -> bool:
        """Apply EU localization."""
        bundle_path = Path(self.ctx.eu_bundle)
        if not bundle_path.exists():
            self.logger.warning(f"EU Bundle not found at {bundle_path}")
            return False
        
        self.logger.info(f"Applying EU Localization Bundle from {bundle_path}...")
        
        with tempfile.TemporaryDirectory(prefix="eu_bundle_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            try:
                with zipfile.ZipFile(bundle_path, 'r') as z:
                    z.extractall(tmp_path)
            except Exception as e:
                self.logger.error(f"Failed to extract EU bundle: {e}")
                return False
            
            # Find and replace EU apps
            self._replace_eu_apps(tmp_path)
            
            # Merge bundle files
            self.logger.info("Merging EU Bundle files into Target ROM...")
            shutil.copytree(tmp_path, self.ctx.target_dir, dirs_exist_ok=True)
        
        return True
    
    def _replace_eu_apps(self, bundle_path: Path):
        """Replace existing apps with EU versions."""
        self.logger.info("Scanning EU bundle for APKs to replace...")
        
        # 1. Identify all unique packages in the bundle
        bundle_packages = {} # pkg_name -> list of paths
        for apk_file in bundle_path.rglob("*.apk"):
            pkg_name = self.ctx.syncer._get_apk_package_name(apk_file)
            if pkg_name:
                if pkg_name not in bundle_packages:
                    bundle_packages[pkg_name] = []
                bundle_packages[pkg_name].append(apk_file)

        self.logger.info(f"Found {len(bundle_packages)} unique package(s) in EU Bundle.")

        # 2. For each unique package, find and remove original app in target ROM
        for pkg_name in bundle_packages:
            # Search for matching app in target ROM (global search)
            # Ensure cache is built by calling find_apks_by_package
            target_apks = self.ctx.syncer.find_apks_by_package(pkg_name, self.ctx.target_dir)
            
            if target_apks:
                self.logger.info(f"Replacing EU App: {pkg_name} ({len(target_apks)} instance(s) found)")
                
                for target_apk in target_apks:
                    if not target_apk.exists():
                        continue
                        
                    app_dir = target_apk.parent
                    self.logger.info(f"  - Found at: {target_apk.relative_to(self.ctx.target_dir)}")
                    
                    # Safety check: avoid deleting root partition dirs (app, priv-app, etc.)
                    protected_dirs = {
                        "app", "priv-app", "system", "product", "system_ext", "vendor",
                        "overlay", "framework", "mi_ext", "odm", "oem"
                    }
                    
                    if app_dir.name not in protected_dirs:
                        self.logger.debug(f"  - Removing directory: {app_dir}")
                        try:
                            shutil.rmtree(app_dir)
                        except Exception as e:
                            self.logger.error(f"  - Failed to remove {app_dir}: {e}")
                    else:
                        self.logger.debug(f"  - Removing single file (protected parent): {target_apk}")
                        target_apk.unlink()
            else:
                self.logger.debug(f"Adding new EU App: {pkg_name} (no match in target)")
    
    # Remove the redundant _get_package_name method as we now use the one in syncer


@ModifierRegistry.register
class FeatureUnlockPlugin(ModifierPlugin):
    """Plugin to unlock device features."""
    
    name = "feature_unlock"
    description = "Unlock device features based on JSON configuration"
    priority = 30
    
    def modify(self) -> bool:
        """Unlock device features."""
        self.logger.info("Unlocking device features...")
        
        config = self._load_config()
        if not config:
            return True
        
        # Check wild_boost dependency
        wild_boost_enabled = self.get_config("wild_boost", {}).get("enable", False)
        
        # Apply XML features
        xml_features = config.get("xml_features", {})
        if not wild_boost_enabled:
            xml_features = {k: v for k, v in xml_features.items() 
                          if not k.startswith("support_wild_boost")}
        
        if xml_features:
            self._apply_xml_features(xml_features)
        
        # Apply build properties
        build_props = config.get("build_props", {})
        if build_props:
            self._apply_build_props(build_props, wild_boost_enabled)
        
        # Apply EU localization props
        if config.get("enable_eu_localization", False) or getattr(self.ctx, "is_port_eu_rom", False):
            self._apply_eu_localization_props()
        
        return True
    
    def _load_config(self) -> Dict:
        """Load feature configuration."""
        config = {}
        
        # Load common config
        common_cfg = Path("devices/common/features.json")
        if common_cfg.exists():
            try:
                with open(common_cfg, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load common features: {e}")
        
        # Load device-specific config
        device_cfg = Path(f"devices/{self.ctx.stock_rom_code}/features.json")
        if device_cfg.exists():
            try:
                with open(device_cfg, 'r') as f:
                    device_config = json.load(f)
                
                # Deep merge
                for key, value in device_config.items():
                    if isinstance(value, dict) and key in config:
                        if key == "build_props" and "product" in value and "product" in config[key]:
                            config[key]["product"].update(value["product"])
                        else:
                            config[key].update(value)
                    else:
                        config[key] = value
            except Exception as e:
                self.logger.error(f"Failed to load device features: {e}")
        
        return config
    
    def _apply_xml_features(self, features: Dict[str, Any]):
        """Apply XML feature flags."""
        feat_dir = self.ctx.target_dir / "product/etc/device_features"
        if not feat_dir.exists():
            return
        
        xml_file = feat_dir / f"{self.ctx.stock_rom_code}.xml"
        if not xml_file.exists():
            try:
                xml_file = next(feat_dir.glob("*.xml"))
            except StopIteration:
                return
        
        content = xml_file.read_text(encoding='utf-8')
        modified = False
        
        for name, value in features.items():
            str_value = str(value).lower()
            pattern = re.compile(rf'<bool name="{re.escape(name)}">.*?</bool>')
            
            if pattern.search(content):
                new_tag = f'<bool name="{name}">{str_value}</bool>'
                new_content = pattern.sub(new_tag, content)
                if new_content != content:
                    content = new_content
                    modified = True
            else:
                if "</features>" in content:
                    new_tag = f'    <bool name="{name}">{str_value}</bool>\n</features>'
                    content = content.replace("</features>", new_tag)
                    modified = True
        
        if modified:
            xml_file.write_text(content, encoding='utf-8')
    
    def _apply_build_props(self, props_map: Dict[str, Dict], wild_boost_enabled: bool):
        """Apply build property modifications."""
        # Filter wild_boost specific props if not enabled
        if not wild_boost_enabled and "product" in props_map:
            product_props = props_map["product"]
            filtered_props = {k: v for k, v in product_props.items()
                            if not k.startswith("ro.product.spoofed")
                            and not k.startswith("ro.spoofed")
                            and not (k.startswith("persist.prophook.com.xiaomi.joyose") 
                                    or k.startswith("persist.prophook.com.miui.powerkeeper"))}
            if filtered_props:
                props_map["product"] = filtered_props
            else:
                del props_map["product"]
        
        # Apply to partitions
        for partition, props in props_map.items():
            prop_file = self.ctx.get_target_prop_file(partition)
            
            if not prop_file or not prop_file.exists():
                self.logger.debug(f"build.prop not found for partition: {partition}")
                continue
            
            self.logger.info(f"Applying build_props to {partition} ({prop_file.relative_to(self.ctx.target_dir)})")
            
            content = prop_file.read_text(encoding='utf-8', errors='ignore')
            lines = content.splitlines()
            
            # Map existing keys to their line index
            prop_indices = {}
            for i, line in enumerate(lines):
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=")[0].strip()
                    prop_indices[key] = i
            
            modified = False
            new_lines = list(lines)
            
            for key, value in props.items():
                new_entry = f"{key}={value}"
                if key in prop_indices:
                    idx = prop_indices[key]
                    if new_lines[idx] != new_entry:
                        self.logger.debug(f"  Updating: {new_lines[idx]} -> {new_entry}")
                        new_lines[idx] = new_entry
                        modified = True
                else:
                    self.logger.debug(f"  Adding: {new_entry}")
                    new_lines.append(new_entry)
                    modified = True
            
            if modified:
                prop_file.write_text("\n".join(new_lines) + "\n", encoding='utf-8')
    
    def _apply_eu_localization_props(self):
        """Apply EU localization properties."""
        self.logger.info("Enabling EU Localization properties...")
        eu_cfg_path = Path("devices/common/eu_localization.json")
        
        if eu_cfg_path.exists():
            try:
                with open(eu_cfg_path, 'r') as f:
                    eu_config = json.load(f)
                eu_props = eu_config.get("build_props", {})
                self._apply_build_props(eu_props, True)
            except Exception as e:
                self.logger.error(f"Failed to apply EU localization props: {e}")


@ModifierRegistry.register
class VNDKFixPlugin(ModifierPlugin):
    """Plugin to fix VNDK APEX and VINTF manifest."""
    
    name = "vndk_fix"
    description = "Fix VNDK APEX and VINTF manifest"
    priority = 40
    
    def modify(self) -> bool:
        """Apply VNDK fixes."""
        self._fix_vndk_apex()
        self._fix_vintf_manifest()
        return True
    
    def _fix_vndk_apex(self):
        """Copy missing VNDK APEX from stock."""
        vndk_version = self.ctx.stock.get_prop("ro.vndk.version")
        
        if not vndk_version:
            for prop in (self.ctx.stock.extracted_dir / "vendor").rglob("*.prop"):
                try:
                    with open(prop, errors='ignore') as f:
                        for line in f:
                            if "ro.vndk.version=" in line:
                                vndk_version = line.split("=")[1].strip()
                                break
                except:
                    pass
                if vndk_version:
                    break
        
        if not vndk_version:
            return
        
        apex_name = f"com.android.vndk.v{vndk_version}.apex"
        stock_apex = self._find_file_recursive(self.ctx.stock.extracted_dir / "system_ext/apex", apex_name)
        target_apex_dir = self.ctx.target_dir / "system_ext/apex"
        
        if stock_apex and target_apex_dir.exists():
            target_file = target_apex_dir / apex_name
            if not target_file.exists():
                self.logger.info(f"Copying missing VNDK Apex: {apex_name}")
                shutil.copy2(stock_apex, target_file)
    
    def _fix_vintf_manifest(self):
        """Fix VINTF manifest for VNDK version."""
        self.logger.info("Checking VINTF manifest for VNDK version...")
        
        vndk_version = self.ctx.stock.get_prop("ro.vndk.version")
        if not vndk_version:
            vendor_prop = self.ctx.target_dir / "vendor/build.prop"
            if vendor_prop.exists():
                try:
                    content = vendor_prop.read_text(encoding='utf-8', errors='ignore')
                    match = re.search(r"ro\.vndk\.version=(.*)", content)
                    if match:
                        vndk_version = match.group(1).strip()
                except:
                    pass
        
        if not vndk_version:
            self.logger.warning("Could not determine VNDK version")
            return
        
        target_xml = self._find_file_recursive(self.ctx.target_dir / "system_ext", "manifest.xml")
        if not target_xml:
            return
        
        original_content = target_xml.read_text(encoding='utf-8')
        
        if f"<version>{vndk_version}</version>" in original_content:
            return
        
        new_block = f"""    <vendor-ndk>
        <version>{vndk_version}</version>
    </vendor-ndk>"""
        
        if "</manifest>" in original_content:
            new_content = original_content.replace("</manifest>", f"{new_block}\n</manifest>")
            target_xml.write_text(new_content, encoding='utf-8')
            self.logger.info(f"Injected VNDK {vndk_version} into manifest")
    
    def _find_file_recursive(self, root_dir: Path, filename: str) -> Optional[Path]:
        if not root_dir.exists():
            return None
        try:
            return next(root_dir.rglob(filename))
        except StopIteration:
            return None


@ModifierRegistry.register
class FileReplacementPlugin(ModifierPlugin):
    """Plugin to handle file/directory replacements from config."""
    
    name = "file_replacement"
    description = "Execute file/directory replacements from replacements.json"
    priority = 20
    
    def __init__(self, context, **kwargs):
        super().__init__(context, **kwargs)
        from src.core.config_merger import ConfigMerger
        from src.core.conditions import ConditionEvaluator
        from src.utils.download import AssetDownloader
        from src.utils.shell import ShellRunner
        
        self.merger = ConfigMerger(self.logger)
        self.evaluator = ConditionEvaluator()
        self.downloader = AssetDownloader()
        self.shell = ShellRunner()
    
    def modify(self) -> bool:
        """Execute file replacements."""
        from src.core.conditions import BuildContext
        
        config = self._load_merged_config("replacements.json")
        replacements = config.get("replacements", [])
        
        if not replacements:
            return True
        
        self.logger.info(f"Processing {len(replacements)} file replacements...")
        
        # Build context for condition evaluation
        build_ctx = BuildContext()
        build_ctx.port_android_version = int(self.ctx.port_android_version)
        build_ctx.base_android_version = int(self.ctx.base_android_version)
        build_ctx.base_device_code = self.ctx.stock_rom_code
        build_ctx.port_os_version_incremental = self.ctx.port.get_prop("ro.mi.os.version.incremental") or ""
        build_ctx.is_port_eu_rom = getattr(self.ctx, "is_port_eu_rom", False)
        
        stock_root = self.ctx.stock.extracted_dir
        target_root = self.ctx.target_dir
        
        for rule in replacements:
            # Evaluate conditions
            passed, reason = self.evaluator.evaluate_with_reason(rule, build_ctx)
            if not passed:
                self.logger.debug(f"Rule '{rule.get('description', 'unnamed')}' skipped: {reason}")
                continue
            
            desc = rule.get("description", "Unknown Rule")
            rtype = rule.get("type", "file")
            self.logger.info(f"Applying replacement rule: {desc}")
            
            try:
                self._handle_rule(rule, rtype, stock_root, target_root)
            except Exception as e:
                self.logger.error(f"Failed to apply rule '{desc}': {e}")
        
        return True
    
    def _load_merged_config(self, filename: str) -> dict:
        """Load and merge configuration from common, chipset and target layers."""
        paths = [
            Path("devices/common"),
            Path(f"devices/{getattr(self.ctx, 'base_chipset_family', 'unknown')}"),
            Path(f"devices/{self.ctx.stock_rom_code}")
        ]
        valid_paths = [p for p in paths if p.exists() and p.is_dir()]
        config, report = self.merger.load_and_merge(valid_paths, filename)
        
        if report.loaded_files:
            self.logger.info(f"Merged {filename} from: {', '.join(report.loaded_files)}")
        return config
    
    def _handle_rule(self, rule: Dict, rtype: str, stock_root: Path, target_root: Path):
        """Handle a single replacement rule based on type."""
        if rtype == "unzip_override":
            self._handle_unzip_override(rule, target_root)
        elif rtype == "wild_boost":
            # Wild boost is handled by its own plugin
            pass
        elif rtype == "copy_file_internal":
            self._handle_copy_file_internal(rule, target_root)
        elif rtype == "remove_files":
            self._handle_remove_files(rule, target_root)
        elif rtype == "hexpatch":
            self._handle_hexpatch(rule, target_root)
        elif rtype == "append_text":
            self._handle_append_text(rule, target_root)
        elif rtype == "copy_local":
            self._handle_copy_local(rule, target_root)
        else:
            self._handle_legacy_replacement(rule, stock_root, target_root)
    
    def _handle_unzip_override(self, rule: Dict, target_root: Path):
        """Handle unzip_override rule type."""
        source_zip = Path(rule["source"])
        if not source_zip.exists():
            self.logger.warning(f"Source zip not found: {source_zip}")
            return
        
        target_dir = target_root
        if "target" in rule:
            target_dir = target_dir / rule["target"]
        
        with zipfile.ZipFile(source_zip, 'r') as z:
            z.extractall(target_dir)
    
    def _handle_copy_file_internal(self, rule: Dict, target_root: Path):
        """Handle copy_file_internal rule type."""
        source = target_root / rule["source"]
        target = target_root / rule["target"]
        
        if not source.exists():
            if rule.get("ensure_exists", False):
                self.logger.warning(f"Internal source not found: {rule['source']}")
            return
        
        target.parent.mkdir(parents=True, exist_ok=True)
        
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
    
    def _handle_remove_files(self, rule: Dict, target_root: Path):
        """Handle remove_files rule type."""
        files = rule.get("files", [])
        search_path = rule.get("search_path", "")
        
        for pattern in files:
            root = target_root / search_path
            for item in root.glob(pattern):
                self.logger.info(f"Removing: {item.relative_to(target_root)}")
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
    
    def _handle_hexpatch(self, rule: Dict, target_root: Path):
        """Handle hexpatch rule type."""
        target_val = rule["target"]
        target_files = []
        
        if "/" in target_val:
            tf = target_root / target_val
            if tf.exists():
                target_files.append(tf)
        else:
            target_files = list(target_root.rglob(target_val))
        
        if not target_files:
            self.logger.warning(f"HexPatch target not found: {target_val}")
            return
        
        for target_file in target_files:
            content = target_file.read_bytes()
            modified = False
            
            for patch in rule.get("patches", []):
                old_bytes = bytes.fromhex(patch["old"])
                new_bytes = bytes.fromhex(patch["new"])
                
                if old_bytes in content:
                    content = content.replace(old_bytes, new_bytes)
                    modified = True
            
            if modified:
                target_file.write_bytes(content)
    
    def _handle_append_text(self, rule: Dict, target_root: Path):
        """Handle append_text rule type."""
        target_file = target_root / rule["target"]
        if not target_file.exists():
            return
        
        text = rule.get("text", "")
        if not text:
            return
        
        content = target_file.read_text(encoding='utf-8', errors='ignore')
        if text not in content:
            with open(target_file, "a", encoding='utf-8') as f:
                f.write(f"\n{text}\n")
    
    def _handle_copy_local(self, rule: Dict, target_root: Path):
        """Handle copy_local rule type."""
        source = Path(rule["source"])
        if not source.exists():
            if not self.downloader.download_if_missing(source):
                return
        
        target_val = rule["target"]
        target_files = []
        
        if "/" in target_val:
            target_files.append(target_root / target_val)
        else:
            target_files = list(target_root.rglob(target_val))
        
        if not target_files:
            return
        
        for target_file in target_files:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            if source.is_dir():
                shutil.copytree(source, target_file, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target_file)
    
    def _handle_legacy_replacement(self, rule: Dict, stock_root: Path, target_root: Path):
        """Handle legacy file replacement rule type."""
        search_path = rule.get("search_path", "")
        match_mode = rule.get("match_mode", "exact")
        ensure_exists = rule.get("ensure_exists", False)
        files = rule.get("files", [])
        
        rule_stock_root = stock_root / search_path
        rule_target_root = target_root / search_path
        
        if not rule_stock_root.exists():
            return
        
        for pattern in files:
            sources = []
            if match_mode == "glob":
                sources = list(rule_stock_root.glob(pattern))
            elif match_mode == "recursive":
                sources = list(rule_stock_root.rglob(pattern))
            else:
                exact_file = rule_stock_root / pattern
                if exact_file.exists():
                    sources = [exact_file]
            
            for src_item in sources:
                rel_name = src_item.name
                target_item = rule_target_root / rel_name
                
                found_in_target = False
                if match_mode == "recursive":
                    candidates = list(rule_target_root.rglob(rel_name))
                    if candidates:
                        target_item = candidates[0]
                        found_in_target = True
                else:
                    if target_item.exists():
                        found_in_target = True
                
                should_copy = found_in_target or ensure_exists
                if should_copy:
                    target_item.parent.mkdir(parents=True, exist_ok=True)
                    
                    if target_item.exists():
                        if target_item.is_dir():
                            shutil.rmtree(target_item)
                        else:
                            target_item.unlink()
                    
                    if src_item.is_dir():
                        shutil.copytree(src_item, target_item, symlinks=True, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_item, target_item)


# Export all plugins
__all__ = [
    'WildBoostPlugin',
    'EULocalizationPlugin', 
    'FeatureUnlockPlugin',
    'VNDKFixPlugin',
    'FileReplacementPlugin',
]
