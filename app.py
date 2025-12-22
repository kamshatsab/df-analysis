import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Анализ динамики фонда", layout="wide")

st.title("📊 Анализ изменений движения ДФ и способов эксплуатации")
st.write("Загрузите два файла для сравнения изменений в фонде.")

# --- читаем справочник из репозитория ---
# fond.csv рядом с app.py в GitHub
fond = pd.read_csv("fond.csv")

# Блок загрузки файлов
col1, col2 = st.columns(2)

with col1:
    file1 = st.file_uploader("Загрузите файл на начальную дату (Excel)", type=['xlsx'])
with col2:
    file2 = st.file_uploader("Загрузите файл на конечную дату (Excel)", type=['xlsx'])

if file1 and file2:
    try:
        # Чтение данных
        df1_raw = pd.read_excel(file1, sheet_name='Отчет', skiprows=4)
        df2_raw = pd.read_excel(file2, sheet_name='Отчет', skiprows=4)

        # Фильтрация
        def filter_data(df: pd.DataFrame) -> pd.DataFrame:
            return df[
                (df['Состояние'].isin(['В работе', 'В простое'])) &
                (df['Категория'] == 'Нефтяная')
            ]

        filtered_df1 = filter_data(df1_raw)
        filtered_df2 = filter_data(df2_raw)

        # 1) Выведены из ДФ
        only_in_df1 = filtered_df1[
            ~filtered_df1['Скважина'].isin(filtered_df2['Скважина'])
        ]

        # 2) Введены в ДФ
        only_in_df2 = filtered_df2[
            ~filtered_df2['Скважина'].isin(filtered_df1['Скважина'])
        ]

        # 3) Замена способа эксплуатации
        df_merged = filtered_df1.merge(
            filtered_df2,
            on='Скважина',
            suffixes=('_df1', '_df2')
        )

        df_changed = df_merged[
            df_merged['Способ эксплуатации_df1'] != df_merged['Способ эксплуатации_df2']
        ]

        # ---- Формируем события ----
        out_list = only_in_df1[['Скважина']].copy()
        out_list['Пояснение'] = 'Выведено из ДФ'

        in_list = only_in_df2[['Скважина']].copy()
        in_list['Пояснение'] = 'Введено в ДФ'

        chg_list = df_changed[['Скважина']].copy()
        chg_list['Пояснение'] = 'Замена способа эксплуатации'

        # Объединяем все события
        events = pd.concat([out_list, in_list, chg_list], ignore_index=True)

        # Одна строка на скважину + объединение пояснений
        final_table = (
            events.groupby('Скважина', as_index=False)['Пояснение']
            .apply(lambda s: '; '.join(sorted(set(s))))
        )

        # ---- ДОБАВЛЯЕМ НГДУ / ЦДНГ / ГУ ИЗ fond.csv ----
        cols_meta = ['Скважина', 'НГДУ', 'ЦДНГ', 'ГУ']

        missing = [c for c in cols_meta if c not in fond.columns]
        if missing:
            raise ValueError(f"В fond.csv нет колонок: {missing}. Нужны: {cols_meta}")

        meta = fond[cols_meta].drop_duplicates(subset=['Скважина'], keep='first').copy()

        final_table = final_table.merge(meta, on='Скважина', how='left')

        # порядок колонок как нужно
        final_table = final_table[['НГДУ', 'ЦДНГ', 'ГУ', 'Скважина', 'Пояснение']]

        # сортировка
        final_table = final_table.sort_values(['НГДУ', 'ЦДНГ', 'ГУ', 'Скважина']).reset_index(drop=True)

        # Вывод на сайт
        st.subheader("Результат обработки:")
        st.dataframe(final_table, use_container_width=True)

        # Экспорт в Excel
        def to_excel(df: pd.DataFrame) -> bytes:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Результат')
            return output.getvalue()

        excel_data = to_excel(final_table)

        st.download_button(
            label="📥 Скачать итоговый файл (Excel)",
            data=excel_data,
            file_name='анализ_динамики_фонда.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except FileNotFoundError:
        st.error("Не найден файл fond.csv в репозитории. Загрузите fond.csv рядом с app.py в GitHub.")
    except Exception as e:
        st.error(f"Произошла ошибка при обработке: {e}")
        st.info(
            "Проверьте:\n"
            "1) В Excel есть лист 'Отчет'\n"
            "2) Колонки в Excel: Скважина, Состояние, Категория, Способ эксплуатации\n"
            "3) В fond.csv есть колонки: Скважина, НГДУ, ЦДНГ, ГУ"
        )
