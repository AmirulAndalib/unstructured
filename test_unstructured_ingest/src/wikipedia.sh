#!/usr/bin/env bash

set -e

SRC_PATH=$(dirname "$(realpath "$0")")
SCRIPT_DIR=$(dirname "$SRC_PATH")
cd "$SCRIPT_DIR"/.. || exit 1
OUTPUT_FOLDER_NAME=wikipedia
OUTPUT_ROOT=${OUTPUT_ROOT:-$SCRIPT_DIR}
OUTPUT_DIR=$OUTPUT_ROOT/structured-output/$OUTPUT_FOLDER_NAME
WORK_DIR=$OUTPUT_ROOT/workdir/$OUTPUT_FOLDER_NAME
DOWNLOAD_DIR=$SCRIPT_DIR/download/$OUTPUT_FOLDER_NAME
max_processes=${MAX_PROCESSES:=$(python3 -c "import os; print(os.cpu_count())")}
CI=${CI:-"false"}

# shellcheck disable=SC1091
source "$SCRIPT_DIR"/cleanup.sh
function cleanup() {
  cleanup_dir "$OUTPUT_DIR"
  cleanup_dir "$WORK_DIR"
  if [ "$CI" == "true" ]; then
    cleanup_dir "$DOWNLOAD_DIR"
  fi
}
trap cleanup EXIT

RUN_SCRIPT=${RUN_SCRIPT:-unstructured-ingest}
PYTHONPATH=${PYTHONPATH:-.} "$RUN_SCRIPT" \
  wikipedia \
  --download-dir "$DOWNLOAD_DIR" \
  --metadata-exclude coordinates,filename,file_directory,metadata.last_modified,metadata.detection_class_prob,metadata.parent_id,metadata.category_depth \
  --num-processes "$max_processes" \
  --strategy hi_res \
  --preserve-downloads \
  --verbose \
  --page-title "Open Source Software" \
  --work-dir "$WORK_DIR" \
  local \
  --output-dir "$OUTPUT_DIR"

"$SCRIPT_DIR"/check-num-files-output.sh 3 $OUTPUT_FOLDER_NAME
