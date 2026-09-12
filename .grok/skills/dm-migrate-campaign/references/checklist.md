# Half-graph migrate checklist (printable)

- [ ] Backup tree under `world-state/backups/<name>-pre-migrate-<TS>`
- [ ] Save via `dm-session.sh save pre-migrate-…`
- [ ] Classified: flat vs half-graph vs surgical
- [ ] Dry-run migrator / plan reviewed
- [ ] money set
- [ ] player inventory embedded
- [ ] party inventories embedded
- [ ] weapon nodes + ammo_type match stackables
- [ ] armor nodes + equipment
- [ ] abilities/stats for firearms
- [ ] creature templates
- [ ] party `at` == current location
- [ ] overview play_mode / currency / time
- [ ] firearms fire_modes modern
- [ ] legacy inv archived
- [ ] Smoke: player, inventory, party, location, skill roll, combat --test
- [ ] Post-mortem note if new failure mode
