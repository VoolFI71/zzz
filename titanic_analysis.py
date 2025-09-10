import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Анализ датасета Titanic")
    parser.add_argument("--path", default="titanic.xlsx", help="Путь к файлу titanic.xlsx")
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        print(f"Файл не найден: {args.path}")
        sys.exit(1)

    # Загрузка данных
    df = pd.read_excel(args.path)

    # Просмотр данных и типов
    print("\n=== Превью данных ===")
    print(df.head())
    print("\n=== Информация о столбцах ===")
    df.info()

    # Базовые подсчёты
    print("\n=== Базовые показатели ===")
    total = len(df)
    women = int(df["Sex"].astype(str).str.lower().eq("female").sum()) if "Sex" in df.columns else None
    print(f"Всего пассажиров: {total}")
    if women is not None:
        print(f"Женщин: {women}")

    if "Name" in df.columns:
        unique_names = df["Name"].dropna().astype(str).unique()
        print(f"Уникальных имён: {len(unique_names)}")
        sample = ", ".join(list(unique_names[:10]))
        if sample:
            print(f"Примеры имён: {sample}{' ...' if len(unique_names) > 10 else ''}")

    # Пропуски и очистка
    print("\n=== Пропуски ===")
    na_summary = df.isna().sum()
    if int(na_summary.sum()) == 0:
        print("Пропусков нет")
        df_clean = df.copy()
    else:
        print(na_summary[na_summary > 0].sort_values(ascending=False))
        before = len(df)
        df_clean = df.dropna()
        print(f"Удалено строк: {before - len(df_clean)}. Размер после очистки: {df_clean.shape}")

    # Среднее/медиана (несколько способов) + дисперсия и СКО для двух столбцов
    cols = ["Age", "Fare"]
    print("\n=== Статистики (Age, Fare) ===")
    for col in cols:
        if col not in df_clean.columns:
            print(f"Столбец {col} не найден, пропускаю")
            continue
        s = pd.to_numeric(df_clean[col], errors="coerce").dropna()
        if s.empty:
            print(f"Столбец {col} пуст после приведения к числам, пропускаю")
            continue

        mean_pd = s.mean()
        mean_np = float(np.mean(s.values))
        median_pd = s.median()
        median_np = float(np.median(s.values))
        var_sample = float(np.var(s.values, ddof=1)) if len(s) > 1 else float("nan")
        std_sample = float(np.std(s.values, ddof=1)) if len(s) > 1 else float("nan")

        print(f"\n— {col} —")
        print(f"mean (pandas): {mean_pd:.4f}")
        print(f"mean (numpy):  {mean_np:.4f}")
        print(f"median (pandas): {median_pd:.4f}")
        print(f"median (numpy):  {median_np:.4f}")
        print(f"variance (sample, ddof=1): {var_sample:.4f}")
        print(f"std (sample, ddof=1):      {std_sample:.4f}")

    # Гистограммы
    print("\n=== Построение гистограмм ===")
    plt.style.use("ggplot")
    for col in cols:
        if col in df_clean.columns:
            s = pd.to_numeric(df_clean[col], errors="coerce").dropna()
            if not s.empty:
                ax = s.plot(kind="hist", bins=30, color="#5b8dd1", edgecolor="#ffffff", title=f"Histogram of {col}")
                ax.set_xlabel(col)
                out = f"hist_{col.lower()}.png"
                plt.tight_layout()
                plt.savefig(out, dpi=130)
                plt.clf()
                print(f"Сохранено: {out}")


if __name__ == "__main__":
    main()


