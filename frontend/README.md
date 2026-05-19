# 503Work — Labor Market Analytics UI

React + Vite фронтенд для аналітичної системи ринку IT-вакансій (TRPZ). Дані надаються FastAPI-бекендом, що описаний у [../README.md](../README.md) та [../REACT_DEV_GUIDE.md](../REACT_DEV_GUIDE.md).

## Передумови

- Node.js 18+ (рекомендовано 20+)
- Запущений API на `http://localhost:8000` (`docker compose up db api -d` у корені проєкту)

## Запуск

```bash
cd frontend
cp .env.example .env       # опційно — за замовчуванням використовується http://localhost:8000
npm install
npm run dev                # http://localhost:5173
```

Якщо ваш бекенд не на `localhost:8000`:

```bash
echo "VITE_API_BASE_URL=http://my-host:8000" > .env
```

> Перевірте, що CORS бекенду містить порт Vite. Додайте у `.env` бекенду:
> ```
> CORS_ORIGINS=http://localhost:5173
> ```
> та перезапустіть API: `docker compose restart api`.

## Скрипти

| Команда           | Опис                                       |
|-------------------|--------------------------------------------|
| `npm run dev`     | Dev-сервер з HMR на 5173                   |
| `npm run build`   | Type-check + production build у `dist/`    |
| `npm run preview` | Локальний preview зібраного бандлу         |
| `npm run lint`    | ESLint                                     |

## Стек

- React 19 + TypeScript + Vite
- Tailwind CSS 3 (dark mode через клас `dark` на `html`)
- React Router v6
- @tanstack/react-query
- recharts

## Структура

```
src/
├── api/
│   ├── client.ts        # fetch-обгортка з API_BASE_URL та ApiError
│   ├── hooks.ts         # React Query хуки на всі endpoints
│   └── types.ts         # типи відповідей API
├── components/
│   ├── charts/          # SnapshotChart, TopSkillsChart, SalaryHistogram, …
│   ├── Card.tsx, KpiCard.tsx, States.tsx, …
│   └── Sidebar.tsx, Topbar.tsx, ThemeToggle.tsx
├── lib/
│   ├── format.ts        # formatNumber, formatUSD, formatSalaryRange
│   └── theme.ts         # useTheme — перемикач світла/темна
├── pages/
│   ├── DashboardPage.tsx
│   ├── VacanciesPage.tsx
│   ├── SkillsPage.tsx
│   ├── SalaryPage.tsx
│   └── GeographyPage.tsx
├── App.tsx              # роутинг + layout
├── main.tsx             # QueryClient + Router + StrictMode
└── index.css            # Tailwind + theme tokens
```

## Сторінки

- **/** — Дашборд: KPI-картки, динаміка ринку (7/30/90 днів), розподіл зарплат, топ навичок, топ міст
- **/vacancies** — таблиця вакансій з фільтрами (навичка, місто, мін. ЗП, досвід) і пагінацією
- **/skills** — топ навичок (попит/пропозиція, Hard/Soft) + gap-аналіз
- **/salary** — розподіл зарплат у USD для вакансій vs резюме + деталізація
- **/geography** — географія активності по містах України

## Тема

Перемикач світла/темна у топбарі. Зберігається у `localStorage` під ключем `503work.theme`. Перший рендер бере значення з системних налаштувань, якщо вибір ще не зроблено. Колірні токени — у CSS-змінних в [src/index.css](src/index.css).
