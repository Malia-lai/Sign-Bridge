import React, { useState } from 'react';
import { Database, Trash2, Download, Upload, BarChart3, AlertCircle } from 'lucide-react';
import { GestureStat, GestureSequence } from '../types';

interface DatasetViewerProps {
  gestures: GestureStat[];
  sequences: GestureSequence[];
  onDeleteGesture: (label: string) => void;
  onClearAll: () => void;
  onImportDataset: (importedSequences: GestureSequence[]) => void;
}

export const DatasetViewer: React.FC<DatasetViewerProps> = ({
  gestures,
  sequences,
  onDeleteGesture,
  onClearAll,
  onImportDataset,
}) => {
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const totalSamples = sequences.length;

  const handleExport = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(sequences, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `sign_language_dataset_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        if (Array.isArray(parsed)) {
          onImportDataset(parsed);
        }
      } catch (err) {
        alert("Erreur lors de la lecture du fichier JSON.");
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 shadow-xl flex flex-col h-full">
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800 mb-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-emerald-400" />
            Gestionnaire de Données (samplenum & delete)
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Total : <strong className="text-emerald-400 font-semibold">{totalSamples} séquences</strong> enregistrées
          </p>
        </div>

        <div className="flex gap-2">
          <label className="p-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium cursor-pointer flex items-center gap-1.5 transition-colors">
            <Upload className="w-4 h-4" />
            Importer
            <input type="file" accept=".json" onChange={handleImportFile} className="hidden" />
          </label>
          <button
            onClick={handleExport}
            disabled={totalSamples === 0}
            className="p-2 rounded-xl bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" />
            Exporter
          </button>
        </div>
      </div>

      {/* Dataset Breakdown */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1 max-h-[380px]">
        {gestures.length === 0 ? (
          <div className="text-center py-12 text-zinc-500 text-sm">
            Aucun geste enregistré pour l'instant.
          </div>
        ) : (
          gestures.map((g) => {
            const percentage = totalSamples > 0 ? (g.count / totalSamples) * 100 : 0;
            return (
              <div
                key={g.label}
                className="bg-zinc-950/70 border border-zinc-800/80 rounded-xl p-3 flex flex-col gap-2 hover:border-zinc-700 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white capitalize text-sm">{g.label}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 font-mono">
                      {g.count} éch.
                    </span>
                  </div>

                  {confirmDelete === g.label ? (
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => {
                          onDeleteGesture(g.label);
                          setConfirmDelete(null);
                        }}
                        className="px-2 py-1 bg-red-600 hover:bg-red-500 text-white rounded-md text-xs font-semibold"
                      >
                        Confirmer
                      </button>
                      <button
                        onClick={() => setConfirmDelete(null)}
                        className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-md text-xs"
                      >
                        Annuler
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmDelete(g.label)}
                      title={`Supprimer les données de ${g.label}`}
                      className="p-1.5 text-zinc-400 hover:text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Progress bar representing proportion */}
                <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full rounded-full transition-all duration-300"
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>

      {totalSamples > 0 && (
        <div className="mt-4 pt-3 border-t border-zinc-800 flex justify-between items-center text-xs text-zinc-500">
          <span>{gestures.filter((g) => g.count > 0).length} classes actives</span>
          <button
            onClick={() => {
              if (confirm("Réinitialiser toutes les données collectées ?")) {
                onClearAll();
              }
            }}
            className="text-red-400 hover:underline"
          >
            Vider tout le dataset
          </button>
        </div>
      )}
    </div>
  );
};
