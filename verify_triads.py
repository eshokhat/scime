import duckdb

def run_validation_query():
    # Подключаемся к локальной базе DuckDB (режим только для чтения безопасен)
    conn = duckdb.connect('database.db', read_only=True)
    
    query = """
        WITH paper_country_counts AS (
            SELECT eid, COUNT(DISTINCT LOWER(TRIM(country))) as total_countries
            FROM countries
            GROUP BY eid
        ),
        valid_papers AS (
            SELECT eid
            FROM paper_country_counts
            WHERE total_countries <= 5  -- ИСКЛЮЧАЕМ МЕГА-ПРОЕКТЫ
        )
        SELECT a.year, a.title, pcc.total_countries
        FROM articles a
        JOIN valid_papers vp ON a.eid = vp.eid
        JOIN paper_country_counts pcc ON a.eid = pcc.eid
        JOIN countries c1 ON a.eid = c1.eid
        JOIN countries c2 ON a.eid = c2.eid
        JOIN countries c3 ON a.eid = c3.eid
        WHERE LOWER(TRIM(c1.country)) = 'israel' 
        AND LOWER(TRIM(c2.country)) = 'united arab emirates'
        AND LOWER(TRIM(c3.country)) = 'morocco'
        AND a.year = 2025
        LIMIT 5;
        """
    # Выполняем запрос и сразу конвертируем в pandas DataFrame для аккуратного вывода
    df = conn.sql(query).df()
    
    if df.empty:
        print("По заданным критериям статьи не найдены.")
    else:
        print(f"Успех! Найдено {len(df)} статей (показаны первые 5):")
        print("-" * 80)
        # Настраиваем pandas, чтобы он не обрезал длинные названия статей в консоли
        import pandas as pd
        pd.set_option('display.max_colwidth', None)
        print(df.to_string(index=False))
        print("-" * 80)

if __name__ == "__main__":
    run_validation_query()