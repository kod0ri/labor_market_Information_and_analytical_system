/**
 * Легка i18n без зовнішніх залежностей: два словники (uk/en), контекст і хук.
 * Мова зберігається в localStorage і виставляється на <html lang="…">.
 * Ключі типізовані від українського словника — пропущений переклад в en
 * ловиться на етапі компіляції.
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

export type Lang = 'uk' | 'en'

const STORAGE_KEY = '503work.lang'

const uk = {
  'nav.dashboard': 'Дашборд',
  'nav.skills': 'Навички',
  'nav.salary': 'Зарплати',
  'nav.geography': 'Географія',
  'nav.search': 'Пошук',

  'topbar.tagline': 'ринок праці · Україна',
  'topbar.logout': 'Вийти',
  'topbar.openMenu': 'Відкрити меню',
  'topbar.closeMenu': 'Закрити меню',
  'topbar.admin': 'Адміністратор',

  'sidebar.sourceLabel': 'джерела',
  'sidebar.etl': 'etl: збір → llm → sql',

  'footer.about.title': 'Про нас',
  'footer.about.text':
    '503Work — інформаційно-аналітична система ринку праці України. ' +
    'Ми збираємо вакансії та резюме з відкритих джерел, обробляємо їх за допомогою LLM ' +
    'і показуємо агреговану аналітику: попит на навички, зарплати, географію.',
  'footer.sources.title': 'Джерела даних',
  'footer.stack.title': 'Як це працює',
  'footer.stack.text':
    'ETL-пайплайн збирає оголошення, LLM витягує структуровані дані, ' +
    'зарплати конвертуються в USD за курсом НБУ.',
  'footer.note': 'дані з відкритих джерел · агрегована статистика, не комерційна пропозиція',

  'states.error.title': 'err: дані недоступні',
  'states.error.hint': 'Перевірте API за адресою /health',
  'states.empty.title': 'Немає даних',
  'states.empty.hint': 'Запустіть ETL-пайплайн або перевірте фільтри',

  'boundary.title': 'Щось пішло не так',
  'boundary.text': 'Сторінка впала з помилкою. Спробуйте перезавантажити.',
  'boundary.reload': 'Перезавантажити',

  'notfound.quip': 'очікували 503? цього разу — not found',
  'notfound.text': 'Такої сторінки не існує',
  'notfound.back': '→ на дашборд',

  'dash.title': 'Дашборд',
  'dash.desc': 'Зведена статистика ринку вакансій та резюме в Україні',
  'dash.err.api': 'Перевірте чи запущений API на localhost:8000',
  'kpi.vacancies': 'Вакансії',
  'kpi.resumes': 'Резюме',
  'kpi.avgVacSalary': 'Сер. ЗП вакансій',
  'kpi.avgResSalary': 'Сер. ЗП резюме',
  'kpi.usdMonth': 'USD / місяць',

  'card.activity.title': 'Активність ринку',
  'card.activity.descCount': 'Кількість нових вакансій та резюме у кожному періоді',
  'card.activity.descSalary': 'Середня зарплата вакансій та резюме у кожному періоді',
  'card.salaryDist.title': 'Розподіл зарплат',
  'card.salaryDist.desc': 'Вакансії vs резюме у діапазонах USD',
  'card.expTime.title': 'Структура досвіду в часі',
  'card.expTime.desc': 'Як розподіляється попит на junior/middle/senior за період',
  'card.topSkills.title': 'Топ навичок',
  'card.topSkills.desc': 'Найбільш популярні навички у вакансіях',
  'card.topCities.title': 'Топ міст',
  'card.topCities.desc': 'Географія активних вакансій',
  'card.sources.title': 'Джерела даних',
  'card.sources.desc': 'Вакансії та резюме за джерелом збору (work.ua, robota.ua, DOU)',
  'card.expSalary.title': 'Досвід та зарплата',
  'card.expSalary.desc': 'Кількість вакансій + середня ЗП по рівнях',
  'card.english.title': 'Рівень англійської',
  'card.english.desc': 'Вимоги у вакансіях',
  'card.topEmployers.title': 'Топ роботодавців',
  'card.topEmployers.desc': 'Компанії з найбільшою кількістю вакансій',
  'card.candExp.title': 'Досвід кандидатів',
  'card.candExp.desc': 'Рівні досвіду у резюме та середня очікувана ЗП',
  'card.resumeSkills.title': 'Топ навичок у резюме',
  'card.resumeSkills.desc': 'Що знають кандидати',

  'seg.new': 'Нові',
  'seg.salary': 'ЗП',
  'seg.day': 'Д',
  'seg.week': 'Т',
  'seg.month': 'М',
  'seg.30d': '30д',
  'seg.90d': '90д',
  'seg.180d': '180д',
  'seg.share': 'Частка %',
  'seg.count': 'Кількість',

  'skills.title': 'Навички',
  'skills.desc': 'Попит та пропозиція по навичкам, gap-аналіз ринку',
  'skills.seg.demand': 'Попит',
  'skills.seg.supply': 'Пропозиція',
  'skills.seg.gap': 'Gap-аналіз',

  'salary.title': 'Зарплати',
  'salary.desc': 'Розподіл зарплат у вакансіях та резюме, конвертовано в USD за курсом НБУ',
  'salary.kpi.vacWith': 'Вакансій з ЗП',
  'salary.kpi.resWith': 'Резюме з ЗП',
  'salary.ofAll': 'від усіх',

  'geo.title': 'Географія',
  'geo.desc': 'Розподіл вакансій та резюме по містах України',
  'geo.seg.vacancies': 'Вакансії',
  'geo.seg.resumes': 'Резюме',

  'search.title': 'Пошук',
} as const

export type TKey = keyof typeof uk

const en: Record<TKey, string> = {
  'nav.dashboard': 'Dashboard',
  'nav.skills': 'Skills',
  'nav.salary': 'Salaries',
  'nav.geography': 'Geography',
  'nav.search': 'Search',

  'topbar.tagline': 'labor market · Ukraine',
  'topbar.logout': 'Log out',
  'topbar.openMenu': 'Open menu',
  'topbar.closeMenu': 'Close menu',
  'topbar.admin': 'Administrator',

  'sidebar.sourceLabel': 'sources',
  'sidebar.etl': 'etl: scrape → llm → sql',

  'footer.about.title': 'About us',
  'footer.about.text':
    '503Work is an information and analytics system for the Ukrainian labor market. ' +
    'We collect vacancies and resumes from open sources, process them with LLMs ' +
    'and present aggregated analytics: skill demand, salaries and geography.',
  'footer.sources.title': 'Data sources',
  'footer.stack.title': 'How it works',
  'footer.stack.text':
    'An ETL pipeline collects postings, an LLM extracts structured data, ' +
    'salaries are converted to USD at the NBU exchange rate.',
  'footer.note': 'data from open sources · aggregated statistics, not a commercial offer',

  'states.error.title': 'err: data unavailable',
  'states.error.hint': 'Check the API at /health',
  'states.empty.title': 'No data',
  'states.empty.hint': 'Run the ETL pipeline or adjust the filters',

  'boundary.title': 'Something went wrong',
  'boundary.text': 'The page crashed with an error. Try reloading.',
  'boundary.reload': 'Reload',

  'notfound.quip': 'expected a 503? this time — not found',
  'notfound.text': 'This page does not exist',
  'notfound.back': '→ to dashboard',

  'dash.title': 'Dashboard',
  'dash.desc': 'Aggregate statistics of the vacancy and resume market in Ukraine',
  'dash.err.api': 'Check that the API is running on localhost:8000',
  'kpi.vacancies': 'Vacancies',
  'kpi.resumes': 'Resumes',
  'kpi.avgVacSalary': 'Avg vacancy salary',
  'kpi.avgResSalary': 'Avg resume salary',
  'kpi.usdMonth': 'USD / month',

  'card.activity.title': 'Market activity',
  'card.activity.descCount': 'New vacancies and resumes per period',
  'card.activity.descSalary': 'Average vacancy and resume salary per period',
  'card.salaryDist.title': 'Salary distribution',
  'card.salaryDist.desc': 'Vacancies vs resumes across USD ranges',
  'card.expTime.title': 'Experience structure over time',
  'card.expTime.desc': 'How junior/middle/senior demand is distributed over the period',
  'card.topSkills.title': 'Top skills',
  'card.topSkills.desc': 'Most in-demand skills in vacancies',
  'card.topCities.title': 'Top cities',
  'card.topCities.desc': 'Geography of active vacancies',
  'card.sources.title': 'Data sources',
  'card.sources.desc': 'Vacancies and resumes by collection source (work.ua, robota.ua, DOU)',
  'card.expSalary.title': 'Experience and salary',
  'card.expSalary.desc': 'Vacancy count + average salary per level',
  'card.english.title': 'English level',
  'card.english.desc': 'Requirements in vacancies',
  'card.topEmployers.title': 'Top employers',
  'card.topEmployers.desc': 'Companies with the most vacancies',
  'card.candExp.title': 'Candidate experience',
  'card.candExp.desc': 'Experience levels in resumes and average expected salary',
  'card.resumeSkills.title': 'Top resume skills',
  'card.resumeSkills.desc': 'What candidates know',

  'seg.new': 'New',
  'seg.salary': 'Pay',
  'seg.day': 'D',
  'seg.week': 'W',
  'seg.month': 'M',
  'seg.30d': '30d',
  'seg.90d': '90d',
  'seg.180d': '180d',
  'seg.share': 'Share %',
  'seg.count': 'Count',

  'skills.title': 'Skills',
  'skills.desc': 'Skill demand and supply, market gap analysis',
  'skills.seg.demand': 'Demand',
  'skills.seg.supply': 'Supply',
  'skills.seg.gap': 'Gap analysis',

  'salary.title': 'Salaries',
  'salary.desc': 'Salary distribution in vacancies and resumes, converted to USD at the NBU rate',
  'salary.kpi.vacWith': 'Vacancies with salary',
  'salary.kpi.resWith': 'Resumes with salary',
  'salary.ofAll': 'of all',

  'geo.title': 'Geography',
  'geo.desc': 'Vacancies and resumes across Ukrainian cities',
  'geo.seg.vacancies': 'Vacancies',
  'geo.seg.resumes': 'Resumes',

  'search.title': 'Search',
}

// `Record<TKey, string>` на `en` (не `as const`, як у uk) - TypeScript
// вимагатиме ВСІ ключі uk-словника присутніми в en, тож пропущений переклад
// ловиться помилкою компіляції, а не порожнім рядком у проді.
const dict: Record<Lang, Record<TKey, string>> = { uk, en }

interface I18nContextValue {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: TKey) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() =>
    localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'uk',
  )

  useEffect(() => {
    // Синхронізуємо атрибут <html lang="..."> зі станом - впливає на те, як
    // скрінрідери й браузерний spellcheck/переклад трактують сторінку.
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    localStorage.setItem(STORAGE_KEY, next)
  }, [])

  // Фолбек на uk[key], якщо раптом ключа нема в поточному словнику (не мало б
  // траплятись при коректній типізації, але захищає рантайм від undefined).
  const t = useCallback((key: TKey) => dict[lang][key] ?? uk[key], [lang])

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n можна викликати лише всередині I18nProvider')
  return ctx
}
