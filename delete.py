"""
Module de suppression de données pour Hand-Tracking-Module
Permet de supprimer un geste spécifique de manière interactive ou par argument.
Usage :
  python delete.py               -> Mode interactif avec menu de sélection
  python delete.py <nom_geste>   -> Supprime directement le geste spécifié
"""

import os
import sys
import numpy as np

DATA_FILE = 'gesture_landmarks.npy'
LABEL_FILE = 'gesture_labels.npy'

def main():
    if not os.path.exists(DATA_FILE) or not os.path.exists(LABEL_FILE):
        print(f"❌ Erreur : Fichiers '{DATA_FILE}' ou '{LABEL_FILE}' introuvables.")
        print("Veuillez d'abord collecter des données avec collect.py.")
        return

    try:
        X = np.load(DATA_FILE)
        y = np.load(LABEL_FILE)
    except Exception as e:
        print(f"❌ Erreur lors du chargement des fichiers .npy : {e}")
        return

    if len(y) == 0:
        print("⚠️ Le jeu de données est vide.")
        return

    unique_labels, counts = np.unique(y, return_counts=True)
    label_dict = dict(zip(unique_labels, counts))

    print("\n" + "=" * 55)
    print("  GESTIONNAIRE DE SUPPRESSION DE GESTES (delete.py)")
    print("=" * 55)
    print(f"Total d'échantillons dans la base : {len(y)}\n")
    print("Gestes actuellement présents :")
    for idx, (lbl, cnt) in enumerate(label_dict.items(), start=1):
        print(f"  [{idx}] {lbl} : {cnt} séquences")
    print("=" * 55)

    target_gesture = None

    # Si passé en argument de ligne de commande
    if len(sys.argv) > 1:
        arg_val = sys.argv[1].strip()
        if arg_val in label_dict:
            target_gesture = arg_val
        elif arg_val.isdigit() and 1 <= int(arg_val) <= len(unique_labels):
            target_gesture = unique_labels[int(arg_val) - 1]
        else:
            print(f"❌ Geste '{arg_val}' non trouvé dans les données existantes.")
            return
    else:
        # Mode interactif
        try:
            choice = input("\nEntrez le nom ou le numéro du geste à supprimer (ou 'Q' pour annuler) : ").strip()
            if choice.lower() in ['q', 'quit', 'exit', '']:
                print("Suppression annulée.")
                return

            if choice.isdigit() and 1 <= int(choice) <= len(unique_labels):
                target_gesture = unique_labels[int(choice) - 1]
            elif choice in label_dict:
                target_gesture = choice
            elif choice.lower() in [lbl.lower() for lbl in unique_labels]:
                # Tolérance casse
                for lbl in unique_labels:
                    if lbl.lower() == choice.lower():
                        target_gesture = lbl
                        break
            else:
                print(f"❌ '{choice}' ne correspond à aucun geste existant.")
                return
        except KeyboardInterrupt:
            print("\nOpération interrompue.")
            return

    # Confirmation
    samples_to_remove = label_dict[target_gesture]
    confirm = input(f"⚠️ Êtes-vous sûr de vouloir supprimer '{target_gesture}' ({samples_to_remove} séquences) ? [o/N] : ").strip().lower()
    if confirm not in ['o', 'oui', 'y', 'yes']:
        print("Suppression annulée.")
        return

    # Sauvegarde de secours automatique
    backup_data = 'gesture_landmarks_backup.npy'
    backup_label = 'gesture_labels_backup.npy'
    try:
        np.save(backup_data, X)
        np.save(backup_label, y)
        print(f"📦 Sauvegarde de secours créée ({backup_data}).")
    except Exception as e:
        print(f"⚠️ Avertissement lors de la création de la sauvegarde : {e}")

    # Filtrage
    keep_mask = y != target_gesture
    new_X = X[keep_mask]
    new_y = y[keep_mask]

    np.save(DATA_FILE, new_X)
    np.save(LABEL_FILE, new_y)

    print(f"\n✅ Geste '{target_gesture}' supprimé avec succès !")
    remaining_labels, remaining_counts = np.unique(new_y, return_counts=True)
    remaining_dict = dict(zip(remaining_labels, remaining_counts))
    print(f"Échantillons restants ({len(new_y)} total) : {remaining_dict}\n")

if __name__ == '__main__':
    main()
