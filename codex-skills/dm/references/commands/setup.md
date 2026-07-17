# /setup - Automatic Installation

Run this command to install DM Codex dependencies. This runs automatically on first launch.

## Steps

1. **Check Python version**
   ```bash
   python3 --version
   ```
   Verify Python 3.11+ is installed. If not, inform the user:
   "Python 3.11+ is required. Install from: https://www.python.org/downloads/"

2. **Create virtual environment if missing**
   ```bash
   [ -d ".venv" ] || python3 -m venv .venv
   ```

3. **Install dependencies (including RAG for document import)**

   Try uv first (faster), fall back to pip. Install with RAG extras for full functionality:
   ```bash
   if command -v uv &> /dev/null; then
       uv pip install -e '.[rag]'
   else
       source .venv/bin/activate && pip install --upgrade pip && pip install -e '.[rag]'
   fi
   ```

   Note: This installs sentence-transformers and chromadb for document import. First run may download ~500MB of model files.

4. **Create .env if missing**
   ```bash
   if [ ! -f ".env" ]; then
       cat > .env << 'EOF'
   # DM Codex Configuration
   DEFAULT_CAMPAIGN_NAME="My Campaign"
   DEFAULT_STARTING_LOCATION="Thornwick"
   EOF
   fi
   ```

5. **Set script permissions**
   ```bash
   chmod +x tools/*.sh tools/*.py lib/*.py
   ```

6. **Verify installation**
   ```bash
   uv run python lib/dice.py "1d20"
   ```

   If the dice roll works, installation is complete.

---

## Welcome Screen

After completing installation, display the welcome screen:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WELCOME TO DM CLAUDE
  Your AI Dungeon Master
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Do you have a D&D book, adventure module, or story
you'd like to bring to life?

  1) Yes, I have a document to import
     → We'll extract NPCs, locations, items, and
       quests from your file (PDF, DOCX, or TXT)

  2) No, create a world from scratch
     → Answer a few questions and we'll generate
       a unique campaign world for you
```

Ask the user directly with these options:
- **Option 1**: "Yes, I have a document" - Explain: Import a PDF, DOCX, or TXT file and extract characters, places, items, and quests automatically
- **Option 2**: "No, create from scratch" - Explain: Answer a few questions about tone, magic level, and setting to generate a unique world

## Routing Based on Choice

### If user chooses "Yes, I have a document":

**First, check the source-material folder for existing files:**
```bash
ls -la source-material/ 2>/dev/null | grep -E '\.(pdf|docx|txt|md)$'
```

If files are found, display them:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IMPORT YOUR ADVENTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Found documents in source-material/:

  1) [filename.pdf]
  2) [filename2.docx]
  ...

  Or: Drag/drop a different file, or paste a path

Supported formats: PDF, DOCX, TXT, MD
```

Ask the user directly with these options:.

If no files in source-material/, display:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IMPORT YOUR ADVENTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Drag and drop your file here, or paste the file path.
(Tip: You can also place files in source-material/)

Supported formats: PDF, DOCX, TXT, MD
```

Then ask for:
1. **File path**: The path to their document (or selection from source-material)
2. **Campaign name**: What to call this campaign (optional, defaults to filename)

Once you have both, run `/import "<file-path>" "<campaign-name>"` to start the import workflow.

### If user chooses "No, create from scratch":
Run `/new-game` to start the world creation workflow.

---

## Returning Players

If campaigns already exist (check with `bash tools/dm-campaign.sh list`), skip the welcome screen and instead:

1. Show existing campaigns
2. Ask if they want to:
   - Continue an existing campaign → `/dm`
   - Create a new campaign → Show welcome screen above
