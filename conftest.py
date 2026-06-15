# Порожній conftest у корені — щоб pytest додав корінь проєкту в sys.path
# і `from src.processor import ...` працювало без PYTHONPATH.
