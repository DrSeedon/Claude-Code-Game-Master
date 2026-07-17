#!/bin/bash
# dm-migrate-campaigns.sh - Migrate legacy world-state to multi-campaign structure
# This script moves existing world-state files into a campaign folder

set -e

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_CMD="uv run python"
LIB_DIR="$PROJECT_ROOT/lib"
WORLD_STATE="$PROJECT_ROOT/world-state"
CAMPAIGNS_DIR="$WORLD_STATE/campaigns"
ACTIVE_FILE="$WORLD_STATE/active-campaign.txt"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  Campaign Migration Tool${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if already migrated
if [ -f "$ACTIVE_FILE" ]; then
    CURRENT_ACTIVE=$(cat "$ACTIVE_FILE" | tr -d '[:space:]')
    if [ -n "$CURRENT_ACTIVE" ] && [ -d "$CAMPAIGNS_DIR/$CURRENT_ACTIVE" ]; then
        echo -e "${YELLOW}Already migrated!${NC}"
        echo "Active campaign: $CURRENT_ACTIVE"
        echo "Campaign path: $CAMPAIGNS_DIR/$CURRENT_ACTIVE"
        echo ""
        echo "To migrate additional data, manually move files to a campaign folder."
        exit 0
    fi
fi

# Check for existing data
HAS_DATA=false
if [ -f "$WORLD_STATE/npcs.json" ] && [ "$(cat "$WORLD_STATE/npcs.json")" != "{}" ]; then
    HAS_DATA=true
fi
if [ -f "$WORLD_STATE/locations.json" ] && [ "$(cat "$WORLD_STATE/locations.json")" != "{}" ]; then
    HAS_DATA=true
fi

if [ "$HAS_DATA" = false ]; then
    echo -e "${YELLOW}No existing world data found to migrate.${NC}"
    echo "Use 'dm-campaign.sh create <name>' to create a new campaign."
    exit 0
fi

# Try to determine campaign name from existing data
CAMPAIGN_NAME=""

# Check for character in characters/ directory
if [ -d "$WORLD_STATE/characters" ]; then
    CHAR_FILES=$(ls "$WORLD_STATE/characters"/*.json 2>/dev/null | head -1)
    if [ -n "$CHAR_FILES" ]; then
        CAMPAIGN_NAME=$(basename "$CHAR_FILES" .json)
        echo -e "Found character file: ${GREEN}$CAMPAIGN_NAME${NC}"
    fi
fi

# If no character found, ask user
if [ -z "$CAMPAIGN_NAME" ]; then
    echo "No character file found in characters/ directory."
    read -p "Enter campaign folder name (e.g., 'theron', 'dragonlance'): " CAMPAIGN_NAME
fi

if [ -z "$CAMPAIGN_NAME" ]; then
    echo -e "${RED}No campaign name provided. Aborting.${NC}"
    exit 1
fi

# Normalize name
CAMPAIGN_NAME=$(echo "$CAMPAIGN_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
TARGET_DIR="$CAMPAIGNS_DIR/$CAMPAIGN_NAME"

if [ -e "$TARGET_DIR" ]; then
    echo -e "${RED}Campaign already exists: $CAMPAIGN_NAME${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Migration Plan:${NC}"
echo "==============="
echo "Campaign name: $CAMPAIGN_NAME"
echo "Target directory: $TARGET_DIR"
echo ""
echo "Files to migrate:"
[ -f "$WORLD_STATE/campaign-overview.json" ] && echo "  - campaign-overview.json"
[ -f "$WORLD_STATE/npcs.json" ] && echo "  - npcs.json"
[ -f "$WORLD_STATE/locations.json" ] && echo "  - locations.json"
[ -f "$WORLD_STATE/facts.json" ] && echo "  - facts.json"
[ -f "$WORLD_STATE/consequences.json" ] && echo "  - consequences.json"
[ -f "$WORLD_STATE/session-log.md" ] && echo "  - session-log.md"
[ -d "$WORLD_STATE/saves" ] && echo "  - saves/ directory"
[ -f "$WORLD_STATE/characters/$CAMPAIGN_NAME.json" ] && echo "  - characters/$CAMPAIGN_NAME.json -> character.json"
echo ""

read -p "Proceed with migration? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Migration cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}Migrating...${NC}"

# Create and validate the canonical campaign structure.
$PYTHON_CMD "$LIB_DIR/campaign_manager.py" create "$CAMPAIGN_NAME" \
    --campaign-name "$CAMPAIGN_NAME"

# Move core files
for FILE in campaign-overview.json npcs.json locations.json facts.json consequences.json session-log.md; do
    if [ -f "$WORLD_STATE/$FILE" ]; then
        cp "$WORLD_STATE/$FILE" "$TARGET_DIR/$FILE"
        echo "  Copied: $FILE"
    fi
done

# Move saves directory contents
if [ -d "$WORLD_STATE/saves" ] && [ "$(ls -A "$WORLD_STATE/saves" 2>/dev/null)" ]; then
    cp -r "$WORLD_STATE/saves/"* "$TARGET_DIR/saves/" 2>/dev/null || true
    echo "  Copied: saves/"
fi

# Move character file (rename to character.json)
if [ -f "$WORLD_STATE/characters/$CAMPAIGN_NAME.json" ]; then
    cp "$WORLD_STATE/characters/$CAMPAIGN_NAME.json" "$TARGET_DIR/character.json"
    echo "  Copied: characters/$CAMPAIGN_NAME.json -> character.json"
else
    # Check for any character file and use the first one
    FIRST_CHAR=$(ls "$WORLD_STATE/characters"/*.json 2>/dev/null | head -1)
    if [ -n "$FIRST_CHAR" ]; then
        cp "$FIRST_CHAR" "$TARGET_DIR/character.json"
        echo "  Copied: $(basename "$FIRST_CHAR") -> character.json"
    fi
fi

# Set active campaign
echo "$CAMPAIGN_NAME" > "$ACTIVE_FILE"
echo "  Created: active-campaign.txt"

# Convert the copied flat files to the canonical graph and remove only the
# campaign-local staging copies. Root legacy files remain untouched.
$PYTHON_CMD "$LIB_DIR/legacy_migration.py" "$TARGET_DIR" --remove-legacy

echo ""
echo -e "${GREEN}Migration complete!${NC}"
echo ""
echo "Active campaign set to: $CAMPAIGN_NAME"
echo "Campaign directory: $TARGET_DIR"
echo ""
echo "Next steps:"
echo "  1. Verify the migration: dm-campaign.sh info"
echo "  2. Test the tools: dm-overview.sh"
echo "  3. Archive root legacy files before removing them manually"
echo ""
echo -e "${YELLOW}Original root files were copied and remain unchanged.${NC}"
