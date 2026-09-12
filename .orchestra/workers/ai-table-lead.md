# AI-table lead memory

- For an unattended `gh auth login --web` device flow, do not put interactive `script` behind `/dev/null` stdin: it stalls at `Press Enter` after showing the code. Arrange the initial newline in the persistent job itself so the same client proceeds to poll and collect the owner's authorization.
