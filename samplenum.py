"""
Vérificateur d'intégrité et compteur d'échantillons pour Hand-Tracking-Module
Vérifie la cohérence entre gesture_landmarks.npy et gesture_labels.npy.
"""

import os
import numpy as np

DATA_FILE = 'gesture_landmarks.npy'
LABEL_FILE = 'gesture_labels.npy'

def check_dataset():
    print("\n" + "=" * 55)
    print("  DIAGNOSTIC DU JEU DE DONNÉES (samplenum.py)")
    print("=" * 55)

    data_exists = os.path.exists(DATA_FILE)
    label_exists = os.path.exists(LABEL_FILE)

    if not data_exists or not label_exists:
        print(f"❌ Fichiers manquants :")
        if not data_exists:
            print(f"   • Manquant : {DATA_FILE}")
        if not label_exists:
            print(f"   • Manquant : {LABEL_FILE}")
        print("\nExécutez 'python collect.py' pour enregistrer des gestes.")
        return

    try:
        data = np.load(DATA_FILE, mmap_mode='r')
        labels = np.load(LABEL_FILE)

        print("✅ Fichiers chargés avec succès !\n")
        print(f"  • Dimensions des repères (X) : {data.shape}")
        print(f"  • Type de données (dtype)   : {data.dtype}")
        print(f"  • Nombre de labels (y)      : {labels.shape[0]}")

        # Vérification d'alignement
        if data.shape[0] != labels.shape[0]:
            print(f"\n⚠️ ALERTE : Désalignement détecté !")
            print(f"   X a {data.shape[0]} échantillons mais y a {labels.shape[0]} labels !")
        else:
            print("  • Alignement X et y         : Parfait (1:1)")

        # Vérification des dimensions attendues (N, 20, 126)
        if len(data.shape) == 3 and data.shape[1] == 20 and data.shape[2] == 126:
            print("  • Format des séquences      : Conforme (20 frames × 126 coordonnées)")
        else:
            print(f"  • Format des séquences      : Inhabituel ({data.shape}) - Attendu : (N, 20, 126)")

        # Vérification de valeurs corrompues (NaN, Inf)
        sample_check = np.array(data[:min(100, data.shape[0])])
        if np.isnan(sample_check).any() or np.isinf(sample_check).any():
            print("⚠️ Attention : Des valeurs NaN ou Inf ont été détectées dans les repères.")
        else:
            print("  • Intégrité des données     : Aucune valeur NaN ou Inf détectée")

        # Distribution par geste
        unique_labels, counts = np.unique(labels, return_counts=True)
        print("\n" + "-" * 55)
        print("  RÉPARTITION DES ÉCHANTILLONS PAR GESTE :")
        print("-" * 55)
        for lbl, count in zip(unique_labels, counts):
            bar = "█" * min(30, int(count / max(counts) * 30))
            print(f"  {lbl.ljust(15)} : {str(count).rjust(4)} séquences {bar}")
        print("-" * 55)
        print(f"  TOTAL GÉNÉRAL : {len(labels)} séquences ({len(unique_labels)} classes distinctes)\n")

    except Exception as e:
        print(f"❌ Le fichier est corrompu ou illisible. Erreur : {e}\n")

if __name__ == '__main__':
    check_dataset()