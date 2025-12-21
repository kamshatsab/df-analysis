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
        def filter_data(df):
            return df[
                (df['Состояние'].isin(['В работе', 'В простое'])) & 
                (df['Категория'] == 'Нефтяная')
            ]

        filtered_df1 = filter_data(df1_raw)
        filtered_df2 = filter_data(df2_raw)

        # 1. Выведены из ДФ
        only_in_df1 = filtered_df1[~filtered_df1['Скважина'].isin(filtered_df2['Скважина'])]
        out_df = only_in_df1[['Скважина']].rename(columns={'Скважина': 'Выведено из ДФ'}).reset_index(drop=True)

        # 2. Введены в ДФ
        only_in_df2 = filtered_df2[~filtered_df2['Скважина'].isin(filtered_df1['Скважина'])]
        in_df = only_in_df2[['Скважина']].rename(columns={'Скважина': 'Введено в ДФ'}).reset_index(drop=True)

        # 3. Изменение способа эксплуатации
        df_merged = filtered_df1.merge(filtered_df2, on='Скважина', suffixes=('_df1', '_df2'))
        df_changed = df_merged[
            df_merged['Способ эксплуатации_df1'] != df_merged['Способ эксплуатации_df2']
        ]
        
        changes_df = df_changed[['Скважина', 'Способ эксплуатации_df1', 'Способ эксплуатации_df2']].rename(
            columns={
                'Скважина': 'Замена способа эксплуатации',
                'Способ эксплуатации_df1': 'Было',
                'Способ эксплуатации_df2': 'Стало'
            }
        ).reset_index(drop=True)

        # Итоговая таблица
        final_table = pd.concat([out_df, in_df, changes_df], axis=1)

        # Отображение результата на сайте
        st.subheader("Результат обработки:")
        st.dataframe(final_table, use_container_width=True)

        # Функция для конвертации в Excel для скачивания
        def to_excel(df):
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
        st.info("Проверьте, что в файлах есть лист 'Отчет' и нужные колонки.")