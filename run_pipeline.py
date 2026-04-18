import subprocess
import logging
import sys

# Налаштування логування
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_script(module_name: str) -> None:
    """Запускає вказаний Python-модуль у вигляді окремого процесу."""
    logger.info(f"▶️ ПОЧАТОК ЕТАПУ: {module_name}...")
    try:
        # sys.executable гарантує, що ми використовуємо той самий віртуальний інтерпретатор,
        # з якого запущено цей runner. Прапорець -m вирішує проблеми з PYTHONPATH.
        subprocess.run([sys.executable, "-m", module_name], check=True)
        logger.info(f"✅ ЕТАП {module_name} ЗАВЕРШЕНО УСПІШНО.\n" + "-" * 50)
    except subprocess.CalledProcessError as e:
        logger.error(
            f"❌ КРИТИЧНА ПОМИЛКА: Етап {module_name} завершився з кодом {e.returncode}. Зупинка пайплайну."
        )
        sys.exit(1)  # Зупиняємо весь пайплайн, якщо один з кроків впав
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Виконання примусово зупинено користувачем.")
        sys.exit(0)


def main():
    logger.info("🚀 СТАРТ ПОВНОГО ПАЙПЛАЙНУ ЗБОРУ ТА ОБРОБКИ ДАНИХ 🚀\n" + "=" * 50)

    # === ЕТАП 1: СКРЕЙПІНГ (Наповнення Staging) ===
    # Спочатку збираємо сирі дані з сайтів.
    run_script("src.scrapers.workua_vacancies")
    run_script("src.scrapers.workua_resumes")

    # === ЕТАП 2: NLP ОБРОБКА (Наповнення Core) ===
    # Передаємо сирі дані в Gemini для структуризації.
    run_script("src.processor.nlp_vacancies")
    run_script("src.processor.nlp_resumes")

    # === ЕТАП 3: КОНВЕРТАЦІЯ ВАЛЮТ (Зарезервовано) ===
    # Тут буде скрипт для приведення зарплат до єдиного знаменника в USD
    # run_script("src.processor.currency_converter")

    logger.info("🎉 ВЕСЬ ПАЙПЛАЙН УСПІШНО ВИКОНАНО! Дані готові для аналітики.")


if __name__ == "__main__":
    main()
