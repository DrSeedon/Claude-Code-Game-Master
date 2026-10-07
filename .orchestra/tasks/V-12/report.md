# V-12: удалить локальную копию Balatro

Дата: 2026-10-07

## Результат

Из `/etc/nginx/sites-available/dnd-duckdns` убраны оба location `/balatro`; исходный конфиг сохранён вне `sites-enabled` как `/var/backups/dnd-duckdns-v12-20261007.conf`. `nginx -t` успешен, выполнен `systemctl reload nginx` (без restart). `/var/www/balatro` перемещён командой `sudo trash --verbose`, путь отсутствует. В репозитории изменён только этот отчёт.

Перед удалением активный `nginx -T` показывал единственную ссылку на `/var/www/balatro` в location удаляемого vhost. В активном `photoserver-qr` location `/balatro/` указывает на `/var/www/cog-balatro/current/`. После изменения в выводе активной конфигурации нет ссылок на старый путь, а COG location остался.

Проверка HTTP выполнена сравнением тел. До изменения главный URL отдавал страницу входа; локальный `auto.html` отдавал Balatro. После изменения главный URL и локальный `auto.html` отдают побайтно одинаковую страницу входа (SHA256 `3f4edba6fc1669afbb5b33c6640f0f0a0027f7ef24132131c76968b1445d8e16`). COG `auto.html` до и после имеет одинаковое тело с SHA256 `9e59c3779a2dcfeec39eef2df34491ae2408b94d597459ce9dc504c54749a87e`, заголовок `Balatro — автопрогоны` и HTTP 200.

## Сырые выводы

Команда: `sudo -n nginx -T 2>&1 | rg -n -C 3 "balatro|server_name|sites-enabled"`

```text
291:# configuration file /etc/nginx/sites-enabled/dnd-duckdns:
292-server {
293:    server_name dnd-game-master.duckdns.org;
295:    location = /balatro { return 301 /balatro/; }
296:    location ^~ /balatro/ {
297:        alias /var/www/balatro/current/;
467:# configuration file /etc/nginx/sites-enabled/photoserver-qr:
471:    server_name photo-158-220-127-161.sslip.io;
482:server {
485:    server_name photo-158-220-127-161.sslip.io;
497:    location = /balatro { return 301 /balatro/; }
535:    location ^~ /balatro/ {
537:        alias /var/www/cog-balatro/current/;
```

Команда: `stat -c "%U:%G %a %n" /var/www/balatro /var/www/balatro/current; du -sh /var/www/balatro; command -v trash; trash --version`

```text
root:root 755 /var/www/balatro
root:root 777 /var/www/balatro/current
291M	/var/www/balatro
/usr/bin/trash
0.23.11.10
```

Команда: `sudo -n trash --help 2>&1 | head -35`

```text
usage: trash [OPTION]... FILE...

Put files in trash

positional arguments:
  files

options:
  -h, --help            show this help message and exit
  --print-completion {bash,zsh,tcsh}
                        print shell completion script
  -d, --directory       ignored (for GNU rm compatibility)
  -f, --force           silently ignore nonexistent files
  -i, --interactive     prompt before every removal
  -r, -R, --recursive   ignored for GNU rm compatibility
  --trash-dir TRASHDIR  use TRASHDIR as trash folder
  -v, --verbose         explain what is being done
  --version             show program's version number and exit
```

Команды: сделать бэкап, удалить ровно проверенный блок из `dnd-duckdns`, затем `nginx -t` и `systemctl reload nginx`.

```text
BACKUP: root:root 644 1381 bytes /var/backups/dnd-duckdns-v12-20261007.conf
Removed exact and prefix Balatro locations from /etc/nginx/sites-available/dnd-duckdns
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
active
```

Команда: `sudo -n trash --verbose /var/www/balatro && sudo -n test ! -e /var/www/balatro`

```text
trash: '/var/www/balatro' trashed in ~/.local/share/Trash
VERIFY: /var/www/balatro no longer exists
```

Команды итоговой проверки: `nginx -t`; фильтр `nginx -T` по активным location/alias; поиск `/var/www/balatro` в полном выводе `nginx -T`; проверка отсутствия каталога; `diff -u` бэкапа и текущего файла.

```text
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
-- retained locations --
489:    location = /balatro { return 301 /balatro/; }
527:    location ^~ /balatro/ {
529:        alias /var/www/cog-balatro/current/;
-- old path references --
none
-- target check --
absent
-- config diff --
--- /var/backups/dnd-duckdns-v12-20261007.conf
+++ /etc/nginx/sites-available/dnd-duckdns
@@
-    location = /balatro { return 301 /balatro/; }
-    location ^~ /balatro/ {
-        alias /var/www/balatro/current/;
-        index index.html;
-        autoindex off;
-        add_header Cache-Control "no-cache" always;
-    }
-
-- backup --
root:root 644 1381 bytes /var/backups/dnd-duckdns-v12-20261007.conf
```

До изменения URL тела и HTTP статусы:

```text
SHA256 before:
3f4edba6fc1669afbb5b33c6640f0f0a0027f7ef24132131c76968b1445d8e16  dnd-game-master.duckdns.org/
11e642c22cc43a162579c6ef825e48aa921c861be9413e450324067e1927dd51  dnd-game-master.duckdns.org/balatro/auto.html
9e59c3779a2dcfeec39eef2df34491ce9dc504c54749a87e  photo-158-220-127-161.sslip.io/balatro/auto.html
```

После удаления каталога, финальная проверка тел и HTTP заголовков:

```text
BODY SHA256
3f4edba6fc1669afbb5b33c6640f0f0a0027f7ef24132131c76968b1445d8e16  /tmp/v12-main.body
3f4edba6fc1669afbb5b33c6640f0f0a0027f7ef24132131c76968b1445d8e16  /tmp/v12-final-main.body
11e642c22cc43a162579c6ef825e48aa921c861be9413e450324067e1927dd51  /tmp/v12-local-balatro.body
3f4edba6fc1669afbb5b33c6640f0f0a0027f7ef24132131c76968b1445d8e16  /tmp/v12-final-local.body
9e59c3779a2dcfeec39eef2df34491ae2408b94d597459ce9dc504c54749a87e  /tmp/v12-cog-balatro.body
9e59c3779a2dcfeec39eef2df34491ae2408b94d597459ce9dc504c54749a87e  /tmp/v12-final-cog.body
BODY MARKERS
/tmp/v12-final-main.body:6:<title>DM Game Master — Вход</title>
/tmp/v12-final-main.body:29:  <h1>DM Game Master</h1>
/tmp/v12-final-main.body:32:  <form method="POST" action="/auth/login">
/tmp/v12-final-cog.body:1:...<title>Balatro — автопрогоны</title>...
/tmp/v12-final-cog.body:87:...<h1>Balatro — автопрогоны</h1>...

HTTP/2 200
content-length: 1709

HTTP/2 200
content-length: 1709

HTTP/2 200
content-length: 21397
last-modified: Sat, 19 Sep 2026 14:44:43 GMT
cache-control: no-cache
```

Примечание: первая версия локального Balatro имела `Last-Modified: Tue, 15 Sep 2026 09:44:41 GMT`, что согласуется с проверенным владельцем фактом о замороженной копии.

## Удаление элемента из корзины root

По отдельному поручению удалена только запись с исходным путём `/var/www/balatro`. Перед удалением `trash-rm` был найден как `/usr/bin/trash-rm`; `balatro.trashinfo` подтверждал этот исходный путь, а размер объекта составлял 291M. Команда удаления: `sudo -n trash-rm /var/www/balatro`.

До удаления было 6 элементов в `files/` и 6 в `info/`. После — 5 и 5; `files/balatro` и `info/balatro.trashinfo` отсутствуют. Контрольные отпечатки оставшихся верхнеуровневых элементов совпали до и после в обеих директориях, включая имена, типы, размеры и времена изменения.

Сырые выводы проверки перед удалением:

```text
/usr/bin/trash-rm
-- target metadata --
directory root:root 4096 bytes /root/.local/share/Trash/files/balatro
regular file root:root 68 bytes /root/.local/share/Trash/info/balatro.trashinfo
[Trash Info]
Path=/var/www/balatro
DeletionDate=2026-10-07T16:56:35
-- file item count --
6
-- info item count --
6
-- target size --
291M	/root/.local/share/Trash/files/balatro
```

Сырые выводы удаления и проверки после:

```text
Before: files=6 info=6
Other-entry manifests: files=cdfa3fdb6f0f2b2ebb7f4f334ca2ccff6eed8730b57aac5d9c0fef55220ae8e5 info=593dd2afc2cfd6b13480af4e0131f96753645e9fc99aca200697db90c25bfe1e
After: files=5 info=5
All-entry manifests after: files=cdfa3fdb6f0f2b2ebb7f4f334ca2ccff6eed8730b57aac5d9c0fef55220ae8e5 info=593dd2afc2cfd6b13480af4e0131f96753645e9fc99aca200697db90c25bfe1e
PASS: only the authorized Balatro entry and its trashinfo were removed; all other top-level entries match.
```
