import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Анализ динамики фонда", layout="wide")

st.title("📊 Анализ изменении движения ДФ и способов эксплуатации")
st.write("Загрузите два файла для сравнения изменений в фонде.")

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

        # Логика фильтрации
        def filter_data(df: pd.DataFrame) -> pd.DataFrame:
            return df[
                (df['Состояние'].isin(['В работе', 'В простое'])) &
                (df['Категория'] == 'Нефтяная')
            ]

        filtered_df1 = filter_data(df1_raw)
        filtered_df2 = filter_data(df2_raw)

        # 1) Выведены из ДФ
        only_in_df1 = filtered_df1[~filtered_df1['Скважина'].isin(filtered_df2['Скважина'])]

        # 2) Введены в ДФ
        only_in_df2 = filtered_df2[~filtered_df2['Скважина'].isin(filtered_df1['Скважина'])]

        # 3) Изменение способа эксплуатации
        df_merged = filtered_df1.merge(filtered_df2, on='Скважина', suffixes=('_df1', '_df2'))
        df_changed = df_merged[df_merged['Способ эксплуатации_df1'] != df_merged['Способ эксплуатации_df2']]

        # Таблица замен (Скважина / Было / Стало)
        changes = df_changed[['Скважина', 'Способ эксплуатации_df1', 'Способ эксплуатации_df2']].copy()
        changes.columns = ['Скважина', 'Было', 'Стало']

        # ---- НОВОЕ: один список + объединение пояснений ----

        # События "Выведено"
        out_list = only_in_df1[['Скважина']].copy()
        out_list['Пояснение'] = 'Выведено из ДФ'
        out_list['Было'] = pd.NA
        out_list['Стало'] = pd.NA

        # События "Введено"
        in_list = only_in_df2[['Скважина']].copy()
        in_list['Пояснение'] = 'Введено в ДФ'
        in_list['Было'] = pd.NA
        in_list['Стало'] = pd.NA

        # События "Замена"
        chg_list = changes[['Скважина', 'Было', 'Стало']].copy()
        chg_list['Пояснение'] = 'Замена способа эксплуатации'

        # Все события в одну таблицу (вниз)
        events = pd.concat([out_list, in_list, chg_list], ignore_index=True)

        # Одна строка на скважину:
        # - "Пояснение" склеиваем через ; (без дублей)
        # - "Было/Стало" берем первое непустое (если была замена)
        final_table = (
            events.groupby('Скважина', as_index=False)
            .agg({
                'Пояснение': lambda s: '; '.join(sorted(set(s))),
                'Было': lambda s: next((x for x in s.dropna()), pd.NA),
                'Стало': lambda s: next((x for x in s.dropna()), pd.NA),
            })
        )

        # Порядок колонок + сортировка
        final_table = final_table[['Скважина', 'Пояснение', 'Было', 'Стало']]
        final_table = final_table.sort_values('Скважина').reset_index(drop=True)

        # Отображение результата на сайте
        st.subheader("Результат обработки:")
        st.dataframe(final_table, use_container_width=True)

        # Функция для конвертации в Excel для скачивания
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

    except Exception as e:
        st.error(f"Произошла ошибка при обработке: {e}")
        st.info("Проверьте, что в файлах есть лист 'Отчет' и нужные колонки: Скважина, Состояние, Категория, Способ эксплуатации.")
