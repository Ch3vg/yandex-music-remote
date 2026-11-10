# Правила разработки и Git-процесса

В репозитории действует строгий поток слияния веток и обязательная проверка автотестами как локально (перед коммитом и отправкой), так и на стороне GitHub.

## 1. Модель ветвления (`рабочая ветка -> dev -> master`)

1. **`master`** — стабильная релизная ветка:
   - Прямой `push` запрещён (включая администратора репозитория).
   - Слияние разрешено **только через Pull Request из ветки `dev`** (`branch-flow`) и только при успешном прохождении всех автотестов (`autotests`, `pytest-and-web-build`).
2. **`dev`** — основная интеграционная ветка разработки:
   - Прямой `push` запрещён.
   - Все рабочие ветки (`feat/*`, `fix/*`, `refactor/*`, `chore/*`, `docs/*`) вливаются **только в `dev`** через Pull Request при условии прохождения автотестов.
3. **Рабочие ветки** создаются от актуального `dev`:
   ```powershell
   git checkout dev
   git pull origin dev
   git checkout -b feat/my-feature
   ```

## 2. Локальные проверки перед коммитом и push (`.githooks/`)

После клонирования репозитория один раз активируйте локальные Git-хуки:

```powershell
.\scripts\install-hooks.ps1
```

Что проверяется автоматически:
- **`pre-commit`**:
  1. Блокирует случайные прямые коммиты в `master` и `dev`.
  2. Сканирует индексированные файлы (`scripts/check_repo.py --staged`) на утечку токенов (`YANDEX_MUSIC_TOKEN`, `y0_...`, GitHub PAT, приватных ключей), маркеры конфликтов слияния и запрещённые файлы (`.env`, `*.log`, `*.exe`).
  3. При изменениях в `web/` запускает `npm --prefix web run build` (`tsc --noEmit && vite build`) и проверяет, что актуальная сборка `web/dist` добавлена в индекс (`scripts/check_repo.py --verify-dist`).
  4. Запускает полный набор автотестов `pytest`.
- **`pre-push`**:
  1. Блокирует прямой `git push` в `master` и `dev`.
  2. Запускает `pytest` перед отправкой ветки на сервер.

## 3. CI и статус автотестов на коммитах в GitHub

При каждом `push` и `pull_request` запускаются workflow в `.github/workflows/`:

- **`ci.yml` (`Autotests`)**:
  - Сразу при старте публикует на коммит статус **`autotests: pending`** (`pending — выполняются автотесты`).
  - Выполняет сканирование секретов, прогон `pytest`, проверку типов TypeScript, сборку Vite и сверку `web/dist`.
  - По завершении выставляет на коммит итоговый статус **`passed`** (`state: success`) или **`failed`** (`state: failure`), который отображается прямо у каждого коммита и в карточке Pull Request.
- **`branch-flow.yml` (`Branch Flow`)**:
  - Проверяет направление Pull Request: в `master` пропускает PR **только из `dev`**, а рабочие ветки направляет **только в `dev`**.

## 4. Первичная публикация и включение защиты веток на GitHub

Так как прямой `push` в `master` и `dev` запрещён правилами, самая первая отправка в пустой репозиторий выполняется один раз до включения серверных Rulesets:

```powershell
# 1. Подключить локальные Git-хуки
.\scripts\install-hooks.ps1

# 2. Создать первый коммит в master и создать от него ветку dev
git commit -m "Initial release"
git branch dev

# 3. Разово отправить стартовые ветки master и dev в пустой репозиторий GitHub
$env:YM_BOOTSTRAP_PUSH = "1"
git push -u origin master dev
Remove-Item Env:YM_BOOTSTRAP_PUSH

# 4. Включить серверную защиту веток master и dev на GitHub через API
# (нужен Fine-Grained PAT токен с правом Repository permissions -> Administration: Read and write)
$env:GITHUB_TOKEN = "github_pat_..."
.\scripts\setup-github-rules.ps1
Remove-Item Env:GITHUB_TOKEN
```

### Альтернатива: настройка Rulesets вручную в веб-интерфейсе GitHub

Если не хочется создавать токен для скрипта, те же правила можно включить вручную на странице `Settings -> Rules -> Rulesets -> New branch ruleset`:

1. В `Settings -> General`:
   - Default branch: **`master`**
   - Снимите галочку **Automatically delete head branches** (чтобы ветка `dev` не удалялась после слияния `dev -> master`).
2. Создайте два активных Ruleset (**`protect-master`** для `master` и **`protect-dev`** для `dev`), оставив список **Bypass list пустым**:
   - **Restrict deletions** — включено;
   - **Block force pushes** — включено;
   - **Require a pull request before merging** — включено (`Required approvals = 0`, `Dismiss stale pull request approvals when new commits are pushed`, `Require conversation resolution before merging`);
   - **Require status checks to pass** — включено, добавьте проверки:
     - `autotests`
     - `pytest-and-web-build`
     - `branch-flow`
     *(для `protect-master` дополнительно включите `Require branches to be up to date before merging`)*.
