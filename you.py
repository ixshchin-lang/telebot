from config import *
import pandas as pd
from main import *

# Чтение файла с семьями
df_families = pd.read_csv('data/key_family.csv')
print(df_families)
print()
# Чтение файла с записями женщин
df_women = pd.read_csv('data/status_women.csv')
print(df_women['family_key'])

