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

cols_main = ['Скважина', 'sedmax_ip', 'lora_id']
missing_main = [c for c in cols_main if c not in main_well.columns]
if missing_main:
    raise ValueError(f"В main_well.csv нет колонок: {missing_main}")

main_well = (
    main_well[cols_main]
    .drop_duplicates(subset=['Скважина'], keep='first')
    .copy()
)

# ================== ЛОГИРОВАНИЕ ==================

LOG_PATH = "usage_log.csv"

def log_event(event: str, file1_name: str = "", file2_name: str = "") -> None:
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

def read_last_logs(n: int = 100) -> pd.DataFrame:
    if not os.path.exists(LOG_PATH):
        return pd.DataFrame(columns=["timestamp", "event", "file1", "file2"])
    df = pd.read_csv(LOG_PATH)
    return df.tail(n).iloc[::-1].reset_index(drop=True)

# ================== ЗАГРУЗКА ФАЙЛОВ ==================

col1, col2 = st.columns(2)

with col1:
    file1 = st.file_uploader("Загрузите файл на начальную дату (Excel)", type=["xlsx"])
with col2:
    file2 = st.file_uploader("Загрузите файл на конечную дату (Excel)", type=["xlsx"])

if file1 and file2:
    try:
        # --- Чтение Excel ---
        df1_raw = pd.read_excel(file1, sheet_name="Отчет", skiprows=4)
        df2_raw = pd.read_excel(file2, sheet_name="Отчет", skiprows=4)

        # --- Фильтрация ---
        def filter_data(df: pd.DataFrame) -> pd.DataFrame:
            return df[
                (df["Состояние"].isin(["В работе", "В простое"])) &
                (df["Категория"] == "Нефтяная")
            ]

        filtered_df1 = filter_data(df1_raw)
        filtered_df2 = filter_data(df2_raw)

        # --- События ---
        only_in_df1 = filtered_df1[
            ~filtered_df1["Скважина"].isin(filtered_df2["Скважина"])
        ]

        only_in_df2 = filtered_df2[
            ~filtered_df2["Скважина"].isin(filtered_df1["Скважина"])
        ]

        df_merged = filtered_df1.merge(
            filtered_df2,
            on="Скважина",
            suffixes=("_df1", "_df2")
        )

        df_changed = df_merged[
            df_merged["Способ эксплуатации_df1"] != df_merged["Способ эксплуатации_df2"]
        ]

        out_list = only_in_df1[["Скважина"]].copy()
        out_list["Пояснение"] = "Выведено из ДФ"

        in_list = only_in_df2[["Скважина"]].copy()
        in_list["Пояснение"] = "Введено в ДФ"

        chg_list = df_changed[["Скважина"]].copy()
        chg_list["Пояснение"] = "Замена способа эксплуатации"

        events = pd.concat([out_list, in_list, chg_list], ignore_index=True)

        final_table = (
            events.groupby("Скважина", as_index=False)["Пояснение"]
            .apply(lambda s: "; ".join(sorted(set(s))))
        )

        # --- НГДУ / ЦДНГ / ГУ ---
        cols_fond = ["Скважина", "НГДУ", "ЦДНГ", "ГУ"]
        missing_fond = [c for c in cols_fond if c not in fond.columns]
        if missing_fond:
            raise ValueError(f"В fond.csv нет колонок: {missing_fond}")

        meta_fond = fond[cols_fond].drop_duplicates(
            subset=["Скважина"], keep="first"
        )

        final_table = final_table.merge(meta_fond, on="Скважина", how="left")

        # --- Причина простоя / Способ эксплуатации (из 2-го файла) ---
        cols_df2 = ["Скважина", "Причина простоя", "Способ эксплуатации"]
        missing_df2 = [c for c in cols_df2 if c not in filtered_df2.columns]
        if missing_df2:
            raise ValueError(f"Во 2-м файле нет колонок: {missing_df2}")

        meta_df2 = filtered_df2[cols_df2].drop_duplicates(
            subset=["Скважина"], keep="first"
        )

        final_table = final_table.merge(meta_df2, on="Скважина", how="left")

        # --- sedmax_ip / lora_id ---
        final_table = final_table.merge(main_well, on="Скважина", how="left")

        # --- ПОРЯДОК КОЛОНОК ---
        final_table = final_table[
            [
                "НГДУ",
                "ЦДНГ",
                "ГУ",
                "Скважина",
                "Причина простоя",
                "Способ эксплуатации",
                "sedmax_ip",
                "lora_id",
                "Пояснение",
            ]
        ]

        final_table = final_table.sort_values(
            ["НГДУ", "ЦДНГ", "ГУ", "Скважина"],
            na_position="last"
        ).reset_index(drop=True)

        # --- ЛОГ ---
        log_event(
            event="processed_files",
            file1_name=file1.name,
            file2_name=file2.name
        )

        st.subheader("Результат обработки:")
        st.dataframe(final_table, use_container_width=True)

        # --- Excel ---
        def to_excel(df: pd.DataFrame) -> bytes:
            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Результат")
            return output.getvalue()

        excel_data = to_excel(final_table)

        downloaded = st.download_button(
            "📥 Скачать итоговый файл (Excel)",
            excel_data,
            "анализ_динамики_фонда.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        if downloaded:
            log_event(
                event="downloaded_result",
                file1_name=file1.name,
                file2_name=file2.name
            )

        with st.expander("🧾 Лог использования (последние 100 записей)"):
            st.dataframe(read_last_logs(100), use_container_width=True)

    except Exception as e:
        st.error(f"Произошла ошибка: {e}")
        st.info(
            "Проверьте:\n"
            "1) В Excel есть лист 'Отчет'\n"
            "2) Во 2-м Excel есть колонки: Причина простоя, Способ эксплуатации\n"
            "3) В fond.csv есть: Скважина, НГДУ, ЦДНГ, ГУ\n"
            "4) В main_well.csv есть: name (или Скважина), sedmax_ip, lora_id"
        )
