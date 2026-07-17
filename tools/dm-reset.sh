#!/bin/bash
# dm-reset.sh - Reset world state for a fresh campaign start
# Archives current world, then cleans for new beginning

# Source common utilities
source "$(dirname "$0")/common.sh"

echo "🔄 Campaign Reset Tool"
echo "======================"
echo ""

# Show which campaign we're working with
ACTIVE_CAMPAIGN=$(get_active_campaign)
if [ -n "$ACTIVE_CAMPAIGN" ]; then
    echo "Active campaign: $ACTIVE_CAMPAIGN"
    echo "Campaign path: $WORLD_STATE_DIR"
else
    echo "No active campaign set. Use 'dm-campaign.sh list' and 'dm-campaign.sh switch <name>' first."
    exit 1
fi
echo ""

ACTION="${1:-}"

show_usage() {
    echo "Usage: dm-reset.sh <action>"
    echo ""
    echo "Actions:"
    echo "  preview     - Show what would be reset (safe)"
    echo "  archive     - Create a verified tar.gz backup, then reset"
    echo "  hard        - Delete everything and start fresh (destructive!)"
    echo ""
    echo "Examples:"
    echo "  dm-reset.sh preview              # See what exists"
    echo "  dm-reset.sh archive              # Safe reset with backup"
    echo "  dm-reset.sh hard                 # Nuclear option"
    echo ""
    echo "Note: This resets the ACTIVE CAMPAIGN only."
    echo "Use 'dm-campaign.sh switch <name>' to change campaigns first."
}

preview_world() {
    require_active_campaign
    echo "📊 Current World State:"
    echo ""
    $PYTHON_CMD "$LIB_DIR/world_graph.py" stats
    echo ""
    echo "📁 Files that would be reset:"
    echo "  • $WORLD_STATE_DIR/world.json"
    echo "  • $WORLD_STATE_DIR/campaign-overview.json"
    echo "  • $WORLD_STATE_DIR/session-log.md"
}

reset_world() {
    require_active_campaign
    echo "🧹 Resetting world state..."
    echo ""

    $PYTHON_CMD "$LIB_DIR/campaign_manager.py" reset "$ACTIVE_CAMPAIGN" || return 1

    echo ""
    echo "✅ World state reset to blank slate"
}

archive_world() {
    require_active_campaign
    local backup_dir="${DM_BACKUP_DIR:-$PROJECT_ROOT/campaign-backups}"
    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)
    local archive="$backup_dir/${ACTIVE_CAMPAIGN}-${timestamp}.tar.gz"
    local temporary="${archive}.tmp"

    mkdir -p "$backup_dir"
    tar -czf "$temporary" -C "$CAMPAIGNS_DIR" "$ACTIVE_CAMPAIGN" || return 1
    tar -tzf "$temporary" >/dev/null || {
        rm -f "$temporary"
        echo "❌ Backup verification failed"
        return 1
    }
    mv "$temporary" "$archive"
    echo "$archive"
}

case "$ACTION" in
    preview)
        preview_world
        echo ""
        echo "💡 Run 'dm-reset.sh archive' to safely reset with backup"
        ;;

    archive)
        echo "📦 Archiving current campaign..."
        echo ""
        ARCHIVE_PATH=$(archive_world) || {
            echo "❌ Campaign archive failed; reset aborted"
            exit 1
        }
        echo "  ✓ Verified archive: $ARCHIVE_PATH"
        echo ""

        preview_world
        echo ""

        read -p "⚠️  Reset this world? Archive saved to '$ARCHIVE_PATH' (y/N) " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            reset_world
            echo ""
            echo "📜 To restore archived campaign:"
            echo "   tar -xzf \"$ARCHIVE_PATH\" -C \"$CAMPAIGNS_DIR\""
        else
            echo "Reset cancelled. World unchanged."
        fi
        ;;

    hard)
        echo "⚠️  HARD RESET - No backup will be created!"
        echo ""
        preview_world
        echo ""

        read -p "💀 This is DESTRUCTIVE. Type 'DELETE' to confirm: " CONFIRM

        if [ "$CONFIRM" = "DELETE" ]; then
            reset_world
            echo ""
            echo "💀 World obliterated. Starting fresh."
        else
            echo "Reset cancelled. World unchanged."
        fi
        ;;

    *)
        show_usage
        exit 1
        ;;
esac
