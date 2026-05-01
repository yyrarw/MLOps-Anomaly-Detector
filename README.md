# MLOps Anomaly Detector

Сервис для обнаружения аномалий в метриках ML-инфраструктуры (GPU, память, задержки, очереди). Пользователь загружает метрики через веб-интерфейс или API, система прогоняет их через ML-модель и возвращает список аномалий.

## Стек

- **FastAPI** — REST API
- **Streamlit** — веб-интерфейс
- **PostgreSQL** — база данных
- **RabbitMQ** — очередь задач
- **Ollama + TinyLlama** — LLM-модель для детекции аномалий
- **Docker Compose** — оркестрация

## Требования

- Docker и Docker Compose

## Запуск

```bash
docker compose up --build
```

Первый запуск занимает несколько минут — Ollama скачивает модель TinyLlama (~600 МБ).

После запуска доступны:

| Сервис | URL |
|---|---|
| Веб-интерфейс (Streamlit) | http://localhost:8501 |
| REST API | http://localhost:8000 |
| API документация | http://localhost:8000/docs |
| RabbitMQ Management | http://localhost:15672 |

## Использование

### Через веб-интерфейс

1. Открыть http://localhost:8501
2. Зарегистрироваться во вкладке **Вход / Регистрация**
3. Пополнить баланс в разделе **Личный кабинет**
4. Отправить данные в разделе **ML-запрос** (форма или CSV-файл)
5. Просмотреть результаты в разделе **История**

### Через API

**Регистрация:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

**Пополнение баланса:**
```bash
curl -X POST http://localhost:8000/balance/top-up \
  -u user@example.com:password123 \
  -H "Content-Type: application/json" \
  -d '{"amount": 50.0}'
```

**Отправка данных на анализ:**
```bash
curl -X POST http://localhost:8000/predict \
  -u user@example.com:password123 \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": 1,
    "rows": [
      {"metric": "gpu_utilization", "value": 95.0, "node": "node-1", "timestamp": "2024-01-01T00:00:00"},
      {"metric": "memory_usage", "value": 40.0, "node": "node-1", "timestamp": "2024-01-01T00:00:00"}
    ]
  }'
```

**Получение результата:**
```bash
curl http://localhost:8000/history/predictions/{task_id} \
  -u user@example.com:password123
```

## Поддерживаемые метрики

| Метрика | Описание |
|---|---|
| `gpu_utilization` | Загрузка GPU, % |
| `memory_usage` | Использование памяти, % |
| `latency_ms` | Задержка ответа, мс |
| `queue_size` | Размер очереди запросов |
| `tokens_per_second` | Скорость генерации токенов |

## ML-модели

| Модель | Описание | Стоимость |
|---|---|---|
| `ZScoreDetector` | Статистический детектор на основе Z-оценки | 2 кр. |
| `IsolationForest` | Древовидная модель для многомерных данных | 5 кр. |
| `AutoencoderDetector` | LLM-модель (TinyLlama via Ollama) | 10 кр. |

## Формат CSV

При загрузке через файл CSV должен содержать колонки:

```
metric,value,node,timestamp
gpu_utilization,95.0,node-1,2024-01-01T00:00:00
memory_usage,40.0,node-1,2024-01-01T00:00:00
```

## Запуск тестов

Тесты не требуют запущенного Docker.

```bash
cd app
pip install -r requirements-test.txt
python -m pytest tests/ -v
```

## Остановка

```bash
docker compose down
```

Для полного сброса (включая базу данных):

```bash
docker compose down -v
```
