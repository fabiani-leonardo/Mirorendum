import os
import re
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# --- CONFIGURAZIONE ---
CARTELLA_FILE = './notizie_referendum' # Inserisci qui il percorso della tua cartella
FREQUENZA = 'D' # 'D' per giornaliero (Daily), 'W' per settimanale (Weekly)

# Dizionario per tradurre i mesi in italiano in numeri
mesi_it = {
    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
    'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
    'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
}

# Regex per catturare "31ottobre2025" (giorno, mese in lettere, anno)
pattern = re.compile(r'(\d{1,2})([a-z]+)(\d{4})', re.IGNORECASE)

date_estratte = []

# Scorre tutti i file nella cartella
for filename in os.listdir(CARTELLA_FILE):
    if filename.endswith(".txt"):
        match = pattern.search(filename)
        if match:
            giorno = int(match.group(1))
            mese_str = match.group(2).lower()
            anno = int(match.group(3))
            
            if mese_str in mesi_it:
                mese = mesi_it[mese_str]
                try:
                    # Crea un oggetto datetime
                    data_file = datetime(anno, mese, giorno)
                    date_estratte.append(data_file)
                except ValueError:
                    print(f"Data non valida nel file: {filename}")

# Creiamo un DataFrame Pandas
df = pd.DataFrame(date_estratte, columns=['Data'])

if df.empty:
    print("Nessuna data valida trovata nei nomi dei file.")
else:
    # Aggiungiamo una colonna di conteggio (1 per ogni file)
    df['Conteggio'] = 1
    
    # Impostiamo la data come indice
    df.set_index('Data', inplace=True)
    
    # Raggruppiamo i dati (Resample) per la frequenza scelta e sommiamo
    conteggio_temporale = df.resample(FREQUENZA).sum()
    
    # --- PLOT ---
    plt.figure(figsize=(12, 6))
    
    # Crea il grafico a barre (istogramma temporale)
    plt.bar(conteggio_temporale.index, conteggio_temporale['Conteggio'], 
            width=5 if FREQUENZA == 'W' else 1, color='skyblue', edgecolor='black')
    
    titolo_freq = "Settimanale" if FREQUENZA == 'W' else "Giornaliera"
    plt.title(f'Quantità {titolo_freq} di notizie estratte dai file', fontsize=14)
    plt.xlabel('Data', fontsize=12)
    plt.ylabel('Numero di Notizie', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Salva il grafico o mostralo a schermo
    plt.savefig('istogramma_notizie.png')
    plt.show()