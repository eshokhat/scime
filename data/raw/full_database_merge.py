import pandas as pd

old_db = 'raw/full_database_2000_2025.csv'
new_db = 'raw/full_database_1990_2000.csv'

print("Загрузка данных...")
df_old = pd.read_csv(old_db)
df_new = pd.read_csv(new_db)

combined = pd.concat([df_old, df_new], ignore_index=True)
combined = combined.drop_duplicates(subset=['eid'])

combined.to_csv('full_database_FINAL.csv', index=False)

print(f"Готово! Теперь в базе {len(combined)} уникальных статей.")
print(f"Диапазон лет: {combined['year'].min()} - {combined['year'].max()}")