# Аудит миграции Claude Code -> Codex

Дата проверки: 2026-07-13.

## Итог

- В `~/.agents/skills` установлено 17 адаптированных skills.
- В Codex глобально включены MCP: `kwin`, `orchestra`, `openaiDeveloperDocs`.
- Для этого проекта включен кастомный `websearch` с Perplexity Sonar и генерацией изображений через OpenRouter.
- Глобальные правила Codex находятся в `~/.codex/AGENTS.md` и написаны по-русски.
- Новая Codex-сессия нужна, чтобы перечитать глобальные инструкции, список skills и новый `kwin` MCP.

Codex ищет личные skills в `$HOME/.agents/skills`; каждый skill должен содержать `SKILL.md` с `name` и `description`. Источник: https://developers.openai.com/codex/skills

## Установленные skills

Почти прямой перенос:

- `humanizer`
- `review`
- `fact-checker`
- `frontend-design`
- `seo-audit`
- `page-cro`
- `accounting`
- `doc-coauthoring`
- `starsector-modding`

Перенос с адаптацией:

- `computer-use`: добавлен корректный frontmatter, зависимость от MCP `kwin` и проверка доступности сервера.
- `webapp-testing`: оставлены Playwright-скрипты и примеры; MCP не обязателен.
- `unity-mcp-orchestrator`: пути и инструкции адаптированы, но Unity MCP остается проектным сервером.
- `reddit-reader`: убран жестко заданный порт прокси, используются `HTTPS_PROXY`/`HTTP_PROXY`; скрипт адаптирован под `~/.agents/skills`.
- `youtube-reader`: убран жестко заданный порт, добавлен штатный web-first сценарий и прокси через environment.
- `habr-publish`: удален Claude-специфичный frontmatter.
- `orchestra`: термины и sender заменены на Codex, MCP предпочитается HTTP fallback.
- `task-observer`: создан короткий Codex-workflow; полная исходная Cowork-методика сохранена в `references/` и не исполняется буквально.

Все 17 каталогов прошли `quick_validate.py`. Python-файлы `reddit-reader` и `webapp-testing` прошли `py_compile` и CLI smoke test.

## MCP Codex

| Сервер | Состояние | Назначение |
|---|---|---|
| `kwin` | enabled | KDE Plasma/Wayland computer use |
| `orchestra` | enabled | локальная Orchestra |
| `openaiDeveloperDocs` | enabled | официальная документация OpenAI |
| `websearch` | enabled в проекте | Perplexity Sonar и генерация/редактирование изображений через OpenRouter |

`kwin` добавлен в ходе миграции. Его инструменты появятся после запуска новой Codex-сессии.

`serena` была удалена из Codex по решению пользователя: её функции для этого
проекта перекрываются обычным поиском, чтением файлов и встроенными
subagents. `orchestra` остаётся отдельным внешним оркестратором и загружается
только для соответствующего workflow.

Проектный `websearch` публикует только два инструмента: `search` и `generate_image`. API-ключ не скопирован в репозиторий; запускатель читает уже настроенное значение из пользовательской Claude-конфигурации.

## MCP Claude

Фактический вывод `claude mcp list` в этом проекте:

| Сервер | Состояние при проверке | Решение |
|---|---|---|
| `websearch` | ошибка подключения | Не переносить вслепую. В Codex уже есть штатный web; локальный сервер сначала чинить отдельно. |
| `mcp-pandoc` | ошибка подключения | Оставить кандидатом. Добавлять после проверки запуска `uvx mcp-pandoc`. |
| `aperant` | ожидает одобрения | Проектный сервер Aperant, глобально Codex не нужен. |

Дополнительно в `~/.claude/settings.json` лежат записи `kwin` и `orchestra`, но текущий Claude CLI не показал их как активные. В Codex оба теперь настроены штатно через `~/.codex/config.toml`.

## Проектные и запасные MCP

- `UnityMCP`: настроен для Unity-проекта `POLUS` через `uvx mcp-for-unity`. Для другого Unity-проекта сервер следует добавлять в его контексте, а не глобально.
- `chroma`: настроен только для `AISwapFace`; не переносить глобально из-за привязки к конкретной базе.
- `playwright`: имеется Claude-сниппет. Для текущего `webapp-testing` не требуется, но можно добавить в Codex отдельно, если нужен интерактивный браузерный MCP.
- `context7`: имеется сниппет, но для OpenAI и библиотек лучше сначала использовать официальные docs/MCP источники.
- `github` и `github-actions`: имеются сниппеты, требуют GitHub token. Добавлять только при реальной необходимости.
- `figma-context`: имеется сниппет, требует Figma token.
- `yougile`: локальный сервер и сниппет с несколькими учетными переменными; добавлять только для задач YouGile.
- `gmail-mcp`, `mailru-mcp`, `figma-mcp-go`: код серверов присутствует локально, активной глобальной конфигурации не найдено.
- `serena-disabled`: старый Claude-сниппет не используется; Serena в Codex
  удалена.

## Безопасность

В `~/.claude/mcp-configs/figma-context.json` найден API-токен, записанный прямо в аргументах команды. Его следует отозвать/перевыпустить и передавать через переменную окружения. Значение токена в этот отчет не скопировано.

Также не следует переносить в глобальные skills или MCP-конфиги содержимое `.env`, OAuth credentials, банковские реквизиты и персональные данные. `accounting` содержит приватный справочник в `references/`; skill прямо запрещает раскрывать его вне соответствующей бухгалтерской задачи.

## Что делать дальше

1. Перезапустить Codex и проверить `/skills`, `$computer-use` и доступность инструментов `kwin`.
2. Проверить Unity skill внутри конкретного Unity-проекта с запущенным Editor и его проектным Unity MCP.
3. Перевыпустить Figma token.
4. Не добавлять остальные MCP массово: сначала исправить два неработающих Claude-сервера и включать проектные интеграции только по необходимости.
