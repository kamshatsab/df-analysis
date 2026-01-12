import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os

st.set_page_config(page_title="Анализ динамики фонда", layout="wide")

st.title("📊 Анализ изменений движения ДФ и способов эксплуатации")
st.write("Загрузите два файла для сравнения изменений в фонде.")

# ================== СПРАВОЧНИКИ ИЗ РЕПОЗИТОРИЯ ==================

# --- fond.csv ---
fond = pd.read_csv("fond.csv")
fond.columns = fond.columns.str.replace('"', '').str.strip()

# --- main_well.csv ---
main_well = pd.read_csv("main_well.csv")
main_well.columns = main_well.columns.str.replace('"', '').str.strip()
main_well = main_well.rename(columns={'name': 'Скважина'})

main_well = (
    main_well[['Скважина', 'sedmax_ip', 'lora_id']]
    .drop_duplicates(subset=['Скважина'], keep='first')
)

# --- Reviziya.xlsx ---
reviziya = pd.read_excel(
    "Reviziya.xlsx",
    sheet_name="Отчет",
    skiprows=5
)
reviziya.columns = reviziya.columns.str.replace('"', '').str.strip()
reviziya = reviziya.rename(columns={'Дата перевода в Д/Ф': 'Дата перевода в ДФ'})

reviziya = (
    reviziya[['Скважина', 'Дата ввода в эксплуатацию', 'Дата перевода в ДФ']]
    .drop_duplicates(subset=['Скважина'], keep='first')
)

# ================== ЛОГИРОВАНИЕ ==================

LOG_PATH = "usage_log.csv"

def log_event(event: str, file1_name="", file2_name=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = pd.DataFrame([{
        "timestamp": ts,
        "event": event,
        "file1": file1_name,
        "file2": file2_name,
    }])

    if os.path.exists(LOG_PATH):
        row.to_csv(LOG_PATH, mode="a", header=False, index=False)
    else:
        row.to_csv(LOG_PATH, mode="w", header=True, index=False)

def read_last_logs(n=100):
    if not os.path.exists(LOG_PATH):
        return pd.DataFrame(columns=["timestamp", "event", "file1", "file2"])
    return pd.read_csv(LOG_PATH).tail(n).iloc[::-1]

# ================== ЗАГРУЗКА ФАЙЛОВ ==================

col1, col2 = st.columns(2)
with col1:
    file1 = st.file_uploader("Загрузите файл на начальную дату (Excel)", type=["xlsx"])
with col2:
    file2 = st.file_uploader("Загрузите файл на конечную дату (Excel)", type=["xlsx"])

if file1 and file2:
    try:
        df1 = pd.read_excel(file1, sheet_name="Отчет", skiprows=4)
        df2 = pd.read_excel(file2, sheet_name="Отчет", skiprows=4)

        def filter_df(df):
            return df[
                (df["Состояние"].isin(["В работе", "В простое"])) &
                (df["Категория"] == "Нефтяная")
            ]

        f1 = filter_df(df1)
        f2 = filter_df(df2)

        out_df = f1[~f1["Скважина"].isin(f2["Скважина"])]
        in_df = f2[~f2["Скважина"].isin(f1["Скважина"])]

        merged = f1.merge(f2, on="Скважина", suffixes=("_1", "_2"))
        changed = merged[merged["Способ эксплуатации_1"] != merged["Способ эксплуатации_2"]]

        events = pd.concat([
            out_df[["Скважина"]].assign(Пояснение="Выведено из ДФ"),
            in_df[["Скважина"]].assign(Пояснение="Введено в ДФ"),
            changed[["Скважина"]].assign(Пояснение="Замена способа эксплуатации")
        ])

        final_table = (
            events.groupby("Скважина", as_index=False)["Пояснение"]
            .apply(lambda x: "; ".join(sorted(set(x))))
        )

        # fond
        final_table = final_table.merge(
            fond[['Скважина', 'НГДУ', 'ЦДНГ', 'ГУ']],
            on="Скважина",
            how="left"
        )

        # данные на конечную дату
        final_table = final_table.merge(
            f2[['Скважина', 'Категория', 'Состояние', 'Причина простоя', 'Способ эксплуатации']]
            .drop_duplicates('Скважина'),
            on="Скважина",
            how="left"
        )

        # main_well
        final_table = final_table.merge(main_well, on="Скважина", how="left")

        # reviziya
        final_table = final_table.merge(reviziya, on="Скважина", how="left")

        # формат дат
        for c in ["Дата ввода в эксплуатацию", "Дата перевода в ДФ"]:
            final_table[c] = pd.to_datetime(final_table[c], errors="coerce").dt.strftime("%d.%m.%Y")

        # порядок колонок
        final_table = final_table[
            [
                "НГДУ",
                "ЦДНГ",
                "ГУ",
                "Скважина",
                "Категория",
                "Состояние",
                "Причина простоя",
                "Способ эксплуатации",
                "sedmax_ip",
                "lora_id",
                "Дата ввода в эксплуатацию",
                "Дата перевода в ДФ",
                "Пояснение"
            ]
        ].sort_values(["НГДУ", "ЦДНГ", "ГУ", "Скважина"])

        log_event("processed_files", file1.name, file2.name)

        st.subheader("Результат обработки")
        st.dataframe(final_table, use_container_width=True)

        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()

        downloaded = st.download_button(
            "📥 Скачать итоговый файл (Excel)",
            to_excel(final_table),
            "анализ_динамики_фонда.xlsx"
        )

        if downloaded:
            log_event("downloaded_result", file1.name, file2.name)

        with st.expander("🧾 Лог использования"):
            st.dataframe(read_last_logs())

    except Exception as e:
        st.error(f"Ошибка: {e}")
        st.info(
            "Проверьте наличие файлов fond.csv, main_well.csv, Reviziya.xlsx "
            "и колонок в Excel"
        )
