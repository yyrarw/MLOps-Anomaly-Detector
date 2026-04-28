import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://app:8000")
SUPPORTED_METRICS = ["gpu_utilization", "memory_usage", "latency_ms", "queue_size", "tokens_per_second"]

st.set_page_config(page_title="MLOps Anomaly Detector", page_icon="🔍", layout="wide")


# --- API helpers ---

def _auth():
    return (st.session_state.get("email"), st.session_state.get("password"))


def api_get(path: str, auth=True):
    try:
        r = requests.get(
            f"{API_URL}{path}",
            auth=_auth() if auth else None,
            timeout=10,
        )
        return r
    except requests.exceptions.ConnectionError:
        st.error("Не удаётся подключиться к серверу.")
        return None


def api_post(path: str, data: dict, auth=True):
    try:
        r = requests.post(
            f"{API_URL}{path}",
            json=data,
            auth=_auth() if auth else None,
            timeout=10,
        )
        return r
    except requests.exceptions.ConnectionError:
        st.error("Не удаётся подключиться к серверу.")
        return None


def error_message(r) -> str:
    try:
        return r.json().get("error", {}).get("message", r.text)
    except Exception:
        return r.text


# --- Session helpers ---

def is_logged_in() -> bool:
    return st.session_state.get("authenticated", False)


def logout():
    for key in ["email", "password", "authenticated", "user"]:
        st.session_state.pop(key, None)
    st.rerun()


# --- Pages ---

def page_home():
    st.title("🔍 MLOps Anomaly Detector")
    st.markdown("""
    ### О сервисе

    **MLOps Anomaly Detector** — платформа для обнаружения аномалий в метриках инфраструктуры.

    #### Что умеет сервис:
    - **Детектировать аномалии** в метриках GPU, памяти, задержках и очередях
    - **Обрабатывать запросы асинхронно** через очередь сообщений RabbitMQ
    - **Масштабироваться** — несколько ML-воркеров обрабатывают задачи параллельно

    #### Доступные метрики:
    """)

    for m in SUPPORTED_METRICS:
        st.markdown(f"- `{m}`")

    st.markdown("""
    #### Как начать:
    1. Зарегистрируйтесь в разделе **Вход / Регистрация**
    2. Пополните баланс в **Личном кабинете**
    3. Отправьте данные через раздел **ML-запрос**
    4. Просмотрите результаты в **Истории**
    """)

    r = api_get("/models", auth=False)
    if r and r.status_code == 200:
        st.markdown("#### Доступные модели:")
        models = r.json()
        for m in models:
            st.markdown(f"- **{m['name']}** — {m['description']} *(стоимость: {m['cost_per_request']} кредитов)*")


def page_auth():
    st.title("🔑 Вход / Регистрация")

    tab_login, tab_register = st.tabs(["Войти", "Зарегистрироваться"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти")

        if submitted:
            if not email or not password:
                st.error("Заполните все поля.")
            else:
                st.session_state["email"] = email
                st.session_state["password"] = password
                r = api_get("/users/me")
                if r is None:
                    return
                if r.status_code == 200:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = r.json()
                    st.success("Вход выполнен!")
                    st.rerun()
                else:
                    st.session_state.pop("email", None)
                    st.session_state.pop("password", None)
                    st.error(f"Ошибка входа: {error_message(r)}")

    with tab_register:
        with st.form("register_form"):
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Пароль (мин. 8 символов)", type="password", key="reg_pass")
            submitted_reg = st.form_submit_button("Зарегистрироваться")

        if submitted_reg:
            if not reg_email or not reg_password:
                st.error("Заполните все поля.")
            else:
                r = api_post("/auth/register", {"email": reg_email, "password": reg_password}, auth=False)
                if r is None:
                    return
                if r.status_code == 201:
                    st.success("Регистрация успешна! Теперь войдите.")
                else:
                    st.error(f"Ошибка: {error_message(r)}")


def page_dashboard():
    st.title("📊 Личный кабинет")

    user = st.session_state.get("user", {})
    st.markdown(f"**Email:** {user.get('email', '—')}")
    st.markdown(f"**Роль:** {user.get('role', '—')}")
    st.markdown(f"**Зарегистрирован:** {user.get('created_at', '—')[:10]}")

    st.divider()

    r = api_get("/balance")
    if r is None:
        return
    if r.status_code == 200:
        balance = r.json()["balance"]
        st.metric("💳 Баланс", f"{balance:.2f} кредитов")
    else:
        st.error(f"Ошибка получения баланса: {error_message(r)}")
        return

    st.subheader("Пополнить баланс")
    with st.form("topup_form"):
        amount = st.number_input("Сумма пополнения (кредитов)", min_value=1.0, value=50.0, step=10.0)
        submitted = st.form_submit_button("Пополнить")

    if submitted:
        r = api_post("/balance/top-up", {"amount": amount})
        if r is None:
            return
        if r.status_code == 200:
            new_balance = r.json()["balance"]
            st.success(f"Баланс пополнен. Новый баланс: {new_balance:.2f} кредитов")
            st.rerun()
        else:
            st.error(f"Ошибка: {error_message(r)}")


def page_predict():
    st.title("🤖 ML-запрос")

    r_balance = api_get("/balance")
    if r_balance is None:
        return
    balance = r_balance.json().get("balance", 0) if r_balance.status_code == 200 else 0
    st.metric("💳 Текущий баланс", f"{balance:.2f} кредитов")

    if balance <= 0:
        st.error("Недостаточно средств. Пополните баланс в Личном кабинете.")
        return

    r_models = api_get("/models", auth=False)
    if r_models is None or r_models.status_code != 200:
        st.error("Не удалось загрузить список моделей.")
        return
    models = r_models.json()
    model_options = {f"{m['name']} ({m['cost_per_request']} кр.)": m["id"] for m in models}

    st.subheader("Параметры запроса")
    selected_label = st.selectbox("Модель", list(model_options.keys()))
    model_id = model_options[selected_label]
    selected_model = next(m for m in models if m["id"] == model_id)

    if balance < selected_model["cost_per_request"]:
        st.warning(f"Недостаточно средств для этой модели. Нужно {selected_model['cost_per_request']} кр., доступно {balance:.2f} кр.")
        return

    st.subheader("Входные данные")
    input_method = st.radio("Способ ввода", ["Форма", "CSV-файл"], horizontal=True)

    rows = []

    if input_method == "Форма":
        n_rows = st.number_input("Количество строк", min_value=1, max_value=20, value=1)
        valid_rows = []
        invalid_rows = []

        for i in range(int(n_rows)):
            st.markdown(f"**Строка {i + 1}**")
            cols = st.columns(4)
            with cols[0]:
                metric = st.selectbox("Метрика", SUPPORTED_METRICS, key=f"metric_{i}")
            with cols[1]:
                value = st.number_input("Значение", key=f"value_{i}", value=0.0)
            with cols[2]:
                node = st.text_input("Узел (node)", key=f"node_{i}", value="node-1")
            with cols[3]:
                ts = st.text_input("Timestamp", key=f"ts_{i}", value=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))

            row = {"metric": metric, "value": value, "node": node.strip(), "timestamp": ts}
            if not node.strip():
                invalid_rows.append({**row, "error": "node пустой"})
            else:
                valid_rows.append(row)

        if invalid_rows:
            st.warning("Отклонённые строки:")
            st.dataframe(pd.DataFrame(invalid_rows))

        rows = valid_rows

    else:
        uploaded = st.file_uploader("Загрузить CSV", type=["csv"])
        st.caption("Колонки: metric, value, node, timestamp")

        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                required_cols = {"metric", "value", "node", "timestamp"}
                if not required_cols.issubset(df.columns):
                    st.error(f"CSV должен содержать колонки: {required_cols}")
                else:
                    valid_mask = (
                        df["metric"].isin(SUPPORTED_METRICS) &
                        df["node"].notna() & (df["node"].str.strip() != "")
                    )
                    valid_df = df[valid_mask].copy()
                    invalid_df = df[~valid_mask].copy()

                    if not invalid_df.empty:
                        st.warning(f"Отклонено строк: {len(invalid_df)}")
                        st.dataframe(invalid_df)

                    if not valid_df.empty:
                        st.success(f"Корректных строк: {len(valid_df)}")
                        st.dataframe(valid_df)
                        rows = valid_df.to_dict("records")
            except Exception as e:
                st.error(f"Ошибка чтения файла: {e}")

    st.divider()
    if st.button("Отправить запрос", disabled=not rows):
        payload = {
            "model_id": model_id,
            "rows": [
                {
                    "metric": row["metric"],
                    "value": float(row["value"]),
                    "node": str(row["node"]),
                    "timestamp": str(row["timestamp"]),
                }
                for row in rows
            ],
        }
        r = api_post("/predict", payload)
        if r is None:
            return
        if r.status_code == 200:
            result = r.json()
            st.success(f"Задача принята! ID: **{result['task_id']}**, статус: `{result['status']}`")
            st.info(f"Баланс после списания: **{result['balance']:.2f} кредитов**")
            st.caption("Результат появится в Истории после обработки воркером.")
        elif r.status_code == 402:
            st.error("Недостаточно средств на балансе.")
        else:
            st.error(f"Ошибка: {error_message(r)}")


def page_history():
    st.title("📜 История операций")

    tab_pred, tab_tx = st.tabs(["ML-запросы", "Транзакции"])

    with tab_pred:
        r = api_get("/history/predictions")
        if r is None:
            return
        if r.status_code == 200:
            data = r.json()
            if not data:
                st.info("История ML-запросов пуста.")
            else:
                df = pd.DataFrame(data)
                df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                df = df.rename(columns={
                    "task_id": "ID задачи",
                    "model_id": "ID модели",
                    "status": "Статус",
                    "credits_charged": "Списано (кр.)",
                    "created_at": "Дата/время",
                })
                st.dataframe(df, use_container_width=True)
        else:
            st.error(f"Ошибка: {error_message(r)}")

    with tab_tx:
        r = api_get("/history/transactions")
        if r is None:
            return
        if r.status_code == 200:
            data = r.json()
            if not data:
                st.info("История транзакций пуста.")
            else:
                df = pd.DataFrame(data)
                df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                df["type"] = df["type"].map({"topup": "Пополнение", "debit": "Списание"})
                df = df.rename(columns={
                    "id": "ID",
                    "amount": "Сумма (кр.)",
                    "type": "Тип",
                    "task_id": "ID задачи",
                    "created_at": "Дата/время",
                })
                st.dataframe(df, use_container_width=True)
        else:
            st.error(f"Ошибка: {error_message(r)}")


# --- Navigation ---

PAGES_PUBLIC = {"🏠 Главная": page_home, "🔑 Вход / Регистрация": page_auth}
PAGES_PRIVATE = {
    "🏠 Главная": page_home,
    "📊 Личный кабинет": page_dashboard,
    "🤖 ML-запрос": page_predict,
    "📜 История": page_history,
}

with st.sidebar:
    st.title("MLOps Anomaly Detector")
    st.divider()

    if is_logged_in():
        st.success(f"Вы вошли как\n**{st.session_state.get('email', '')}**")
        pages = PAGES_PRIVATE
    else:
        pages = PAGES_PUBLIC

    page = st.radio("Навигация", list(pages.keys()), label_visibility="collapsed")

    if is_logged_in():
        st.divider()
        if st.button("Выйти"):
            logout()

pages[page]()
