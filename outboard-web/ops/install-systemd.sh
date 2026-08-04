#!/bin/sh
set -eu

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")/systemd" && pwd)

install -m 0644 "$source_dir"/*.service "$source_dir"/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now outboard-backup.timer outboard-health.timer outboard-restore-check.timer
systemctl list-timers --all --no-pager 'outboard-*'
