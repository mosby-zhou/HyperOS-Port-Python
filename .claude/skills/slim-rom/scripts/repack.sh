#!/bin/bash
# ROM 精简打包脚本
# 用法: ./repack.sh <rom_name> [product_size]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
BUILD_DIR="$PROJECT_ROOT/build/target"
OUT_DIR="$PROJECT_ROOT/out"

# 参数
ROM_NAME="${1:-thor-slim}"
PRODUCT_SIZE="${2:-}"  # 可选，如果不提供则自动计算

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查必要目录
check_dirs() {
    if [ ! -d "$BUILD_DIR/product/product_a" ]; then
        log_error "product 分区未解包，请先执行 Phase 1 解包"
        exit 1
    fi
}

# 获取镜像大小
get_img_size() {
    local img="$1"
    if [ -f "$img" ]; then
        stat -c%s "$img"
    else
        echo "0"
    fi
}

# 打包单个分区
pack_partition() {
    local part_name="$1"
    local src_dir="$2"
    local config_dir="$3"

    log_info "打包 $part_name 分区..."

    local fs_config="$config_dir/${part_name}_fs_config"
    local file_contexts="$config_dir/${part_name}_file_contexts"

    if [ ! -f "$fs_config" ] || [ ! -f "$file_contexts" ]; then
        log_error "配置文件不存在: $fs_config 或 $file_contexts"
        return 1
    fi

    "$PROJECT_ROOT/bin/linux/x86_64/mkfs.erofs" \
        -zlz4hc,9 \
        -T 1230768000 \
        --mount-point "/$part_name" \
        --fs-config-file "$fs_config" \
        --file-contexts "$file_contexts" \
        "$BUILD_DIR/${part_name}_new.img" \
        "$src_dir"

    # 替换原镜像
    mv "$BUILD_DIR/${part_name}_new.img" "$BUILD_DIR/${part_name}.img"
    log_info "$part_name 打包完成: $(ls -lh "$BUILD_DIR/${part_name}.img" | awk '{print $5}')"
}

# 生成 super.img
make_super() {
    log_info "生成 super.img..."

    # 获取各分区大小
    local product_size=$(get_img_size "$BUILD_DIR/product_a.img")
    local system_size=$(get_img_size "$BUILD_DIR/system_a.img")
    local vendor_size=$(get_img_size "$BUILD_DIR/vendor_a.img")
    local system_ext_size=$(get_img_size "$BUILD_DIR/system_ext_a.img")
    local odm_size=$(get_img_size "$BUILD_DIR/odm_a.img")
    local vendor_dlkm_size=$(get_img_size "$BUILD_DIR/vendor_dlkm_a.img")
    local mi_ext_size=$(get_img_size "$BUILD_DIR/mi_ext_a.img")

    # super 分区总大小 (9126805504 = 约 8.5GB)
    local super_size=9126805504

    "$PROJECT_ROOT/otatools/bin/lpmake" \
        --metadata-size 65536 \
        --super-name super \
        --block-size 4096 \
        --device super:$super_size \
        --metadata-slots 2 \
        --group qti_dynamic_partitions:$super_size \
        --partition odm_a:readonly:$odm_size:qti_dynamic_partitions \
        --image odm_a="$BUILD_DIR/odm_a.img" \
        --partition odm_b:readonly:0:qti_dynamic_partitions \
        --partition product_a:readonly:$product_size:qti_dynamic_partitions \
        --image product_a="$BUILD_DIR/product_a.img" \
        --partition product_b:readonly:0:qti_dynamic_partitions \
        --partition system_a:readonly:$system_size:qti_dynamic_partitions \
        --image system_a="$BUILD_DIR/system_a.img" \
        --partition system_b:readonly:0:qti_dynamic_partitions \
        --partition system_ext_a:readonly:$system_ext_size:qti_dynamic_partitions \
        --image system_ext_a="$BUILD_DIR/system_ext_a.img" \
        --partition system_ext_b:readonly:0:qti_dynamic_partitions \
        --partition vendor_a:readonly:$vendor_size:qti_dynamic_partitions \
        --image vendor_a="$BUILD_DIR/vendor_a.img" \
        --partition vendor_b:readonly:0:qti_dynamic_partitions \
        --partition vendor_dlkm_a:readonly:$vendor_dlkm_size:qti_dynamic_partitions \
        --image vendor_dlkm_a="$BUILD_DIR/vendor_dlkm_a.img" \
        --partition vendor_dlkm_b:readonly:0:qti_dynamic_partitions \
        --partition mi_ext_a:readonly:$mi_ext_size:qti_dynamic_partitions \
        --image mi_ext_a="$BUILD_DIR/mi_ext_a.img" \
        --partition mi_ext_b:readonly:0:qti_dynamic_partitions \
        --output "$BUILD_DIR/super_raw.img"

    # 转换为 sparse 格式
    log_info "转换为 sparse 格式..."
    "$PROJECT_ROOT/otatools/bin/img2simg" "$BUILD_DIR/super_raw.img" "$BUILD_DIR/super.img"

    log_info "super.img 生成完成: $(ls -lh "$BUILD_DIR/super.img" | awk '{print $5}')"
}

# 复制输出文件
copy_output() {
    local timestamp=$(date +%Y%m%d)
    local output_dir="$OUT_DIR/${ROM_NAME}-${timestamp}"

    log_info "复制输出文件到 $output_dir..."

    mkdir -p "$output_dir"

    # 复制 super.img
    cp "$BUILD_DIR/super.img" "$output_dir/"

    # 复制固件文件
    local images_dir="$BUILD_DIR/repack_images"
    if [ -d "$images_dir" ]; then
        # 查找原始 ROM 目录
        for rom_dir in "$PROJECT_ROOT/roms"/*/images; do
            if [ -d "$rom_dir" ]; then
                cp "$rom_dir"/boot.img "$output_dir/" 2>/dev/null || true
                cp "$rom_dir"/vendor_boot.img "$output_dir/" 2>/dev/null || true
                cp "$rom_dir"/dtbo.img "$output_dir/" 2>/dev/null || true
                cp "$rom_dir"/vbmeta*.img "$output_dir/" 2>/dev/null || true
                cp "$rom_dir"/recovery.img "$output_dir/" 2>/dev/null || true
                cp "$rom_dir"/cust.img "$output_dir/" 2>/dev/null || true
                cp "$rom_dir"/*.mbn "$output_dir/" 2>/dev/null || true
                cp "$rom_dir"/*.elf "$output_dir/" 2>/dev/null || true
                cp "$rom_dir"/*.bin "$output_dir/" 2>/dev/null || true
                cp "$rom_dir"/rawprogram*.xml "$output_dir/" 2>/dev/null || true
                break
            fi
        done
    fi

    log_info "输出文件列表:"
    ls -lh "$output_dir/"

    log_info "总大小: $(du -sh "$output_dir" | cut -f1)"
}

# 主流程
main() {
    log_info "开始打包流程..."
    log_info "项目目录: $PROJECT_ROOT"
    log_info "构建目录: $BUILD_DIR"

    check_dirs

    # 只打包 product 分区（其他分区未修改）
    pack_partition "product_a" "$BUILD_DIR/product/product_a" "$BUILD_DIR/product/config"

    # 生成 super.img
    make_super

    # 复制输出文件
    copy_output

    log_info "打包完成！"
}

main "$@"
