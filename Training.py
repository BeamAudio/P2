import librosa
import numpy as np
import pandas as pd
import sys
import pathlib
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt # <-- Añadido para gráficos
import seaborn as sns # <-- Añadido para gráficos más estéticos
import math # Para log10

# --- 1. FEATURE EXTRACTION (Modificado para Power + ZCR) ---

FRAME_SIZE = 160
HOP_SIZE = 80
TARGET_SAMPLE_RATE = 16000 # Puedes ajustar esto a tu SampleRate, ej. 16000

# --- Funciones de características traducidas de C++ ---

def compute_power(frame):
    """
    Calcula la potencia de la trama en dB, aplicando una ventana Hann.
    (Traducción directa de la lógica de C++: 10*log10(mean(pow)))
    """
# ... existing code ...
    N = len(frame)
    if N == 0: 
        return -np.inf # Equivalente a -INFINITY en C++
    
    w = np.hanning(N)
    windowed_frame = frame * w
    
# ... existing code ...
    # np.mean(frame**2) es equivalente al bucle de C++ (pow /= (double)N)
    pow_val = np.mean(np.square(windowed_frame, dtype=np.float64)) # Usar float64 para precisión
    
    if pow_val < 1e-10: # Evitar log(0)
# ... existing code ...
        return -100.0
        
    return 10.0 * math.log10(pow_val)

def compute_am(frame):
# ... existing code ...
    """
    Calcula la Amplitud Media (Mean Absolute Magnitude), aplicando una ventana Hann.
    (Traducción directa de la lógica de C++)
    """
    N = len(frame)
# ... existing code ...
    if N == 0:
        return 0.0
        
    w = np.hanning(N)
# ... existing code ...
    windowed_frame = frame * w
    
    # np.mean(np.abs(windowed_frame)) es equivalente al bucle de C++
    return np.mean(np.abs(windowed_frame))

def compute_zcr(frame, sample_rate):
# ... existing code ...
    """
    Calcula la Tasa de Cruce por Cero (ZCR) normalizada por frecuencia,
    aplicando una ventana Hann.
    (Traducción directa de la lógica de C++)
    """
    N = len(frame)
# ... existing code ...
    if N < 2:
        return 0.0
        
    w = np.hanning(N)
# ... existing code ...
    windowed_frame = frame * w
    
    # x[n] * x[n + 1] < 0 en la señal enventanada
    xn_win = windowed_frame[:-1]
# ... existing code ...
    xn1_win = windowed_frame[1:]
    crossings = np.sum(xn_win * xn1_win < 0)
    
    # Normalización de C++: (zcr * fm) / (2 * (N - 1))
# ... existing code ...
    return (float(crossings) * float(sample_rate)) / (2.0 * float(N - 1))

def compute_power_windowed(x, w):
# ... existing code ...
    """
    Función de ayuda (no usada por el pipeline principal ahora)
    Calcula la potencia de una trama enventanada, normalizada por la energía de la ventana.
    """
    N = len(x)
# ... existing code ...
    if len(w) != N:
        raise ValueError("La señal y la ventana deben tener la misma longitud")
    
    xn_win = x * w
# ... existing code ...
    num = np.sum(np.square(xn_win, dtype=np.float64))
    den = np.sum(np.square(w, dtype=np.float64))

    if den == 0.0:
# ... existing code ...
        return -np.inf
    
    pow_val = num / den
    if pow_val < 1e-10: # Evitar log(0)
# ... existing code ...
        return -100.0

    return 10.0 * math.log10(pow_val)
# ... existing code ...

# --- Fin de las funciones C++ traducidas ---


def extract_features(wav_path):
# ... existing code ...
    """Extrae características (Power y ZCR) de un archivo WAV completo."""
    try:
        audio_float, sample_rate = librosa.load(wav_path, sr=TARGET_SAMPLE_RATE, mono=True)
    except Exception as e:
# ... existing code ...
        print(f"  > Warning: Could not read {wav_path.name}. Error: {e}", file=sys.stderr)
        return None

    features = []
    
    # Crear ventana Hann una vez (aunque las funciones internas ahora la crean)
    # hann_window = np.hanning(FRAME_SIZE) # Ya no es necesario aquí

    for i in range(0, len(audio_float) - FRAME_SIZE, HOP_SIZE):
        frame = audio_float[i : i + FRAME_SIZE]
        if len(frame) < FRAME_SIZE:
            continue
            
        time_s = i / sample_rate
        
        # 1. Calcular Potencia (con ventana Hann interna, según C++)
        power_db = compute_power(frame)
        
        # 2. Calcular Tasa de Cruce por Cero (ZCR)
        # (con ventana Hann interna, según C++)
        zcr = compute_zcr(frame, sample_rate)
        
        features.append([time_s, power_db, zcr])
        
    if not features: return None
    # Columnas actualizadas
    return pd.DataFrame(features, columns=['time', 'power_db', 'zcr'])

# --- NUEVA FUNCIÓN: Carga y Alineación de Etiquetas ---

def load_and_align_labels(features_df, lab_file):
    """
    Carga un archivo .lab y asigna sus etiquetas (ej. 'S', 'V') a cada trama
    en el features_df basado en las marcas de tiempo.
    """
    if not lab_file.exists():
        print(f"  > Warning: Label file not found, skipping: {lab_file.name}", file=sys.stderr)
        return None
    
    features_df['label'] = np.nan # Empezar sin etiquetas
    
    try:
        with open(lab_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 3: continue
                
                start_time = float(parts[0])
                end_time = float(parts[1])
                label = parts[2] # 'S', 'V', etc.

                # Asignar etiqueta a todos los frames cuyo *inicio* esté en este rango
                frame_indices = (features_df['time'] >= start_time) & (features_df['time'] < end_time)
                features_df.loc[frame_indices, 'label'] = label
    except Exception as e:
        print(f"  > Error processing label file {lab_file.name}: {e}", file=sys.stderr)
        return None

    # Eliminar tramas que no recibieron una etiqueta (ej. al final del archivo)
    final_df = features_df.dropna(subset=['label'])
    # Mantener solo 'S' y 'V' (ignorar 'U' u otros si existen)
    final_df = final_df[final_df['label'].isin(['S', 'V'])]
    
    if len(final_df) == 0:
        print(f"  > Warning: No 'S' or 'V' labels found in {lab_file.name}", file=sys.stderr)
        return None
        
    return final_df

# --- 2. MAIN WORKFLOW (Modificado para Carga Supervisada) ---

def main(folder_path):
    # --- Part 1: Feature Extraction and Labeling ---
    audio_folder = pathlib.Path(folder_path)
    if not audio_folder.is_dir():
# ... existing code ...
        print(f"Error: Path is not a directory: {folder_path}", file=sys.stderr)
        return

    print(f"Scanning for audio files and .lab files in: {folder_path}...")
    file_extensions = ("*.wav", "*.mp3", "*.flac", "*.m4a")
    all_audio_files = []
    for ext in file_extensions:
        all_audio_files.extend(list(audio_folder.rglob(ext)))

    if not all_audio_files:
# ... existing code ...
        print("Error: No audio files found.", file=sys.stderr)
        return

    print(f"Found {len(all_audio_files)} audio files. Processing with matching .lab files...")
    all_features = []
    for audio_file in all_audio_files:
        lab_file = audio_file.with_suffix('.lab') # Busca 'mi_audio.wav' -> 'mi_audio.lab'
        
        print(f"Processing: {audio_file.name}")
        df_features = extract_features(audio_file)
        if df_features is None:
            continue
            
        df_labeled = load_and_align_labels(df_features, lab_file)
        if df_labeled is None:
            continue

        all_features.append(df_labeled)
    
    if not all_features:
        print("Error: No features could be extracted or labeled.", file=sys.stderr)
        return
        
    combined_df = pd.concat(all_features, ignore_index=True)
    # Reemplazar -inf con un valor muy bajo (ej. -100 dB) para que el scaler funcione
    combined_df.replace([np.inf, -np.inf], -100.0, inplace=True)
    
    print(f"\nTotal labeled frames for training: {len(combined_df)}")
    print(f"Label distribution:\n{combined_df['label'].value_counts()}")

    # --- Part 2: Optimize SVM (Supervised) ---
    print("\n--- Part 2: Optimizing SVM Classifier (S vs. V) ---")
    
    # Mapear etiquetas de texto ('S', 'V') a números (0, 1) para el SVM
    label_map = {'S': 0, 'V': 1}
    df_train = combined_df.copy()
    df_train['label_num'] = df_train['label'].map(label_map)
    
    # Entrenar SVM con 'power_db' y 'zcr'
    X = df_train[['power_db', 'zcr']]
    y = df_train['label_num']
    
    if len(df_train) < 100:
# ... existing code ...
        print("Error: Not enough labeled data found to train SVM.", file=sys.stderr)
        return

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    scaler_svm = StandardScaler()
    X_train_scaled = scaler_svm.fit_transform(X_train)
    X_test_scaled = scaler_svm.transform(X_test)
    
    param_grid = {'C': [0.01, 0.1, 1, 10, 100]}
    print("Running GridSearchCV...")
    # class_weight='balanced' es MUY importante si tienes más silencio que voz
    model = LinearSVC(dual=True, max_iter=3000, class_weight='balanced')
    grid_search = GridSearchCV(model, param_grid, cv=5, scoring='f1_weighted', n_jobs=-1)
    grid_search.fit(X_train_scaled, y_train)
    
    best_model = grid_search.best_estimator_
    best_params = grid_search.best_params_
    
    y_pred = best_model.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)
    
    print("\n--- Optimization Complete ---")
    print(f"Best 'C' parameter found: {best_params['C']}")
    print(f"Final model accuracy (vs. .lab labels): {accuracy * 100:.2f}%")

    # --- Part 3: Final Learned Parameters ---
    print("\n" + "="*50)
    print("Valores finales aprendidos para el VAD (S=0, V=1)")
    print("="*50)
    
    # Solo parámetros de Power y ZCR
    power_db_mean = scaler_svm.mean_[0]
    power_db_scale = scaler_svm.scale_[0]
    zcr_mean = scaler_svm.mean_[1]
    zcr_scale = scaler_svm.scale_[1]
    
    coef_power_db = best_model.coef_[0][0]
    coef_zcr = best_model.coef_[0][1]
    intercept = best_model.intercept_[0]
    
    print("\n--- Parámetros del Escalador SVM (Scaler) ---")
    print(f"POWER_DB_MEAN = {power_db_mean:.8f}")
    print(f"POWER_DB_SCALE = {power_db_scale:.8f}")
    print(f"ZCR_MEAN = {zcr_mean:.8f}")
    print(f"ZCR_SCALE = {zcr_scale:.8f}")

    print("\n--- Parámetros del Modelo SVM ---")
    print(f"COEF_POWER_DB = {coef_power_db:.8f}")
    print(f"COEF_ZCR = {coef_zcr:.8f}")
    print(f"INTERCEPT = {intercept:.8f}")
    print("="*50)


    # --- Part 4: PLOTTING (NUEVA SECCIÓN) ---
    print("\nGenerating plot...")
    try:
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(1, 1, figsize=(10, 8)) # Un solo gráfico
        
        # --- Gráfico: Resultados del SVM (Regiones de Decisión) ---
        
        # Mapear etiquetas 'S'/'V' a nombres para la leyenda
        label_names_map = {'S': 'Silence (Label)', 'V': 'Voice (Label)'}
        df_train_sample = df_train.sample(n=min(5000, len(df_train))) # Muestrear
        df_train_sample['label_name'] = df_train_sample['label'].map(label_names_map)

        sns.scatterplot(
            data=df_train_sample,
            x='power_db',
            y='zcr', # <-- Eje Y actualizado
            hue='label_name',
            palette={'Silence (Label)': 'gray', 'Voice (Label)': 'blue'},
            alpha=0.6,
            s=10,
            ax=ax
        )
        ax.set_title('Límite de Decisión del SVM (Voz vs. Silencio)')
        ax.set_xlabel('Potencia (dB)')
        ax.set_ylabel('Tasa de Cruce por Cero (ZCR)') # <-- Eje Y actualizado
        
        # --- Dibujar el Límite de Decisión (Región) ---
        # Crear una malla de puntos en el espacio de características
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        xx = np.linspace(xlim[0], xlim[1], 100)
        yy = np.linspace(ylim[0], ylim[1], 100)
        YY, XX = np.meshgrid(yy, xx)
        xy = np.vstack([XX.ravel(), YY.ravel()]).T # Puntos en el espacio original

        # Escalar los puntos de la malla usando el escalador del SVM
        xy_scaled = scaler_svm.transform(xy)
        
        # Predecir la decisión para cada punto en la malla
        Z = best_model.decision_function(xy_scaled).reshape(XX.shape)

        # Dibujar los contornos: el límite (nivel 0) y los márgenes (niveles -1 y 1)
        ax.contour(XX, YY, Z, colors='black', levels=[-1, 0, 1], alpha=0.7,
                       linestyles=['--', '-', '--'])
        # Rellenar las regiones
        ax.contourf(XX, YY, Z, levels=np.linspace(Z.min(), Z.max(), 10), cmap='coolwarm', alpha=0.3)

        ax.legend(title='Clase (Etiqueta .lab)')
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)

        plt.suptitle('Análisis VAD (SVM) usando Power y ZCR (Etiquetas .lab)', fontsize=16, fontweight='bold')
        output_filename = "vad_analysis_plots.png"
        try:
            plt.savefig(output_filename)
            print(f"\nGráfico guardado exitosamente en: {output_filename}")
        except Exception as e_save:
            print(f"\nError al guardar el gráfico: {e_save}")
            
        # plt.show() # Se comenta plt.show() porque causa el error en entornos no interactivos

    except Exception as e:
# ... existing code ...
        print(f"Error al generar gráficos: {e}")
        print("Asegúrate de que 'matplotlib' y 'seaborn' están instalados: pip install matplotlib seaborn")


if __name__ == "__main__":
# ... existing code ...
    if len(sys.argv) != 2:
        print("Usage: python Training.py <path_to_audio_folder>")
    else:
        main(sys.argv[1])